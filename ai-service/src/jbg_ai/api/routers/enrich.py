"""Catalog enrichment routes. Real pipeline when stub mode is off (C09)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.deps import (
    V1_RESPONSES,
    get_app_settings,
    get_catalog_principal,
)
from jbg_ai.api.schemas.enrich import EnrichRequest, EnrichResponse
from jbg_ai.config import Settings
from jbg_ai.enrichment.constants import DEFAULT_RAG_LLM_MODEL
from jbg_ai.enrichment.errors import EnrichConfigError
from jbg_ai.enrichment.llm import EnrichLlm, LiteLlmEnrichClient
from jbg_ai.enrichment.pipeline import enrich_products as run_enrichment
from jbg_ai.stubs import enrich_products_stub

router = APIRouter(prefix="/v1/enrich", tags=["enrich"], responses=V1_RESPONSES)

MISSING_RAG_KEY_DETAIL = (
    "JPV_RAG_LLM_API_KEY is required when STUB_MODE is false; "
    "refusing to invent enrichment profiles"
)


def build_enrich_llm(settings: Settings) -> EnrichLlm:
    if not settings.jpv_rag_llm_api_key:
        raise EnrichConfigError(MISSING_RAG_KEY_DETAIL)
    return LiteLlmEnrichClient(
        api_key=settings.jpv_rag_llm_api_key,
        model=settings.jpv_rag_llm_model or DEFAULT_RAG_LLM_MODEL,
        base_url=settings.jpv_rag_llm_base_url,
    )


def _resolve_enrich_llm(request: Request, settings: Settings) -> EnrichLlm:
    injected = getattr(request.app.state, "enrich_llm", None)
    if injected is not None:
        return injected  # type: ignore[no-any-return]
    return build_enrich_llm(settings)


@router.post(
    "/products",
    response_model=EnrichResponse,
    summary="Propose enriched profiles for a batch of products",
)
async def enrich_products(
    payload: EnrichRequest,
    request: Request,
    principal: ServicePrincipal = Depends(get_catalog_principal),
    settings: Settings = Depends(get_app_settings),
) -> EnrichResponse:
    """Every proposed field carries its own confidence and provenance; nothing is written.

    Catalog-scoped: enriching the catalog belongs to no point of sale, so this
    route accepts a token without `pos_id`. Retrieval, assistance and inventory
    keep requiring one.
    """
    if settings.stub_mode:
        return enrich_products_stub(payload, principal)
    if not settings.jpv_rag_llm_api_key and getattr(request.app.state, "enrich_llm", None) is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=MISSING_RAG_KEY_DETAIL,
        )
    llm = _resolve_enrich_llm(request, settings)
    return await run_enrichment(payload, principal, settings, llm)
