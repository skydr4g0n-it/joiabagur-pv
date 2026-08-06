"""Evaluation routes — mounted only when development endpoints are enabled.

Under a production profile the router is never registered, so the path does not
exist at all instead of answering a misleading documented 404. Real eval runs
arrive in C24.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.deps import (
    V1_RESPONSES,
    get_app_settings,
    get_service_principal,
    require_stub_mode,
)
from jbg_ai.api.schemas.evals import EvalRunsResponse
from jbg_ai.config import Settings
from jbg_ai.stubs import evals_runs_stub

DELIVERED_BY = "C24 (add-eval-harness-golden-set-and-baselines)"

router = APIRouter(prefix="/v1/evals", tags=["evals"], responses=V1_RESPONSES)


@router.get(
    "/runs",
    response_model=EvalRunsResponse,
    summary="List evaluation runs (development profile only)",
)
def list_eval_runs(
    principal: ServicePrincipal = Depends(get_service_principal),
    settings: Settings = Depends(get_app_settings),
) -> EvalRunsResponse:
    require_stub_mode(settings, DELIVERED_BY)
    return evals_runs_stub(principal)
