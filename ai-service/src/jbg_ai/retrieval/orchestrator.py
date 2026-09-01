"""Embed the query, search by cosine, map scores. Delivered by C14.

C20 adds the synonym expansion stage. Its result is computed and logged but not
consumed: the lexical branch that reads it arrives with C21, and until then the
response of this endpoint is unchanged. That is declared rather than disguised.
"""

from __future__ import annotations

import logging
import time
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
from jbg_ai.indexing.embeddings import EmbeddingClient, LiteLlmEmbeddingClient
from jbg_ai.indexing.errors import EmbeddingError
from jbg_ai.retrieval.errors import InvalidFamilyIdError, RetrievalDependencyError
from jbg_ai.retrieval.ports import ProductSearchPort, SearchFilters, SearchHit
from jbg_ai.retrieval.synonyms import expand_query
from jbg_ai.stubs.responses import over_retrieval_count

logger = logging.getLogger(__name__)

VECTOR_UNTIL_C21_NOTE = "vector_only_until_c21"


def build_retrieval_embed_client(settings: Settings) -> LiteLlmEmbeddingClient:
    """Distinct from the indexer client: one attempt, so C03's 800 ms budget holds."""
    return LiteLlmEmbeddingClient(
        api_key=settings.jpv_embedding_api_key,
        model=settings.jpv_embedding_model or DEFAULT_EMBEDDING_MODEL,
        base_url=settings.jpv_embedding_base_url,
        batch_size=settings.jpv_embedding_batch_size,
        max_attempts=1,
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


def _hit_to_result(hit: SearchHit, *, mode: RetrievalMode) -> RetrievalResult:
    score = clamp_score(hit.distance)
    notes: list[str] = []
    if mode in (RetrievalMode.HYBRID, RetrievalMode.LEXICAL):
        notes.append(VECTOR_UNTIL_C21_NOTE)
    return RetrievalResult(
        product_id=str(hit.product_id),
        sku=hit.sku,
        score=score,
        match_reasons=["vector"],
        materials=list(hit.materials),
        family_id=str(hit.family_id) if hit.family_id is not None else None,
        variant_label=hit.variant_label,
        debug=DebugInfo(
            vector_score=score,
            lexical_score=None,
            rerank_score=None,
            notes=notes,
        ),
    )


async def retrieve_products(
    payload: RetrievalRequest,
    principal: ServicePrincipal,
    *,
    settings: Settings,
    embed: EmbeddingClient,
    search: ProductSearchPort,
    expand_synonyms: bool | None = None,
) -> RetrievalResponse:
    """`expand_synonyms` overrides the settings default for one call.

    It is a parameter and not only a setting because C24 sweeps configurations inside
    one process; putting it on `RetrievalRequest` instead would move the frozen
    `openapi.json`.
    """
    logger.debug(
        "operator query=%s",
        payload.query,
        extra={"trace_id": principal.trace_id},
    )

    expansion_enabled = (
        settings.jpv_query_expansion_enabled if expand_synonyms is None else expand_synonyms
    )
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
        False,
        extra={"trace_id": principal.trace_id},
    )

    filters = parse_body_filters(payload.filters)
    compatible = await search.count_compatible(
        model_version_key=embed.model_version_key,
        model_id=embed.model_id,
    )
    if compatible == 0:
        raise RetrievalDependencyError(
            "no compatible embeddings for the live model_version_key; "
            "refusing to abstain over an empty or foreign index"
        )

    # The ORIGINAL query, never an expanded form: expansion feeds the lexical branch
    # only. Embedding a variant too would double the provider round trips on a client
    # still built per request, against a budget already raised to 2500 ms in C16.
    embed_started = time.perf_counter()
    try:
        embedded = await embed.embed([payload.query])
    except EmbeddingError as exc:
        raise RetrievalDependencyError(str(exc)) from exc
    embed_ms = (time.perf_counter() - embed_started) * 1000
    logger.info(
        "stage=embed trace_id=%s latency_ms=%.1f model=%s cache_hits=%s",
        principal.trace_id,
        embed_ms,
        embedded.embedding_model,
        embedded.cache_hits,
        extra={"trace_id": principal.trace_id},
    )
    if not embedded.vectors:
        raise RetrievalDependencyError("embedding provider returned no vector")
    query_vec = embedded.vectors[0]

    overfetch = over_retrieval_count(payload.top_k)
    threshold = settings.jpv_retrieval_distance_threshold
    search_started = time.perf_counter()
    hits = await search.search(
        query_vec,
        threshold=threshold,
        overfetch=overfetch,
        filters=filters,
        model_version_key=embed.model_version_key,
        model_id=embed.model_id,
    )
    hits = sorted(hits, key=lambda item: item.distance)[:overfetch]
    search_ms = (time.perf_counter() - search_started) * 1000

    results = [_hit_to_result(hit, mode=payload.mode) for hit in hits]
    low_confidence = len(results) == 0
    distance_min: float | None = hits[0].distance if hits else None
    logger.info(
        "stage=search trace_id=%s latency_ms=%.1f distance_min=%s candidates=%s "
        "low_confidence=%s mode=%s threshold=%s",
        principal.trace_id,
        search_ms,
        distance_min,
        len(results),
        low_confidence,
        payload.mode.value,
        threshold,
        extra={"trace_id": principal.trace_id},
    )

    return RetrievalResponse(
        results=results,
        candidates_returned=len(results),
        low_confidence=low_confidence,
        trace_id=principal.trace_id,
        effective_pos_id=principal.pos_id or "",
    )
