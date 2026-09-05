"""Fuse a vector list and two lexical lists into one answer. C14 built the vector branch; C21
connects the lexical one and makes `mode` mean what it says.

Two cables were stripped and left unconnected before this change. `ai.product_document.tsv` —
a generated `to_tsvector('spanish', doc_text)` column with its GIN index — had been populated
on every live row since C05 and nothing queried it. C20 computed the query expansion, logged it
as `stage=expand` and nobody read the result. Both are consumed here.

The order of the pipeline is a decision and not an accident (design D10): the lexical branch
races the **embedding provider**, not the vector search. Running the two SQL statements in
parallel would optimise what costs nothing — on 1.168 rows with a GIN index the lexical query
is noise — while holding two of the five pool connections per request against a pool with
`max_overflow=0`. Racing the provider instead hides the lexical branch entirely behind a
170-1707 ms round trip and holds one connection at any moment.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.schemas.common import DebugInfo
from jbg_ai.api.schemas.retrieval import (
    RetrievalFilters,
    RetrievalMode,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
)
from jbg_ai.config.settings import Settings
from jbg_ai.indexing.constants import DEFAULT_EMBEDDING_MODEL
from jbg_ai.indexing.embeddings import EmbeddingClient, EmbedResult, LiteLlmEmbeddingClient
from jbg_ai.indexing.errors import EmbeddingError
from jbg_ai.retrieval.errors import InvalidFamilyIdError, RetrievalDependencyError
from jbg_ai.retrieval.filters import StructuralFilters, demote, extract_filters
from jbg_ai.retrieval.fusion import RankedList, fuse, normalised_scores
from jbg_ai.retrieval.lexical import EXPANDED_LIST, TYPED_LIST, expanded_request, typed_request
from jbg_ai.retrieval.ports import LexicalHit, ProductSearchPort, SearchFilters, SearchHit
from jbg_ai.retrieval.projection import (
    ProjectionFreshness,
    ProjectionScope,
    default_freshness,
    parse_pos_id,
    resolve_scope,
)
from jbg_ai.retrieval.synonyms import ExpandedQuery, expand_query
from jbg_ai.stubs.responses import over_retrieval_count

logger = logging.getLogger(__name__)

VECTOR_LIST = "vector"
LEXICAL_REASON = "lexical"
VECTOR_REASON = "vector"


def build_retrieval_embed_client(settings: Settings) -> LiteLlmEmbeddingClient:
    """Distinct from the indexer client: one attempt, so C03's 800 ms budget holds.

    Built once per process in `api/main.py` and resolved from `app.state`, with a **bounded**
    cache injected through this constructor seam — see `retrieval/cache.py`. Per request the
    unbounded cache of C11 was harmless; as a singleton it would be a lifetime leak.
    """
    from jbg_ai.retrieval.cache import BoundedEmbeddingCache

    return LiteLlmEmbeddingClient(
        api_key=settings.jpv_embedding_api_key,
        model=settings.jpv_embedding_model or DEFAULT_EMBEDDING_MODEL,
        base_url=settings.jpv_embedding_base_url,
        batch_size=settings.jpv_embedding_batch_size,
        max_attempts=1,
        cache=BoundedEmbeddingCache(),
    )


def parse_body_filters(filters: RetrievalFilters) -> SearchFilters:
    family_id: UUID | None = None
    if filters.family_id is not None:
        try:
            family_id = UUID(filters.family_id)
        except ValueError as exc:
            raise InvalidFamilyIdError(filters.family_id) from exc

    exclude: list[UUID] = []
    for raw in filters.exclude_product_ids:
        try:
            exclude.append(UUID(str(raw)))
        except (ValueError, TypeError, AttributeError):
            logger.debug("ignoring malformed exclude_product_id=%s", raw)

    materials = [item for item in filters.materials if item]
    return SearchFilters(
        materials=materials,
        category=filters.category,
        family_id=family_id,
        exclude_product_ids=exclude,
    )


def clamp_score(distance: float) -> float:
    return min(max(1.0 - distance, 0.0), 1.0)


@dataclass
class _Candidate:
    """One product, whatever produced it, plus the diagnostics of the branches that saw it."""

    product_id: UUID
    sku: str
    materials: list[str]
    family_id: UUID | None
    variant_label: str | None
    price: float | None
    size_label: str | None
    #: Read by the availability block of `demotion_rank` and never emitted. `None` means the
    #: query ran unscoped, which is not the same as a bucket of zero.
    qty_bucket: str | None = None
    vector_score: float | None = None
    lexical_score: float | None = None
    reasons: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass(frozen=True)
class _EmbedOutcome:
    result: EmbedResult | None
    error: Exception | None
    latency_ms: float


async def retrieve_products(
    payload: RetrievalRequest,
    principal: ServicePrincipal,
    *,
    settings: Settings,
    embed: EmbeddingClient,
    search: ProductSearchPort,
    expand_synonyms: bool | None = None,
    rrf_k: int | None = None,
    weight_typed: float | None = None,
    weight_expanded: float | None = None,
    weight_vector: float | None = None,
    branch_depth: int | None = None,
    pos_prefilter: bool | None = None,
    projection_max_age_seconds: int | None = None,
    freshness: ProjectionFreshness | None = None,
) -> RetrievalResponse:
    """Every configuration knob overrides the settings default for one call.

    They are parameters and not only settings because C24 sweeps configurations inside one
    process; putting them on `RetrievalRequest` instead would move the frozen `openapi.json`.
    None of them mutates `settings`.
    """
    logger.debug(
        "operator query=%s",
        payload.query,
        extra={"trace_id": principal.trace_id},
    )

    expansion_enabled = (
        settings.jpv_query_expansion_enabled if expand_synonyms is None else expand_synonyms
    )
    k = settings.jpv_rrf_k if rrf_k is None else rrf_k
    w_typed = settings.jpv_rrf_weight_typed if weight_typed is None else weight_typed
    w_expanded = settings.jpv_rrf_weight_expanded if weight_expanded is None else weight_expanded
    w_vector = settings.jpv_rrf_weight_vector if weight_vector is None else weight_vector
    depth = settings.jpv_branch_depth if branch_depth is None else branch_depth
    prefilter = (
        settings.jpv_pos_prefilter_enabled if pos_prefilter is None else pos_prefilter
    )
    max_age = (
        settings.jpv_pos_projection_max_age_seconds
        if projection_max_age_seconds is None
        else projection_max_age_seconds
    )

    run_vector = payload.mode is not RetrievalMode.LEXICAL
    run_lexical = payload.mode is not RetrievalMode.VECTOR

    expand_started = time.perf_counter()
    expanded = expand_query(payload.query, enabled=expansion_enabled)
    expand_ms = (time.perf_counter() - expand_started) * 1000
    logger.info(
        "stage=expand trace_id=%s latency_ms=%.2f enabled=%s tokens=%s matched_terms=%s "
        "consumed=%s",
        principal.trace_id,
        expand_ms,
        expansion_enabled,
        len(expanded.groups),
        len(expanded.matched),
        run_lexical,
        extra={"trace_id": principal.trace_id},
    )

    # Parsed even when the prefilter is off: a token whose point of sale cannot be read is
    # broken whatever this request intends to do with it, and finding that out only when
    # somebody enables the flag is how a mis-issued token survives to production.
    pos_id = parse_pos_id(principal.pos_id)

    filters = parse_body_filters(payload.filters)
    if run_vector:
        compatible = await search.count_compatible(
            model_version_key=embed.model_version_key,
            model_id=embed.model_id,
        )
        if compatible == 0:
            raise RetrievalDependencyError(
                "no compatible embeddings for the live model_version_key; "
                "refusing to abstain over an empty or foreign index"
            )

    scope_started = time.perf_counter()
    scope = await resolve_scope(
        pos_id,
        search=search,
        enabled=prefilter,
        max_age_seconds=max_age,
        freshness=freshness or default_freshness,
    )
    logger.info(
        "stage=projection trace_id=%s latency_ms=%.2f enabled=%s applied=%s stale=%s "
        "age_seconds=%s scope_size=%s max_age_seconds=%s",
        principal.trace_id,
        (time.perf_counter() - scope_started) * 1000,
        prefilter,
        scope.applied,
        scope.stale,
        None if scope.age_seconds is None else round(scope.age_seconds, 1),
        scope.size,
        max_age,
        extra={"trace_id": principal.trace_id},
    )
    if scope.stale:
        logger.warning(
            "stage=projection trace_id=%s degraded=unscoped age_seconds=%s max_age_seconds=%s "
            "reason=%s",
            principal.trace_id,
            None if scope.age_seconds is None else round(scope.age_seconds, 1),
            max_age,
            "never_synchronised" if scope.age_seconds is None else "stale",
            extra={"trace_id": principal.trace_id},
        )

    embedded, typed_hits, expanded_hits = await _race_provider_against_text(
        payload,
        principal,
        expanded=expanded,
        embed=embed,
        search=search,
        filters=filters,
        depth=depth,
        run_vector=run_vector,
        run_lexical=run_lexical,
        pos_id=scope.pos_id,
    )

    vector_hits: list[SearchHit] = []
    vector_ran = False
    threshold = settings.jpv_retrieval_distance_threshold
    if embedded is not None and embedded.result is not None:
        vector_ran = True
        vector_hits = await _vector_branch(
            embedded.result,
            principal,
            embed=embed,
            search=search,
            filters=filters,
            threshold=threshold,
            depth=depth,
            mode=payload.mode,
            pos_id=scope.pos_id,
        )
    elif embedded is not None and embedded.error is not None:
        if payload.mode is RetrievalMode.VECTOR or not (typed_hits or expanded_hits):
            # A 200 with an empty list would be indistinguishable from a legitimate
            # abstention, and C16's panel paints its "we found nothing" screen on exactly
            # that shape. Serving a dependency failure behind it is the lie D8 prevents.
            raise RetrievalDependencyError(str(embedded.error)) from embedded.error
        logger.warning(
            "stage=embed trace_id=%s degraded_to=lexical error=%s",
            principal.trace_id,
            embedded.error,
            extra={"trace_id": principal.trace_id},
        )

    structural = extract_filters(expanded)
    candidates, cross_branch = _fuse_branches(
        typed_hits,
        expanded_hits,
        vector_hits,
        k=k,
        depth=depth,
        weights=(w_typed, w_expanded, w_vector),
    )

    ordered, demoted = demote(candidates, structural)
    logger.info(
        "stage=filters trace_id=%s extracted=%s demoted=%s candidates=%s",
        principal.trace_id,
        structural.describe(),
        demoted,
        len(ordered),
        extra={"trace_id": principal.trace_id},
    )

    window = over_retrieval_count(payload.top_k)
    shown = ordered[:window]
    fused = run_lexical and vector_ran
    low_confidence = _low_confidence(shown, fused=fused)

    logger.info(
        "stage=fuse trace_id=%s typed=%s expanded=%s vector=%s fused=%s branches=%s "
        "cross_branch=%s returned=%s low_confidence=%s k=%s depth=%s",
        principal.trace_id,
        len(typed_hits),
        len(expanded_hits),
        len(vector_hits),
        len(candidates),
        _branches_that_ran(run_lexical=run_lexical, vector_ran=vector_ran),
        cross_branch,
        len(shown),
        low_confidence,
        k,
        depth,
        extra={"trace_id": principal.trace_id},
    )

    results = [_to_result(item, structural) for item in shown]
    return RetrievalResponse(
        results=results,
        candidates_returned=len(results),
        low_confidence=low_confidence,
        trace_id=principal.trace_id,
        effective_pos_id=principal.pos_id or "",
        projection_age_seconds=scope.reported_age,
    )


async def _race_provider_against_text(
    payload: RetrievalRequest,
    principal: ServicePrincipal,
    *,
    expanded: ExpandedQuery,
    embed: EmbeddingClient,
    search: ProductSearchPort,
    filters: SearchFilters,
    depth: int,
    run_vector: bool,
    run_lexical: bool,
    pos_id: UUID | None,
) -> tuple[_EmbedOutcome | None, list[LexicalHit], list[LexicalHit]]:
    """`gather(embed, lexical A then B)` — one pool connection held at any moment (D10)."""

    async def _embed_stage() -> _EmbedOutcome | None:
        if not run_vector:
            return None
        started = time.perf_counter()
        try:
            result = await embed.embed([payload.query])
        except EmbeddingError as exc:
            return _EmbedOutcome(None, exc, (time.perf_counter() - started) * 1000)
        latency = (time.perf_counter() - started) * 1000
        if not result.vectors:
            return _EmbedOutcome(
                None, RetrievalDependencyError("embedding provider returned no vector"), latency
            )
        logger.info(
            "stage=embed trace_id=%s latency_ms=%.1f model=%s cache_hits=%s",
            principal.trace_id,
            latency,
            result.embedding_model,
            result.cache_hits,
            extra={"trace_id": principal.trace_id},
        )
        return _EmbedOutcome(result, None, latency)

    async def _lexical_stage() -> tuple[list[LexicalHit], list[LexicalHit]]:
        if not run_lexical:
            return [], []
        started = time.perf_counter()
        # Sequential on purpose: two concurrent statements would hold two of the five pool
        # connections, and the pair costs single-digit milliseconds behind the provider.
        typed = await search.search_lexical(
            typed_request(payload.query), depth=depth, filters=filters, pos_id=pos_id
        )
        widened = await search.search_lexical(
            expanded_request(expanded), depth=depth, filters=filters, pos_id=pos_id
        )
        logger.info(
            "stage=lexical trace_id=%s latency_ms=%.1f typed=%s expanded=%s scoped=%s",
            principal.trace_id,
            (time.perf_counter() - started) * 1000,
            len(typed),
            len(widened),
            pos_id is not None,
            extra={"trace_id": principal.trace_id},
        )
        return typed, widened

    embedded, lexical = await asyncio.gather(_embed_stage(), _lexical_stage())
    typed_hits, expanded_hits = lexical
    return embedded, typed_hits, expanded_hits


async def _vector_branch(
    embedded: EmbedResult,
    principal: ServicePrincipal,
    *,
    embed: EmbeddingClient,
    search: ProductSearchPort,
    filters: SearchFilters,
    threshold: float,
    depth: int,
    mode: RetrievalMode,
    pos_id: UUID | None,
) -> list[SearchHit]:
    started = time.perf_counter()
    hits = await search.search(
        embedded.vectors[0],
        threshold=threshold,
        depth=depth,
        filters=filters,
        model_version_key=embed.model_version_key,
        model_id=embed.model_id,
        pos_id=pos_id,
    )
    hits = sorted(hits, key=lambda item: item.distance)[:depth]
    # `vector_empty` and not `low_confidence`: this stage knows only whether **its own**
    # branch returned anything, and the response-level marking is computed after the fusion.
    # The two really do diverge — a healthy vector branch whose candidates the lexical one
    # never saw logs `vector_empty=False` inside a response that *is* low confidence, because
    # nothing came from both branches. Sharing the name put two opposite values under one
    # field in a single trace, which is the kind of log that gets believed over the code.
    logger.info(
        "stage=search trace_id=%s latency_ms=%.1f distance_min=%s candidates=%s "
        "vector_empty=%s mode=%s threshold=%s scoped=%s depth=%s truncated=%s",
        principal.trace_id,
        (time.perf_counter() - started) * 1000,
        hits[0].distance if hits else None,
        len(hits),
        not hits,
        mode.value,
        threshold,
        pos_id is not None,
        depth,
        len(hits) < depth,
        extra={"trace_id": principal.trace_id},
    )
    return hits


def _fuse_branches(
    typed_hits: list[LexicalHit],
    expanded_hits: list[LexicalHit],
    vector_hits: list[SearchHit],
    *,
    k: int,
    depth: int,
    weights: tuple[float, float, float],
) -> tuple[list[_Candidate], int]:
    """Fuse the three lists and rebuild the candidates with their real provenance."""
    w_typed, w_expanded, w_vector = weights
    candidates: dict[UUID, _Candidate] = {}

    for hit in (*typed_hits, *expanded_hits):
        item = candidates.get(hit.product_id) or _from_hit(hit)
        item.lexical_score = max(item.lexical_score or 0.0, hit.ts_rank)
        candidates[hit.product_id] = item

    for hit in vector_hits:
        item = candidates.get(hit.product_id) or _from_hit(hit)
        item.vector_score = clamp_score(hit.distance)
        candidates[hit.product_id] = item

    fused = fuse(
        [
            RankedList(TYPED_LIST, w_typed, [hit.product_id for hit in typed_hits]),
            RankedList(EXPANDED_LIST, w_expanded, [hit.product_id for hit in expanded_hits]),
            RankedList(VECTOR_LIST, w_vector, [hit.product_id for hit in vector_hits]),
        ],
        k=k,
        depth=depth,
    )
    scores = normalised_scores(fused)

    ordered: list[_Candidate] = []
    cross_branch = 0
    for entry, score in zip(fused, scores, strict=True):
        item = candidates[entry.key]  # type: ignore[index]
        item.score = score
        reasons: list[str] = []
        if VECTOR_LIST in entry.ranks:
            reasons.append(VECTOR_REASON)
        if TYPED_LIST in entry.ranks or EXPANDED_LIST in entry.ranks:
            reasons.append(LEXICAL_REASON)
        item.reasons = reasons
        # A candidate seen by both lexical lists is not cross-branch: with the expansion
        # disabled the two lists are identical, and every lexical hit would qualify.
        if len(reasons) > 1:
            cross_branch += 1
        # A diagnostic is absent rather than invented for a branch that did not see it.
        if VECTOR_REASON not in reasons:
            item.vector_score = None
        if LEXICAL_REASON not in reasons:
            item.lexical_score = None
        ordered.append(item)

    return ordered, cross_branch


def _from_hit(hit: LexicalHit | SearchHit) -> _Candidate:
    """One candidate from whichever branch saw it first. Every branch reports the bucket."""
    return _Candidate(
        product_id=hit.product_id,
        sku=hit.sku,
        materials=list(hit.materials),
        family_id=hit.family_id,
        variant_label=hit.variant_label,
        price=hit.price,
        size_label=hit.size_label,
        qty_bucket=hit.qty_bucket,
    )


def _branches_that_ran(*, run_lexical: bool, vector_ran: bool) -> str:
    names = [
        name
        for name, ran in ((LEXICAL_REASON, run_lexical), (VECTOR_REASON, vector_ran))
        if ran
    ]
    return "+".join(names) if names else "none"


def _low_confidence(shown: Sequence[_Candidate], *, fused: bool) -> bool:
    """Absence of cross-branch consensus — but only where there were branches to disagree.

    With two branches running, the signal is the one D9 defines: no returned candidate was
    produced by more than one of them, which is the exact signature of the measured failure
    where the vector branch answered *pulsera* and the lexical one the three *sortijas* with
    zero overlap. It stays a signal: it never changes how many candidates are returned.

    With **one** branch — `mode=lexical`, `mode=vector`, or a `hybrid` request whose embedding
    provider failed and degraded — no candidate can ever appear twice, so that rule would mark
    every response low confidence and the field would carry no information at all. There it
    keeps the C14 meaning instead: the retriever returned nothing. Reporting a permanent true
    would be the same kind of lie as the `["vector"]` constant this change removed.
    """
    if not fused:
        return not shown
    return not any(len(item.reasons) > 1 for item in shown)


def _to_result(item: _Candidate, structural: StructuralFilters) -> RetrievalResult:
    notes: list[str] = []
    if not structural.is_empty:
        notes.append(f"structural_filters:{structural.describe()}")
    return RetrievalResult(
        product_id=str(item.product_id),
        sku=item.sku,
        score=item.score,
        match_reasons=list(item.reasons),
        materials=list(item.materials),
        family_id=str(item.family_id) if item.family_id is not None else None,
        variant_label=item.variant_label,
        debug=DebugInfo(
            vector_score=item.vector_score,
            lexical_score=item.lexical_score,
            rerank_score=None,
            notes=notes,
        ),
    )
