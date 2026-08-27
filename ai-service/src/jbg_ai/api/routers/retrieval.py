"""Retrieval routes. Products are real when stub mode is off (C14); substitutes stay C26."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

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
from jbg_ai.db.engine import DatabaseNotConfiguredError
from jbg_ai.indexing.embeddings import EmbeddingClient
from jbg_ai.retrieval.errors import InvalidFamilyIdError, RetrievalDependencyError
from jbg_ai.retrieval.orchestrator import (
    build_retrieval_embed_client,
    retrieve_products as run_product_retrieval,
)
from jbg_ai.retrieval.ports import ProductSearchPort
from jbg_ai.retrieval.search import SqlAlchemyProductSearch
from jbg_ai.stubs import retrieval_products_stub, retrieval_substitutes_stub

SUBSTITUTES_DELIVERED_BY = "C26 (add-substitutes-retrieval)"

router = APIRouter(prefix="/v1/retrieval", tags=["retrieval"], responses=V1_RESPONSES)


def _missing(setting: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"{setting} is required when STUB_MODE is false",
    )


def _require_real_retrieval_settings(request: Request, settings: Settings) -> None:
    injected_embed = getattr(request.app.state, "retrieval_embed", None)
    injected_search = getattr(request.app.state, "retrieval_search", None)
    if injected_embed is None and not settings.jpv_embedding_api_key:
        raise _missing("JPV_EMBEDDING_API_KEY")
    if injected_search is None and not settings.database_url:
        raise _missing("DATABASE_URL")


def _resolve_embed(request: Request, settings: Settings) -> EmbeddingClient:
    injected = getattr(request.app.state, "retrieval_embed", None)
    if injected is not None:
        return injected  # type: ignore[no-any-return]
    return build_retrieval_embed_client(settings)


def _resolve_search(request: Request, settings: Settings) -> ProductSearchPort:
    injected = getattr(request.app.state, "retrieval_search", None)
    if injected is not None:
        return injected  # type: ignore[no-any-return]
    return SqlAlchemyProductSearch(settings)


@router.post(
    "/products",
    response_model=RetrievalResponse,
    summary="Retrieve catalog candidates for a query",
)
async def retrieve_products(
    payload: RetrievalRequest,
    request: Request,
    principal: ServicePrincipal = Depends(get_service_principal),
    settings: Settings = Depends(get_app_settings),
) -> RetrievalResponse:
    """Over-fetch candidates so .NET can filter and still fill a page of `top_k`.

    `payload.pos_id` is ignored on purpose: the scope comes from the token.
    """
    if settings.stub_mode:
        return retrieval_products_stub(payload, principal)

    _require_real_retrieval_settings(request, settings)
    try:
        return await run_product_retrieval(
            payload,
            principal,
            settings=settings,
            embed=_resolve_embed(request, settings),
            search=_resolve_search(request, settings),
        )
    except InvalidFamilyIdError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except DatabaseNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except RetrievalDependencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


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
