"""One sale-assistance request, in whichever of the three modes it is. Delivered by C30a.

**Nothing here calls a language model.** `pitch` comes back empty, `prompt_version` null and
`usage` zero, and that is a requirement with a test rather than a state of affairs that
happens to hold: the prose, its versioned prompt and the numeric gate that guards it are
C30b, and the split exists so C30b's value can be measured *against* this layer.

The only provider call this module can cause is the **embedding of the question**, and only
in the two modes that have one — and that call is the retrieval's own, not a new one. The
piece-anchored mode with no question touches no vector at all.
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
from jbg_ai.assist.modes import AssistMode, resolve_mode
from jbg_ai.config.settings import Settings
from jbg_ai.indexing.embeddings import EmbeddingClient
from jbg_ai.knowledge.search import KnowledgeCitation, KnowledgeSearchIndex, search_knowledge
from jbg_ai.retrieval.orchestrator import retrieve_products
from jbg_ai.retrieval.ports import FamilyMember, ProductSearchPort, SourceDocument

logger = logging.getLogger(__name__)

STAGE = "assist"

#: What the pitch is until C30b writes one. An empty string and not a placeholder sentence:
#: a placeholder is something a client can ship by accident.
EMPTY_PITCH = ""


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

    logger.info(
        "stage=%s trace_id=%s mode=%s intent=%s groups=%s members=%s warnings=%s "
        "citations=%s abstained=%s roster=%s threshold=%s",
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
        extra={"trace_id": principal.trace_id},
    )

    return AssistResponse(
        intent=mode.intent,
        groups=groups,
        # C30b's half of the split, declared as absence rather than faked.
        pitch=EMPTY_PITCH,
        citations=[_to_citation(item, product_id=anchored_id) for item in citations],
        warnings=warnings,
        clarification_question=None,
        usage=Usage(),
        abstained=abstained,
        prompt_version=None,
        trace_id=principal.trace_id,
        effective_pos_id=principal.pos_id or "",
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
