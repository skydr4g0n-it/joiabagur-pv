"""Internal service token (HS256) validation for the `/v1` surface.

The .NET API is the only issuer. Claim names are frozen in snake_case on the
wire; C03 maps its C# properties when signing.
"""

from __future__ import annotations

import jwt
from pydantic import BaseModel

ALGORITHM = "HS256"
REQUIRED_CLAIMS = ("user_id", "role", "pos_id", "trace_id")


class ServicePrincipal(BaseModel):
    """Caller identity taken from the token — never from the request body."""

    user_id: str
    role: str
    pos_id: str
    trace_id: str


class InvalidServiceToken(Exception):
    """Any token that cannot be trusted. The exact cause is never surfaced."""


def decode_service_token(token: str, secret: str) -> ServicePrincipal:
    """Validate signature, expiry and required claims, or raise InvalidServiceToken."""
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:  # bad signature, wrong alg, expired, malformed
        raise InvalidServiceToken from exc

    claims: dict[str, str] = {}
    for claim in REQUIRED_CLAIMS:
        value = payload.get(claim)
        if value is None or not str(value).strip():
            raise InvalidServiceToken
        claims[claim] = str(value)

    return ServicePrincipal(**claims)
