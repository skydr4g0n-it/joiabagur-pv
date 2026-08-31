"""Family suggestion route. Delivered by C18a — the ninth `/v1` path.

Adding it moves the frozen contract deliberately: `openapi.json` is regenerated in
the same change, and `test_openapi_snapshot_is_stable` goes green against the new
snapshot. The drift test exists to make a boundary move visible, not to prevent one.

The route proposes and never writes. Applying an accepted subset belongs to .NET,
whose family service is the only path that stamps `Product.UpdatedAt` on entering
products — the watermark an incremental index pull depends on.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.deps import V1_RESPONSES, get_app_settings, get_catalog_principal
from jbg_ai.api.schemas.families import (
    FamilyAuditRequest,
    FamilyAuditResponse,
    FamilySuggestRequest,
    FamilySuggestResponse,
)
from jbg_ai.config import Settings
from jbg_ai.db.engine import DatabaseNotConfiguredError
from jbg_ai.families.audit import audit_families
from jbg_ai.families.errors import FamilyDependencyError, InvalidPieceTypeError
from jbg_ai.families.orchestrator import suggest_families
from jbg_ai.stubs import families_audit_stub, families_suggest_stub

router = APIRouter(prefix="/v1/families", tags=["families"], responses=V1_RESPONSES)


def _missing(setting: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"{setting} is required when STUB_MODE is false",
    )


@router.post(
    "/suggest",
    response_model=FamilySuggestResponse,
    summary="Propose product families, and report what was refused",
)
async def suggest(
    payload: FamilySuggestRequest,
    request: Request,
    principal: ServicePrincipal = Depends(get_catalog_principal),
    settings: Settings = Depends(get_app_settings),
) -> FamilySuggestResponse:
    """Group the active index into candidate families without writing anything.

    Answers 503 rather than a degraded result when the index is unreachable. Unlike
    search, which drops to the lexical branch, there is no honest partial answer
    here: proposing groupings without the index would mean inventing catalogue
    structure.
    """
    if settings.stub_mode:
        return families_suggest_stub(payload, principal)

    if not settings.database_url:
        raise _missing("DATABASE_URL")

    try:
        return await suggest_families(
            payload,
            settings,
            trace_id=principal.trace_id,
        )
    except InvalidPieceTypeError as exc:
        # 422 and not an empty result: a typo would otherwise narrow the query to
        # nothing and answer with a plausible-looking empty body.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatabaseNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except FamilyDependencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.post(
    "/audit",
    response_model=FamilyAuditResponse,
    summary="Audit existing families, and nominate the products that look like members",
)
async def audit(
    payload: FamilyAuditRequest,
    request: Request,
    principal: ServicePrincipal = Depends(get_catalog_principal),
    settings: Settings = Depends(get_app_settings),
) -> FamilyAuditResponse:
    """Report unsupported memberships and orphan candidates, writing nothing.

    The tenth `/v1` path, and a separate route rather than an extension of `/suggest`
    on purpose: the two read disjoint populations — suggestion reads products that
    belong to no family, this reads the families that exist — and they converge
    differently, since suggestion empties itself as batches are approved while the
    audit is a standing signal. Folding one into the other would move the committed
    snapshot just the same, so nothing would be saved by it.

    Answers 503 rather than a degraded result when the index is unreachable, for the
    same reason `/suggest` does — and here the stakes are higher. This route feeds a
    catalogue-quality screen, where an empty answer reads as "the catalogue is clean".
    Returning one because the index did not respond would assert by accident exactly
    the conclusion the review exists to establish with evidence.
    """
    if settings.stub_mode:
        return families_audit_stub(payload, principal)

    if not settings.database_url:
        raise _missing("DATABASE_URL")

    try:
        return await audit_families(
            payload,
            settings,
            trace_id=principal.trace_id,
        )
    except InvalidPieceTypeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatabaseNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except FamilyDependencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
