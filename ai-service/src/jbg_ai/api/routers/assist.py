"""Sale assistance routes. Real generation arrives in C30."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.deps import (
    V1_RESPONSES,
    get_app_settings,
    get_service_principal,
    require_stub_mode,
)
from jbg_ai.api.schemas.assist import AssistRequest, AssistResponse
from jbg_ai.config import Settings
from jbg_ai.stubs import assist_sale_stub

DELIVERED_BY = "C30 (add-assist-generation-with-rule-warnings)"

router = APIRouter(prefix="/v1/assist", tags=["assist"], responses=V1_RESPONSES)


@router.post(
    "/sale",
    response_model=AssistResponse,
    summary="Assist a sale with family-grouped candidates and a pitch",
)
def assist_sale(
    payload: AssistRequest,
    principal: ServicePrincipal = Depends(get_service_principal),
    settings: Settings = Depends(get_app_settings),
) -> AssistResponse:
    """Group candidates by family; the pitch keeps price and stock as placeholders."""
    require_stub_mode(settings, DELIVERED_BY)
    return assist_sale_stub(payload, principal)
