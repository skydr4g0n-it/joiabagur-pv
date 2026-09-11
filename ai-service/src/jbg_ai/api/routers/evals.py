"""Evaluation routes — mounted only when development endpoints are enabled.

Under a production profile the router is never registered, so the path does not exist at all
instead of answering a misleading documented 404.

**This route is no longer a placeholder.** Its stub named C24 in writing as the change that
would fill it, and C24 fills it: with stubs off it serves the runs the harness persisted, most
recent first. What it does NOT do is move the contract — the request and response models are
untouched, so the committed OpenAPI snapshot stays byte for byte identical, and the harness
writes those rows only when persistence is explicitly asked for.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.deps import (
    V1_RESPONSES,
    get_app_settings,
    get_service_principal,
)
from jbg_ai.api.schemas.evals import EvalMetric, EvalRun, EvalRunsResponse
from jbg_ai.config import Settings
from jbg_ai.db.engine import DatabaseNotConfiguredError
from jbg_ai.stubs import evals_runs_stub

#: How many runs the route returns. An ablation table is five rows and a history of a few
#: revisions; anything past this is an archive question, not a development-endpoint one.
RUN_LIMIT = 50

router = APIRouter(prefix="/v1/evals", tags=["evals"], responses=V1_RESPONSES)


@router.get(
    "/runs",
    response_model=EvalRunsResponse,
    summary="List evaluation runs (development profile only)",
)
async def list_eval_runs(
    principal: ServicePrincipal = Depends(get_service_principal),
    settings: Settings = Depends(get_app_settings),
) -> EvalRunsResponse:
    if settings.stub_mode:
        return evals_runs_stub(principal)

    from jbg_ai.evals.repository import read_runs

    if not settings.database_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL is required when STUB_MODE is false",
        )
    try:
        rows = await read_runs(settings=settings, limit=RUN_LIMIT)
    except DatabaseNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return EvalRunsResponse(
        runs=[
            EvalRun(
                run_id=row["run_id"],
                suite=row["suite"],
                status=row["status"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                metrics=[EvalMetric(**metric) for metric in row["metrics"]],
            )
            for row in rows
        ],
        trace_id=principal.trace_id,
    )
