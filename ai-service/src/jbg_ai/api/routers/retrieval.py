"""Retrieval routes. Real vector search arrives in C14 / C26."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.deps import (
    V1_RESPONSES,
    get_app_settings,
    get_service_principal,
    require_stub_mode,
)
from jbg_ai.api.schemas.retrieval import (
    RetrievalRequest,
    RetrievalResponse,
    SubstitutesRequest,
    SubstitutesResponse,
)
from jbg_ai.config import Settings
from jbg_ai.stubs import retrieval_products_stub, retrieval_substitutes_stub

PRODUCTS_DELIVERED_BY = "C14 (add-vector-retrieval-endpoint)"
SUBSTITUTES_DELIVERED_BY = "C26 (add-substitutes-retrieval)"

router = APIRouter(prefix="/v1/retrieval", tags=["retrieval"], responses=V1_RESPONSES)


@router.post(
    "/products",
    response_model=RetrievalResponse,
    summary="Retrieve catalog candidates for a query",
)
def retrieve_products(
    payload: RetrievalRequest,
    principal: ServicePrincipal = Depends(get_service_principal),
    settings: Settings = Depends(get_app_settings),
) -> RetrievalResponse:
    """Over-fetch candidates so .NET can filter and still fill a page of `top_k`.

    `payload.pos_id` is ignored on purpose: the scope comes from the token.
    """
    require_stub_mode(settings, PRODUCTS_DELIVERED_BY)
    return retrieval_products_stub(payload, principal)


@router.post(
    "/substitutes",
    response_model=SubstitutesResponse,
    summary="Retrieve interchangeable products for a reference product",
)
def retrieve_substitutes(
    payload: SubstitutesRequest,
    principal: ServicePrincipal = Depends(get_service_principal),
    settings: Settings = Depends(get_app_settings),
) -> SubstitutesResponse:
    require_stub_mode(settings, SUBSTITUTES_DELIVERED_BY)
    return retrieval_substitutes_stub(payload, principal)
