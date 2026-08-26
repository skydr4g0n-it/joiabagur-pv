"""Index synchronisation routes. Real catalog drain when stub mode is off (C13)."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.deps import (
    V1_RESPONSES,
    get_app_settings,
    get_catalog_principal,
)
from jbg_ai.api.schemas.index import IndexStatusResponse, IndexSyncRequest, IndexSyncResponse
from jbg_ai.config import Settings
from jbg_ai.indexing.constants import DEFAULT_EMBEDDING_MODEL
from jbg_ai.indexing.embeddings import LiteLlmEmbeddingClient
from jbg_ai.indexing.feed import FEED_TIMEOUT_SECONDS, HttpxIndexFeedClient, IndexFeedClient
from jbg_ai.indexing.orchestrator import (
    CatalogSyncRequest,
    report_index_status,
    sync_catalog,
)
from jbg_ai.indexing.provenance import load_provenance_map
from jbg_ai.indexing.repository import ProductDocumentRepo, SqlAlchemyProductDocumentRepo
from jbg_ai.indexing.sync_errors import IndexFeedConfigError, ProvenanceMapError
from jbg_ai.stubs import index_status_stub, index_sync_stub

INDEX_RESPONSES: dict[int | str, dict[str, Any]] = {
    **V1_RESPONSES,
    503: {
        "description": (
            "Catalog sync cannot run: missing JPV_INDEX_FEED_BASE_URL, "
            "JPV_INDEX_FEED_API_KEY, JPV_EMBEDDING_API_KEY, sku_provenance.json, "
            "or the catalog feed did not respond"
        )
    },
}

router = APIRouter(prefix="/v1/index", tags=["index"], responses=INDEX_RESPONSES)


def _missing(setting: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"{setting} is required when STUB_MODE is false",
    )


def _require_real_sync_settings(request: Request, settings: Settings) -> None:
    injected_feed = getattr(request.app.state, "index_feed", None)
    injected_embed = getattr(request.app.state, "index_embed", None)
    injected_map = getattr(request.app.state, "index_provenance", None)
    if injected_feed is None:
        if not settings.jpv_index_feed_base_url:
            raise _missing("JPV_INDEX_FEED_BASE_URL")
        if not settings.jpv_index_feed_api_key:
            raise _missing("JPV_INDEX_FEED_API_KEY")
    if injected_embed is None and not settings.jpv_embedding_api_key:
        raise _missing("JPV_EMBEDDING_API_KEY")
    if injected_map is None:
        try:
            load_provenance_map()
        except ProvenanceMapError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="sku_provenance.json is missing; refusing catalog sync",
            ) from None


async def _run_with_ports(
    request: Request,
    settings: Settings,
    runner,
):
    injected_feed = getattr(request.app.state, "index_feed", None)
    injected_embed = getattr(request.app.state, "index_embed", None)
    injected_repo = getattr(request.app.state, "index_repo", None)
    injected_map = getattr(request.app.state, "index_provenance", None)
    provenance = injected_map if injected_map is not None else load_provenance_map()
    repo: ProductDocumentRepo = injected_repo or SqlAlchemyProductDocumentRepo(settings)
    embed = injected_embed or LiteLlmEmbeddingClient(
        api_key=settings.jpv_embedding_api_key,
        model=settings.jpv_embedding_model or DEFAULT_EMBEDDING_MODEL,
        base_url=settings.jpv_embedding_base_url,
        batch_size=settings.jpv_embedding_batch_size,
    )
    if injected_feed is not None:
        return await runner(injected_feed, embed, repo, provenance)
    async with httpx.AsyncClient(
        base_url=settings.jpv_index_feed_base_url.rstrip("/"),  # type: ignore[union-attr]
        timeout=FEED_TIMEOUT_SECONDS,
    ) as client:
        feed: IndexFeedClient = HttpxIndexFeedClient(
            client, settings.jpv_index_feed_api_key or ""
        )
        return await runner(feed, embed, repo, provenance)


@router.post(
    "/sync",
    response_model=IndexSyncResponse,
    summary="Synchronise the vector index from a cursor",
    responses=INDEX_RESPONSES,
)
async def sync_index(
    payload: IndexSyncRequest,
    request: Request,
    principal: ServicePrincipal = Depends(get_catalog_principal),
    settings: Settings = Depends(get_app_settings),
) -> IndexSyncResponse:
    if settings.stub_mode:
        return index_sync_stub(payload, principal)
    _require_real_sync_settings(request, settings)

    async def _run(feed, embed, repo, provenance):
        return await sync_catalog(
            CatalogSyncRequest(
                full=payload.full,
                since=payload.since,
                since_id=payload.since_id,
                batch_size=payload.batch_size,
            ),
            feed=feed,
            embed=embed,
            repo=repo,
            provenance_map=provenance,
            time_budget_seconds=settings.jpv_index_sync_time_budget_seconds,
        )

    try:
        result = await _run_with_ports(request, settings, _run)
    except ProvenanceMapError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="sku_provenance.json is missing; refusing catalog sync",
        ) from None
    except IndexFeedConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None
    return IndexSyncResponse(
        upserted=result.upserted,
        skipped=result.skipped,
        deleted=result.deleted,
        failed=result.failed,
        since=result.since,
        since_id=result.since_id,
        cursor=result.cursor,
        cursor_id=result.cursor_id,
        trace_id=principal.trace_id,
    )


@router.get(
    "/status",
    response_model=IndexStatusResponse,
    summary="Report index size and drift",
    responses=INDEX_RESPONSES,
)
async def index_status(
    request: Request,
    principal: ServicePrincipal = Depends(get_catalog_principal),
    settings: Settings = Depends(get_app_settings),
) -> IndexStatusResponse:
    if settings.stub_mode:
        return index_status_stub(principal)
    _require_real_sync_settings(request, settings)

    async def _run(feed, embed, repo, provenance):
        _ = embed, provenance
        return await report_index_status(feed=feed, repo=repo)

    try:
        result = await _run_with_ports(request, settings, _run)
    except IndexFeedConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None
    return IndexStatusResponse(
        indexed_documents=result.indexed_documents,
        drift_count=result.drift_count,
        last_full_sync_at=result.last_full_sync_at,
        last_incremental_sync_at=result.last_incremental_sync_at,
        trace_id=principal.trace_id,
    )
