"""FastAPI dependencies: settings access, service authentication, stub guard."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jbg_ai.api.auth import InvalidServiceToken, ServicePrincipal, decode_service_token
from jbg_ai.config import Settings

UNAUTHORIZED_DETAIL = "Invalid or missing internal service token"

#: Documented on every `/v1` route so the .NET client sees both failure modes.
V1_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": UNAUTHORIZED_DETAIL},
    501: {"description": "Not implemented yet; delivered in a later change"},
}

_bearer = HTTPBearer(auto_error=False, description="Internal HS256 service token")


def get_app_settings(request: Request) -> Settings:
    """Settings resolved once at app build time."""
    return request.app.state.settings  # type: ignore[no-any-return]


def get_service_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_app_settings),
) -> ServicePrincipal:
    """Reject anything but a valid internal token; expose the caller to handlers."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        principal = decode_service_token(credentials.credentials, settings.jwt_secret)
    except InvalidServiceToken:
        raise _unauthorized() from None

    # The issuer owns correlation: the claim wins over the middleware value.
    request.state.trace_id = principal.trace_id
    return principal


def require_stub_mode(settings: Settings, delivered_by: str) -> None:
    """Answer 501 while the real implementation of a frozen route does not exist."""
    if settings.stub_mode:
        return
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Not implemented yet: the real implementation arrives in a later change, "
            f"{delivered_by}"
        ),
    )


def _unauthorized() -> HTTPException:
    """One opaque 401 for every failure mode — never reveal which step failed."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=UNAUTHORIZED_DETAIL,
        headers={"WWW-Authenticate": "Bearer"},
    )
