"""Sale assistance routes. Real when stub mode is off since C30a; the fixture survives it.

`DELIVERED_BY` went with the 501, exactly as `SUBSTITUTES_DELIVERED_BY` did when C26 served
its route: a constant announcing a future delivery, left behind on a route that answers, is
a lie the next reader has to disprove. Checked by search before removing it, not by memory.

**The prose is still absent, and that is the shape of the change rather than an omission.**
`pitch` is empty, `prompt_version` null and `usage` zero until C30b, which is what makes
C30b measurable: same route, same candidates, same citations, with an argument and without.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.deps import (
    V1_RESPONSES,
    get_app_settings,
    get_service_principal,
)
from jbg_ai.api.schemas.assist import AssistRequest, AssistResponse
from jbg_ai.assist.errors import NoAnchorError, UnusableAnchorProductError
from jbg_ai.assist.orchestrator import assist_sale as run_assist_sale
from jbg_ai.config import Settings
from jbg_ai.db.engine import DatabaseNotConfiguredError
from jbg_ai.indexing.embeddings import EmbeddingClient
from jbg_ai.knowledge.errors import KnowledgeSearchError
from jbg_ai.knowledge.search import KnowledgeSearchIndex, SqlAlchemyKnowledgeIndex
from jbg_ai.retrieval.errors import (
    InvalidFamilyIdError,
    InvalidPosIdError,
    RetrievalDependencyError,
)
from jbg_ai.retrieval.orchestrator import build_retrieval_embed_client
from jbg_ai.retrieval.ports import ProductSearchPort
from jbg_ai.retrieval.search import SqlAlchemyProductSearch
from jbg_ai.stubs import assist_sale_stub

router = APIRouter(prefix="/v1/assist", tags=["assist"], responses=V1_RESPONSES)


def _missing(setting: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"{setting} is required when STUB_MODE is false",
    )


def _require_real_settings(request: Request, settings: Settings) -> None:
    injected_embed = getattr(request.app.state, "retrieval_embed", None)
    injected_search = getattr(request.app.state, "retrieval_search", None)
    if injected_embed is None and not settings.jpv_embedding_api_key:
        raise _missing("JPV_EMBEDDING_API_KEY")
    if injected_search is None and not settings.database_url:
        raise _missing("DATABASE_URL")


def _resolve_embed(request: Request, settings: Settings) -> EmbeddingClient:
    """The SAME singleton the retrieval route resolves, and sharing it is the point.

    Measured: the client's bounded cache is keyed on a hash of the text plus the model and
    version, and both paths compose an identical `model_version_key`. So a piece-and-question
    request that embeds its question for the retrieval finds that vector already cached when
    the knowledge search asks for it — **one provider call, not two** — provided both are
    handed the same stripped text, which `assist_sale` guarantees.
    """
    injected = getattr(request.app.state, "retrieval_embed", None)
    if injected is not None:
        return injected  # type: ignore[no-any-return]
    client = build_retrieval_embed_client(settings)
    request.app.state.retrieval_embed = client
    return client


def _resolve_search(request: Request, settings: Settings) -> ProductSearchPort:
    injected = getattr(request.app.state, "retrieval_search", None)
    if injected is not None:
        return injected  # type: ignore[no-any-return]
    return SqlAlchemyProductSearch(settings)


def _resolve_knowledge(request: Request, settings: Settings) -> KnowledgeSearchIndex:
    injected = getattr(request.app.state, "knowledge_index", None)
    if injected is not None:
        return injected  # type: ignore[no-any-return]
    return SqlAlchemyKnowledgeIndex(settings)


@router.post(
    "/sale",
    response_model=AssistResponse,
    summary="Assist a sale with family-grouped candidates and a pitch",
)
async def assist_sale(
    payload: AssistRequest,
    request: Request,
    principal: ServicePrincipal = Depends(get_service_principal),
    settings: Settings = Depends(get_app_settings),
) -> AssistResponse:
    """Group candidates by family; the pitch keeps price and stock as placeholders."""
    if settings.stub_mode:
        return assist_sale_stub(payload, principal)

    _require_real_settings(request, settings)
    try:
        return await run_assist_sale(
            payload,
            principal,
            settings=settings,
            embed=_resolve_embed(request, settings),
            search=_resolve_search(request, settings),
            knowledge=_resolve_knowledge(request, settings),
        )
    except UnusableAnchorProductError as exc:
        # 422 and not 404, like the substitutes route: the body named something this service
        # cannot process. Never a 200 with `abstained` set — that would claim the catalogue
        # has no answer when what is broken is the piece.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NoAnchorError as exc:
        # Unreachable through HTTP — the request model rejects it first — and kept because
        # the layer is also a callable and the two paths must answer the same way.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidFamilyIdError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidPosIdError as exc:
        # A token whose point of sale cannot be read is a mis-issued token. The retrieval
        # routes refuse it for the same reason and must not be contradicted here.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatabaseNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except (RetrievalDependencyError, KnowledgeSearchError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
