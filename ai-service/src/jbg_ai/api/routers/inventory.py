"""Inventory proposal routes. Real proposals arrive in C35."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.deps import (
    V1_RESPONSES,
    get_app_settings,
    get_service_principal,
    require_stub_mode,
)
from jbg_ai.api.schemas.inventory import InventoryProposeRequest, InventoryProposeResponse
from jbg_ai.config import Settings
from jbg_ai.stubs import inventory_propose_stub

DELIVERED_BY = "C35 (add-inventory-agent-proposals)"

router = APIRouter(prefix="/v1/inventory", tags=["inventory"], responses=V1_RESPONSES)


@router.post(
    "/propose",
    response_model=InventoryProposeResponse,
    summary="Propose what deserves inventory attention, in priority order",
)
def propose_inventory(
    payload: InventoryProposeRequest,
    principal: ServicePrincipal = Depends(get_service_principal),
    settings: Settings = Depends(get_app_settings),
) -> InventoryProposeResponse:
    """Proposals carry priority and rationale; .NET decides quantities."""
    require_stub_mode(settings, DELIVERED_BY)
    return inventory_propose_stub(payload, principal)
