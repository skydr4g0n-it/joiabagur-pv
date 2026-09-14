"""One sale-assistance request, in whichever of the three modes it is. C30a, generating since C30b.

**Two of the three modes now call a language model, and one never does.** The piece with no
question and the piece with a question hand what this module has already assembled to the
generation layer; the free query does not, because classifying a query is C31's work and an
argument written over a candidate set whose intent nobody determined is prose about a guess.
An abstained request does not call either: writing confidently about an empty candidate set is
the failure the abstention rule exists to prevent.

`pitch_client` is **injected and never built here**, like every other port this module takes.
A deployment without it serves exactly the response C30a served — empty argument, absent prompt
version, zero usage — which is what makes the generation layer measurable as an ablation
against the structured one, and what makes a deployment with no provider credential a
degradation rather than an outage.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from uuid import UUID

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.schemas.assist import (
    AssistGroup,
    AssistGroupMember,
    AssistRequest,
    AssistResponse,
    Citation,
)
from jbg_ai.api.schemas.common import Usage
from jbg_ai.api.schemas.retrieval import RetrievalRequest, RetrievalResult
from jbg_ai.assist.constants import (
    DEFAULT_MATERIAL_CAP,
    DEFAULT_PITCH_SECTIONS,
    FAMILY_ROSTER_CAP,
    WARNING_FAMILY_HAS_VARIANTS,
    WARNING_SIZE_LABEL_MISSING,
)
from jbg_ai.assist.errors import UnusableAnchorProductError
from jbg_ai.assist.grounding import ground_piece
from jbg_ai.assist.knowledge_scope import piece_scoped_exclusions
from jbg_ai.assist.llm import AssistLlm
from jbg_ai.assist.modes import AssistMode, resolve_mode
from jbg_ai.assist.pitch import EMPTY_PITCH, PitchOutcome, generate_pitch
from jbg_ai.assist.prompt import PitchCitation, payload_from
from jbg_ai.config.settings import Settings
from jbg_ai.indexing.embeddings import EmbeddingClient
from jbg_ai.knowledge.search import KnowledgeCitation, KnowledgeSearchIndex, search_knowledge
from jbg_ai.retrieval.orchestrator import retrieve_products
from jbg_ai.retrieval.ports import FamilyMember, ProductSearchPort, SourceDocument

logger = logging.getLogger(__name__)

STAGE = "assist"


def _require_usable(source: SourceDocument | None, product_id: str) -> SourceDocument:
    """Three unusable cases, three sentences. The C26 pattern, reused rather than restated."""
    if source is None:
        raise UnusableAnchorProductError(
            product_id, "it is not present in the retrieval index"
        )
    if not source.is_active:
        raise UnusableAnchorProductError(
            product_id, "it is present in the retrieval index but inactive"
        )
    if not source.has_embedding:
        raise UnusableAnchorProductError(
            product_id, "it is indexed but carries no embedding, so it cannot be assisted"
        )
    return source


def _parse_product_id(raw: str) -> UUID:
    try:
        return UUID(raw)
    except (ValueError, AttributeError) as exc:
        raise UnusableAnchorProductError(
            raw, "it is not a valid product identifier"
        ) from exc


def _member_from_roster(member: FamilyMember, *, score: float) -> AssistGroupMember:
    return AssistGroupMember(
        product_id=str(member.product_id),
        sku=member.sku,
        variant_label=member.variant_label,
        materials=list(member.materials),
        score=score,
        # The roster is an enumeration and not a retrieval: nothing matched, so there is no
        # reason to report. An invented one would be the decoration C30a exists to avoid.
        match_reasons=[],
    )


def _member_from_result(result: RetrievalResult) -> AssistGroupMember:
    return AssistGroupMember(
        product_id=result.product_id,
        sku=result.sku,
        variant_label=result.variant_label,
        materials=list(result.materials),
        score=result.score,
        match_reasons=list(result.match_reasons),
    )


def _group_results(results: Sequence[RetrievalResult]) -> list[AssistGroup]:
    """Group candidates by family, preserving rank, with *null family ⇒ one member*.

    The invariant is enforced structurally rather than asserted afterwards: candidates with
    no family never share a bucket, so no code path can produce the group the contract
    forbids. Order is the retrieval's — a group takes the position of its best member — so
    grouping never reorders what the ranking decided.
    """
    groups: list[AssistGroup] = []
    by_family: dict[str, AssistGroup] = {}
    for result in results:
        member = _member_from_result(result)
        if result.family_id is None:
            groups.append(AssistGroup(family_id=None, family_label=None, members=[member]))
            continue
        existing = by_family.get(result.family_id)
        if existing is None:
            group = AssistGroup(
                family_id=result.family_id, family_label=None, members=[member]
            )
            by_family[result.family_id] = group
            groups.append(group)
        else:
            existing.members.append(member)
    return groups


def _anchored_group(
    source: SourceDocument, roster: Sequence[FamilyMember]
) -> AssistGroup:
    """The group of the anchored piece: its family when it has one, itself when it does not."""
    if source.family_id is None or not roster:
        return AssistGroup(
            family_id=None,
            family_label=None,
            members=[
                AssistGroupMember(
                    product_id=str(source.product_id),
                    sku=source.sku,
                    variant_label=None,
                    materials=list(source.materials),
                    # The piece the caller named, at full score: it was not ranked against
                    # anything, it was asked for.
                    score=1.0,
                    match_reasons=[],
                )
            ],
        )
    label = next(
        (member.family_name for member in roster if member.family_name is not None), None
    )
    return AssistGroup(
        family_id=str(source.family_id),
        family_label=label,
        members=[_member_from_roster(member, score=1.0) for member in roster],
    )


def _to_citation(
    citation: KnowledgeCitation, *, product_id: str | None
) -> Citation:
    return Citation(
        citation_id=citation.citation_id,
        document_title=citation.document_title,
        section_title=citation.section_title,
        doc_type=citation.doc_type,
        claim_scope=citation.claim_scope,
        score=min(max(citation.score, 0.0), 1.0),
        snippet=citation.content,
        product_id=product_id,
    )


def _warnings(
    *, size_label: str | None, roster_size: int, has_family: bool
) -> list[str]:
    """The two codes of the closed vocabulary, from data, by rule, in a stable order.

    `family_has_variants` reads the **roster** and never the candidate count: a family of
    four whose retrieval returned one still has four, and a warning computed from what came
    back would be silent exactly when the operator most needs it.

    There is no stock warning here and there is no place to add one: this service holds an
    availability bucket for ranking that can be minutes stale, and "critical stock" said out
    loud with twelve units in the drawer is the assistant's credibility at the counter. C34
    owns those two, after hydration.
    """
    codes: list[str] = []
    if has_family and roster_size > 1:
        codes.append(WARNING_FAMILY_HAS_VARIANTS)
    if not size_label:
        codes.append(WARNING_SIZE_LABEL_MISSING)
    return codes


async def assist_sale(
    payload: AssistRequest,
    principal: ServicePrincipal,
    *,
    settings: Settings,
    embed: EmbeddingClient,
    search: ProductSearchPort,
    knowledge: KnowledgeSearchIndex,
    pitch_client: AssistLlm | None = None,
    abstain: bool | None = None,
    knowledge_distance_threshold: float | None = None,
    pitch_sections: Sequence[str] = DEFAULT_PITCH_SECTIONS,
    material_cap: int = DEFAULT_MATERIAL_CAP,
    roster_cap: int = FAMILY_ROSTER_CAP,
    citation_top_k: int = 5,
) -> AssistResponse:
    """Serve one request. Every configuration knob is a parameter, none is read here.

    `abstain` and `knowledge_distance_threshold` travel as arguments and `Settings` supplies
    only their defaults, so an evaluation can compare configurations **inside one process**
    without restarting anything — the pattern C20, C23 and C25 established and the one the
    abstention capability now requires of every consuming path.

    `payload.pos_id` is ignored on purpose: the scope is the token's, as everywhere in `/v1`.
    """
    mode = resolve_mode(product_id=payload.product_id, query=payload.query)
    threshold = (
        settings.jpv_knowledge_distance_threshold
        if knowledge_distance_threshold is None
        else knowledge_distance_threshold
    )
    # Stripped once and used for BOTH the retrieval and the knowledge search. Measured: the
    # embedding cache is keyed on a hash of the exact text, so a trailing space is a miss and
    # M3 would pay a second embedding for a difference nobody can see.
    question = (payload.query or "").strip()

    groups: list[AssistGroup] = []
    citations: tuple[KnowledgeCitation, ...] = ()
    abstained = False
    focus_source: SourceDocument | None = None
    roster: list[FamilyMember] = []

    if mode.is_anchored:
        product_id = str(payload.product_id)
        focus_source = _require_usable(
            await search.source_document(_parse_product_id(product_id)), product_id
        )
        if focus_source.family_id is not None:
            roster = list(
                await search.family_roster(focus_source.family_id, cap=roster_cap)
            )
        groups = [_anchored_group(focus_source, roster)]

        if mode is AssistMode.PIECE_ONLY:
            # No vector search of any kind: the addresses are exact.
            citations = await ground_piece(
                focus_source.materials,
                index=knowledge,
                sections=pitch_sections,
                material_cap=material_cap,
            )
        else:
            citations = await search_knowledge(
                question,
                embed=embed,
                index=knowledge,
                top_k=citation_top_k,
                exclude_documents=piece_scoped_exclusions(focus_source.materials),
                distance_threshold=threshold,
                trace_id=principal.trace_id,
            )
    else:
        decisions: list[bool] = []
        retrieved = await retrieve_products(
            RetrievalRequest(query=question, top_k=payload.top_k),
            principal,
            settings=settings,
            embed=embed,
            search=search,
            abstain=abstain,
            on_abstention=decisions.append,
        )
        abstained = bool(decisions and decisions[-1])
        if not abstained:
            groups = _group_results(retrieved.results)
            citations = await search_knowledge(
                question,
                embed=embed,
                index=knowledge,
                top_k=citation_top_k,
                distance_threshold=threshold,
                trace_id=principal.trace_id,
            )
            # The warnings describe the piece the response leads with. Reading the focus
            # piece costs one primary-key lookup and is the same read the anchored modes
            # make, which is why `size_label` never has to be smuggled out of the retrieval
            # orchestrator: the port already answers this question.
            focus_source = await _focus_of(groups, search=search)
            if focus_source is not None and focus_source.family_id is not None:
                roster = list(
                    await search.family_roster(focus_source.family_id, cap=roster_cap)
                )

    warnings = (
        _warnings(
            size_label=focus_source.size_label,
            roster_size=len(roster),
            has_family=focus_source.family_id is not None,
        )
        if focus_source is not None
        else []
    )
    anchored_id = str(payload.product_id) if mode.is_anchored else None

    # The two cuts, **before** any provider call: the free-query mode and an abstained
    # request. They overlap today — abstention is only reachable on the query path, which is
    # the mode that does not generate — and both are stated anyway, because they are two
    # different reasons and the day an anchored mode can abstain only one of them holds.
    outcome: PitchOutcome | None = None
    if pitch_client is not None and mode.is_anchored and not abstained:
        outcome = await generate_pitch(
            _pitch_payload(
                focus_source, roster, citations, warnings=warnings, question=question
            ),
            mode,
            client=pitch_client,
        )
        if not outcome.withheld:
            # The citations of a response carrying an argument are the ones the argument
            # **used and that verified**. When it was withheld they stay the ones that
            # grounded the response: a degraded response must never be poorer than the one
            # the structured layer produces on its own, which is what keeps the ablation
            # comparable — same route, same candidates, same citations, with prose and
            # without it.
            citations = _cited(citations, outcome.used_citation_ids)

    logger.info(
        "stage=%s trace_id=%s mode=%s intent=%s groups=%s members=%s warnings=%s "
        "citations=%s abstained=%s roster=%s threshold=%s prompt_version=%s model=%s "
        "prompt_tokens=%s completion_tokens=%s total_tokens=%s provider_calls=%s "
        "pitch_ms=%.1f pitch_chars=%s pitch_sha256=%s violations=%s withdrawn=%s "
        "provider_error=%s",
        STAGE,
        principal.trace_id,
        mode.value,
        mode.intent,
        len(groups),
        sum(len(group.members) for group in groups),
        ",".join(warnings) or "none",
        ",".join(citation.citation_id for citation in citations) or "none",
        abstained,
        len(roster),
        threshold,
        # Everything of the generation **except the argument itself**: the version, the model,
        # what it cost, how long it took, which citations it used, why anything was refused,
        # how long the text is and a hash of it. A log line is durable storage outside the
        # database and carries no point-of-sale scope, while the response does; the text is
        # re-derivable from a versioned prompt at temperature zero, which is what makes not
        # storing it viable rather than merely cautious.
        outcome.prompt_version if outcome is not None else None,
        outcome.usage.model if outcome is not None else None,
        outcome.usage.prompt_tokens if outcome is not None else 0,
        outcome.usage.completion_tokens if outcome is not None else 0,
        outcome.usage.total_tokens if outcome is not None else 0,
        outcome.usage.calls if outcome is not None else 0,
        outcome.elapsed_ms if outcome is not None else 0.0,
        len(outcome.pitch) if outcome is not None else 0,
        outcome.digest if outcome is not None else "none",
        ",".join(outcome.causes()) if outcome is not None and outcome.violations else "none",
        ",".join(outcome.withdrawn_citation_ids)
        if outcome is not None and outcome.withdrawn_citation_ids
        else "none",
        outcome.provider_error if outcome is not None else None,
        extra={"trace_id": principal.trace_id},
    )

    return AssistResponse(
        intent=mode.intent,
        groups=groups,
        pitch=outcome.pitch if outcome is not None else EMPTY_PITCH,
        citations=[_to_citation(item, product_id=anchored_id) for item in citations],
        warnings=warnings,
        # Declared **of C31**, not deferred by accident: emitting a clarification question is a
        # routing decision over a free query, which is the capability that classifies one.
        clarification_question=None,
        usage=_usage(outcome),
        abstained=abstained,
        # "The generation layer ran", and no longer "there is a pitch". An empty argument alone
        # cannot tell a deployment that does not generate from a generation that was rejected,
        # and that distinction is the only evidence a consumer has that the guard acted.
        prompt_version=outcome.prompt_version if outcome is not None else None,
        trace_id=principal.trace_id,
        effective_pos_id=principal.pos_id or "",
    )


def _pitch_payload(
    source: SourceDocument | None,
    roster: Sequence[FamilyMember],
    citations: Sequence[KnowledgeCitation],
    *,
    warnings: Sequence[str],
    question: str,
):
    """What the model is handed — and therefore, exactly, which figures it may write.

    Built from the objects this module already holds, never from a rendered string: the numeric
    gate reads this object, and a gate that read the prompt text would admit the numerals of
    its own instructions.
    """
    return payload_from(
        sku=source.sku if source is not None else "",
        piece_type=source.piece_type if source is not None else None,
        materials=list(source.materials) if source is not None else [],
        size_label=source.size_label if source is not None else None,
        variant_label=next(
            (
                member.variant_label
                for member in roster
                if source is not None and member.product_id == source.product_id
            ),
            None,
        ),
        family_label=next(
            (member.family_name for member in roster if member.family_name is not None),
            None,
        ),
        variants=[(member.sku, member.variant_label) for member in roster],
        warnings=list(warnings),
        citations=[
            PitchCitation(
                citation_id=item.citation_id,
                document_title=item.document_title,
                section_title=item.section_title,
                claim_scope=item.claim_scope,
                content=item.content,
            )
            for item in citations
        ],
        query=question or None,
    )


def _cited(
    citations: Sequence[KnowledgeCitation], used: Sequence[str]
) -> tuple[KnowledgeCitation, ...]:
    """The grounding fragments the argument declared, in the order it declared them."""
    by_id = {item.citation_id: item for item in citations}
    return tuple(by_id[item] for item in used if item in by_id)


def _usage(outcome: PitchOutcome | None) -> Usage:
    """The contract's usage, summed across every call the request made.

    The model is reported **only when a call actually returned one**. Naming a model beside
    zero tokens is precisely the shape C09's seam produces and the reason it could not be
    reused: it reads as a measured cost and is not one.
    """
    if outcome is None:
        return Usage()
    return Usage(
        prompt_tokens=outcome.usage.prompt_tokens,
        completion_tokens=outcome.usage.completion_tokens,
        total_tokens=outcome.usage.total_tokens,
        model=outcome.usage.model if outcome.usage.calls else None,
    )


async def _focus_of(
    groups: Sequence[AssistGroup], *, search: ProductSearchPort
) -> SourceDocument | None:
    """The piece a query-only response leads with, read from the index.

    A response with no anchor still describes **a** piece to the operator — the first member
    of the first group, which is the top-ranked candidate — and the two warnings are
    statements about a piece. Attributing them to the whole result set instead would make
    `size_label_missing` fire whenever any of fifteen candidates lacked a size, which is
    almost always and therefore informs of nothing.

    An unusable row here is **not** an error: unlike an anchored piece, this one was chosen
    by the retrieval rather than named by the caller, so the honest response is the groups
    without the warnings.
    """
    if not groups or not groups[0].members:
        return None
    try:
        product_id = UUID(groups[0].members[0].product_id)
    except ValueError:
        return None
    return await search.source_document(product_id)
