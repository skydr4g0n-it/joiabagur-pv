"""The substitutes engine: what to offer when the piece the customer asked for is gone. C26.

Product to product, which changes the cost of the whole capability. The anchor is a
`product_id` and its embedding is **already stored**, so this path calls no provider, runs no
lexical branch, expands no synonyms and fuses nothing: one statement, one ordering.

**Why this is not `orchestrator.py`.** That module answers a question typed by a person and
spends five responsibilities doing it. Nothing here shares them. What IS shared is reused
verbatim — `projection.resolve_scope`, `ports`, and `filters.business_score` with
`OUT_OF_STOCK_BUCKET` — so the meaning of "out of stock" keeps living in exactly one place.

**Why `fuse()` is not called.** There is one candidate list. Fusion combines the opinions of
several rankers, and a fusion over one list is the identity map with a rank-reciprocal
rounding error. `fusion.py` used to predict this module as its next caller; the prediction
was wrong and that docstring now says so.

**Why `demotion_rank` is not reused, which is the trap this module exists to avoid.** Its
second component is `int(_size_mismatch(...))`, an INTEGER BLOCK, and an integer block does
not break a tie — it PARTITIONS. Every candidate of a different size would land behind every
candidate of the right one, however close the design, which sends the source product's own
family variants to the tail by construction. That is not a hypothesis: C25 measured the shape
with its rotation term and found 11.067 inverted pairs, 71,2 % of them more than ten
positions apart, and withdrew it. Here the size enters the tail as a CONTINUOUS term, so it
buys positions instead of banishing rows, and the sibling of another size stays visible.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from uuid import UUID

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.schemas.common import DebugInfo
from jbg_ai.api.schemas.retrieval import (
    SimilaritySignals,
    SubstituteResult,
    SubstitutesRequest,
    SubstitutesResponse,
)
from jbg_ai.config import Settings
from jbg_ai.enrichment.vocab import fold
from jbg_ai.retrieval.errors import UnusableSourceProductError
from jbg_ai.retrieval.filters import BusinessWeights, business_score
from jbg_ai.retrieval.orchestrator import clamp_score, parse_body_filters
from jbg_ai.retrieval.ports import NeighbourHit, ProductSearchPort, SourceDocument
from jbg_ai.retrieval.projection import (
    ProjectionFreshness,
    default_freshness,
    parse_pos_id,
    resolve_scope,
)
from jbg_ai.stubs.responses import over_retrieval_count

logger = logging.getLogger(__name__)

#: `visual_similarity` is null by design and not by omission: §15.7 of the RAG design keeps
#: the visual and the textual vector spaces unfused, so there is no number to put here that
#: would mean what the field's name says. The contract makes it nullable precisely for this,
#: while `style_similarity` beside it is required and not nullable.
VISUAL_SIMILARITY_UNAVAILABLE = None

#: What `match_reasons` says when NEITHER side carries style tags. It exists because
#: `SimilaritySignals.style_similarity` is required and not nullable, so an absence of data
#: has to be emitted as `0.0` — and a bare zero reads as "these styles differ", which is a
#: statement the catalogue cannot support: measured, only 1 of 404 real products has any
#: same-type candidate to share a style tag with at all.
NO_STYLE_TAGS_REASON = "sin etiquetas de estilo que comparar"

#: Substitutes never abstain, and this is a MEASURED decision rather than a deferral. Over a
#: sample of 300 documents the distance to the nearest neighbour runs to a maximum of 0,123
#: for products with a family and 0,255 for products without one, and the second range
#: CONTAINS the first — the same containment that stopped C25 re-fixing its scalar threshold.
#: In a catalogue of 1.168 pieces of Menorcan sea jewellery everything resembles something,
#: so an absolute bound either accepts everything or starts rejecting good cases. The unusable
#: source product is the real degenerate case and it is handled as an explicit error instead.
SUBSTITUTES_NEVER_ABSTAIN = False


@dataclass(frozen=True)
class _Scored:
    """A candidate with its ordering key already composed. Nothing here reaches the wire."""

    hit: NeighbourHit
    similarity: float
    size_penalty: float
    availability_penalty: float
    material_overlap: float
    style_similarity: float
    family_match: bool

    @property
    def order_score(self) -> float:
        """`sim - w_size*[talla distinta] - w_availability*[agotado]`. Higher is better.

        Every term is continuous and every penalty only ever SUBTRACTS, which is what keeps
        the key a ranking instead of a partition. It is deliberately NOT clamped here:
        clamping would flatten every strongly penalised candidate onto one value and lose
        the order between them. The clamp happens once, on the way out, where the contract
        asks for a `score` inside `[0, 1]`.
        """
        return self.similarity - self.size_penalty - self.availability_penalty


def _jaccard(left: list[str], right: list[str]) -> float:
    """Overlap of two tag sets, folded. Zero when either side is empty.

    Zero and not `None`, because the contract's field is required and not nullable — and
    zero-because-empty is a different statement from zero-because-disjoint, which is why the
    empty case is declared in `match_reasons` instead of being left to the reader to guess.
    """
    first = {fold(value) for value in left if value}
    second = {fold(value) for value in right if value}
    if not first or not second:
        return 0.0
    return len(first & second) / len(first | second)


def _size_differs(source_size: str | None, candidate_size: str | None) -> bool:
    """True only when BOTH sides declare a size and the two disagree.

    **An absent size is not a mismatch**, and this is the guard the exploration's simulation
    demanded: with `'mini' IS DISTINCT FROM NULL` every sized candidate of an unsized source
    was being penalised for *having* a size. It is not cosmetic — 54 % of the rings carry no
    `size_label` — and it is the rule `ports.py` already writes down for the business
    signals: a signal with no datum must not be read as a signal with a bad one.
    """
    if source_size is None or candidate_size is None:
        return False
    return fold(source_size) != fold(candidate_size)


def _score_candidate(
    hit: NeighbourHit,
    source: SourceDocument,
    *,
    weight_size: float,
    weights: BusinessWeights,
) -> _Scored:
    """Compose one candidate's ordering key and its four declared signals."""
    # `business_score` returns 0.0 or `-availability`, reused rather than re-derived so that
    # the meaning of "out of stock" — `qty_bucket == OUT_OF_STOCK_BUCKET`, and an ABSENT row
    # costing nothing — keeps living in `filters.py` alone.
    return _Scored(
        hit=hit,
        similarity=clamp_score(hit.distance),
        size_penalty=(
            weight_size if _size_differs(source.size_label, hit.size_label) else 0.0
        ),
        availability_penalty=-business_score(hit, weights),
        material_overlap=_jaccard(source.materials, hit.materials),
        style_similarity=_jaccard(source.style_tags, hit.style_tags),
        family_match=source.family_id is not None and hit.family_id == source.family_id,
    )


def _ordering_key(item: _Scored) -> tuple[float, float, UUID]:
    """Descending by the composed score, then by material overlap, then deterministic.

    Material overlap is a **strict tiebreak and never a weight**. Making it a fourth term of
    the score would mean choosing how much similarity one shared material is worth, and no
    query of the golden set can calibrate that number — the same reason the price band was
    kept out of the ordering. As a tiebreak it decides only between candidates the composed
    key has already declared equal, so it cannot reorder anything it was not asked to.

    `product_id` last mirrors the statement's own final key: without it `LIMIT` would cut
    inside a tie and two identical runs could disagree.
    """
    return (-item.order_score, -item.material_overlap, item.hit.product_id)


def _match_reasons(item: _Scored, source: SourceDocument) -> list[str]:
    """The human-readable half of the explanation, and the valve of the frozen contract.

    `SimilaritySignals` cannot express the **size**, which is the attribute that actually
    discriminates in half of the reserved golden-set queries, so it is stated here. No price
    and no stock FIGURE may appear: .NET owns both, and a number written here would be one
    this service cannot stand behind. **That includes the price band**, whose values are
    literally euro ranges on the live catalogue, so only the FACT that two bands differ is
    stated and never which two — see the comment on the band clause below, which carries the
    measurement that rules out naming them.
    """
    reasons: list[str] = []

    if source.size_label is not None and item.hit.size_label is not None:
        if _size_differs(source.size_label, item.hit.size_label):
            reasons.append(
                f"talla distinta ({item.hit.size_label}) - se pidio {source.size_label}"
            )
        else:
            reasons.append(f"misma talla ({item.hit.size_label})")
    elif source.size_label is not None:
        reasons.append(f"sin talla declarada - se pidio {source.size_label}")

    if item.family_match:
        reasons.append("misma familia")

    shared = sorted(
        {fold(value) for value in source.materials if value}
        & {fold(value) for value in item.hit.materials if value}
    )
    if shared:
        reasons.append("mismo material (" + ", ".join(shared) + ")")

    if not source.style_tags and not item.hit.style_tags:
        reasons.append(NO_STYLE_TAGS_REASON)

    # The band is named as a FACT and never as a value. Measured on the live catalogue, every
    # `price_band` is literally a euro range — `30-80`, `150-300`, `lt-30` — so printing it
    # here would put a price figure on the wire from Python, which is precisely what the
    # boundary rule forbids: .NET owns price, and `api/schemas/common.py` says in writing that
    # no model here carries a price figure. That the bands differ is not a figure; `30-80` is.
    if (
        source.price_band is not None
        and item.hit.price_band is not None
        and item.hit.price_band != source.price_band
    ):
        reasons.append("otra banda de precio")

    return reasons


def _to_result(
    item: _Scored, source: SourceDocument, *, projection_age_seconds: float | None
) -> SubstituteResult:
    """Render one candidate.

    `score` carries the COMPOSED key clamped into the contract's `[0, 1]`, and not the raw
    cosine similarity: it is what ordered the list. The clamp cannot invert anything because
    it is monotone — a key below zero was already behind every key above it — so the emitted
    scores fall along the returned order. The raw similarity survives in `debug.vector_score`
    so a reader can still see what the penalties cost.

    The projection age travels in `debug.notes` because `SubstitutesResponse` carries no
    `projection_age_seconds` field and the contract is frozen; `RetrievalResponse` has one
    and this model does not. See the note in `api/routers/retrieval.py`.
    """
    notes: list[str] = []
    if projection_age_seconds is not None:
        notes.append(f"projection_age_seconds:{projection_age_seconds:.1f}")
    if item.size_penalty:
        notes.append(f"size_penalty:{item.size_penalty:g}")
    if item.availability_penalty:
        notes.append(f"availability_penalty:{item.availability_penalty:g}")

    return SubstituteResult(
        product_id=str(item.hit.product_id),
        sku=item.hit.sku,
        score=min(max(item.order_score, 0.0), 1.0),
        match_reasons=_match_reasons(item, source),
        materials=list(item.hit.materials),
        family_id=str(item.hit.family_id) if item.hit.family_id is not None else None,
        variant_label=item.hit.variant_label,
        similarity_signals=SimilaritySignals(
            material_overlap=item.material_overlap,
            style_similarity=item.style_similarity,
            visual_similarity=VISUAL_SIMILARITY_UNAVAILABLE,
            family_match=item.family_match,
        ),
        debug=DebugInfo(
            vector_score=item.similarity,
            lexical_score=None,
            rerank_score=None,
            notes=notes,
        ),
    )


def _require_usable(source: SourceDocument | None, product_id: str) -> SourceDocument:
    """Three unusable cases, three sentences, and never a 200 with an empty list.

    An empty success is indistinguishable from a catalogue that genuinely holds no
    substitute, and the operator's panel paints the same "nothing found" screen over both.
    Naming the cause is the signature this project has kept since C17.
    """
    if source is None:
        raise UnusableSourceProductError(
            product_id, "it is not present in the retrieval index"
        )
    if not source.is_active:
        raise UnusableSourceProductError(
            product_id, "it is present in the retrieval index but inactive"
        )
    if not source.has_embedding:
        raise UnusableSourceProductError(
            product_id, "it is indexed but carries no embedding, so it has no neighbours"
        )
    return source


async def retrieve_substitutes(
    payload: SubstitutesRequest,
    principal: ServicePrincipal,
    *,
    settings: Settings,
    search: ProductSearchPort,
    weight_size: float | None = None,
    business_weight_availability: float | None = None,
    pos_signals: bool | None = None,
    projection_max_age_seconds: int | None = None,
    freshness: ProjectionFreshness | None = None,
) -> SubstitutesResponse:
    """Serve one substitutes request. No embedding provider is called on this path.

    The configuration knobs are call parameters and not only settings, for the reason C24
    fixed: a sweep runs many configurations inside one process, and putting them on
    `SubstitutesRequest` would move the frozen `openapi.json`. None of them mutates
    `settings`.

    `payload.pos_id` is ignored on purpose — the scope comes from the token — and
    `payload.reason` governs nothing: it is free text in the frozen contract, so it is
    propagated to the trace and nowhere else. Turning it into an enumeration would mean
    moving that contract.
    """
    started = time.perf_counter()
    w_size = settings.jpv_substitute_weight_size if weight_size is None else weight_size
    weights = BusinessWeights(
        availability=(
            settings.jpv_business_weight_availability
            if business_weight_availability is None
            else business_weight_availability
        ),
    )
    read_signals = (
        settings.jpv_pos_prefilter_enabled if pos_signals is None else pos_signals
    )
    max_age = (
        settings.jpv_pos_projection_max_age_seconds
        if projection_max_age_seconds is None
        else projection_max_age_seconds
    )

    # Parsed even when the signals are off, exactly as on the product path: a token whose
    # point of sale cannot be read is broken whatever this request intends to do with it.
    pos_id = parse_pos_id(principal.pos_id)

    try:
        source_id = UUID(payload.product_id)
    except ValueError as exc:
        raise UnusableSourceProductError(
            payload.product_id, "it is not a valid product identifier"
        ) from exc

    source = _require_usable(await search.source_document(source_id), payload.product_id)

    # The scope is resolved for its SIGNAL only. `scope.pos_id` feeds `signal_pos_id`, never
    # a restricting parameter — `neighbours_of` does not have one — so availability can
    # demote a candidate and can never remove it. C34 owns the exclusion, on the .NET side.
    scope = await resolve_scope(
        pos_id,
        search=search,
        enabled=read_signals,
        max_age_seconds=max_age,
        freshness=freshness or default_freshness,
    )

    filters = parse_body_filters(payload.filters)
    window = over_retrieval_count(payload.top_k)
    hits = await search.neighbours_of(
        source_id,
        piece_type=source.piece_type,
        depth=window,
        exclude_product_ids=filters.exclude_product_ids,
        signal_pos_id=scope.pos_id,
    )

    scored = sorted(
        (
            _score_candidate(hit, source, weight_size=w_size, weights=weights)
            for hit in hits
        ),
        key=_ordering_key,
    )
    results = [
        _to_result(item, source, projection_age_seconds=scope.reported_age)
        for item in scored
    ]

    logger.info(
        "stage=substitutes trace_id=%s latency_ms=%.1f source=%s piece_type=%s "
        "candidates=%s returned=%s demoted_size=%s demoted_availability=%s "
        "w_size=%s w_availability=%s reading_scope=%s projection_age_seconds=%s reason=%s",
        principal.trace_id,
        (time.perf_counter() - started) * 1000,
        payload.product_id,
        source.piece_type,
        len(hits),
        len(results),
        sum(1 for item in scored if item.size_penalty),
        sum(1 for item in scored if item.availability_penalty),
        w_size,
        weights.availability,
        scope.pos_id is not None,
        None if scope.reported_age is None else round(scope.reported_age, 1),
        payload.reason,
        extra={"trace_id": principal.trace_id},
    )

    return SubstitutesResponse(
        results=results,
        # What the retriever PRODUCED, which is the over-retrieval window and not `top_k`:
        # the contract documents `top_k` as the page .NET wants *after* hydrating and
        # filtering, so it has to be given more than it asked for and told how much more.
        candidates_returned=len(results),
        low_confidence=SUBSTITUTES_NEVER_ABSTAIN,
        trace_id=principal.trace_id,
        effective_pos_id=principal.pos_id or "",
    )
