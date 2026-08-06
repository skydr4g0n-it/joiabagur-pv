"""Index synchronisation routes. Real indexing arrives in C13."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.deps import (
    V1_RESPONSES,
    get_app_settings,
    get_service_principal,
    require_stub_mode,
)
from jbg_ai.api.schemas.index import IndexStatusResponse, IndexSyncRequest, IndexSyncResponse
from jbg_ai.config import Settings
from jbg_ai.stubs import index_status_stub, index_sync_stub

DELIVERED_BY = "C13 (add-product-document-indexer)"

router = APIRouter(prefix="/v1/index", tags=["index"], responses=V1_RESPONSES)


@router.post(
    "/sync",
    response_model=IndexSyncResponse,
    summary="Synchronise the vector index from a cursor",
)
def sync_index(
    payload: IndexSyncRequest,
    principal: ServicePrincipal = Depends(get_service_principal),
    settings: Settings = Depends(get_app_settings),
) -> IndexSyncResponse:
    require_stub_mode(settings, DELIVERED_BY)
    return index_sync_stub(payload, principal)


@router.get(
    "/status",
    response_model=IndexStatusResponse,
    summary="Report index size and drift",
)
def index_status(
    principal: ServicePrincipal = Depends(get_service_principal),
    settings: Settings = Depends(get_app_settings),
) -> IndexStatusResponse:
    require_stub_mode(settings, DELIVERED_BY)
    return index_status_stub(principal)
