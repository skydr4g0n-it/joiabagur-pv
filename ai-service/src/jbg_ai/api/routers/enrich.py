"""Catalog enrichment routes. Real enrichment arrives in C09."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.deps import (
    V1_RESPONSES,
    get_app_settings,
    get_catalog_principal,
    require_stub_mode,
)
from jbg_ai.api.schemas.enrich import EnrichRequest, EnrichResponse
from jbg_ai.config import Settings
from jbg_ai.stubs import enrich_products_stub

DELIVERED_BY = "C09 (add-catalog-enrichment-pipeline)"

router = APIRouter(prefix="/v1/enrich", tags=["enrich"], responses=V1_RESPONSES)


@router.post(
    "/products",
    response_model=EnrichResponse,
    summary="Propose enriched profiles for a batch of products",
)
def enrich_products(
    payload: EnrichRequest,
    principal: ServicePrincipal = Depends(get_catalog_principal),
    settings: Settings = Depends(get_app_settings),
) -> EnrichResponse:
    """Every proposed field carries its own confidence and provenance; nothing is written.

    Catalog-scoped: enriching the catalog belongs to no point of sale, so this
    route accepts a token without `pos_id`. Retrieval, assistance and inventory
    keep requiring one.
    """
    require_stub_mode(settings, DELIVERED_BY)
    return enrich_products_stub(payload, principal)
