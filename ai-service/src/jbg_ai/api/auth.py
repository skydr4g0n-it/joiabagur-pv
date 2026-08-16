"""Internal service token (HS256) validation for the `/v1` surface.

The .NET API is the only issuer. Claim names are frozen in snake_case on the
wire; C03 maps its C# properties when signing.
"""

from __future__ import annotations

import jwt
from pydantic import BaseModel

ALGORITHM = "HS256"

#: Required on every `/v1` route, whatever its scope.
BASE_CLAIMS = ("user_id", "role", "trace_id")

#: Required additionally on routes that operate inside one point of sale.
POS_CLAIM = "pos_id"

#: Retrieval, sale assistance and inventory: the caller is always somewhere.
REQUIRED_CLAIMS = (*BASE_CLAIMS, POS_CLAIM)

#: Enrichment and index synchronization: the catalog belongs to no point of sale,
#: so demanding one would force the caller to invent a value — and a wildcard
#: `pos_id` is exactly what must never exist, because from the soft-prefilter
#: change onward that claim is the retriever's only hard filter.
CATALOG_CLAIMS = BASE_CLAIMS


class ServicePrincipal(BaseModel):
    """Caller identity taken from the token — never from the request body."""

    user_id: str
    role: str
    trace_id: str
    pos_id: str | None = None


class InvalidServiceToken(Exception):
    """Any token that cannot be trusted. The exact cause is never surfaced."""


def decode_service_token(
    token: str, secret: str, required_claims: tuple[str, ...] = REQUIRED_CLAIMS
) -> ServicePrincipal:
    """Validate signature, expiry and required claims, or raise InvalidServiceToken.

    Which claims are required is a property of the route, not of the token: the
    same signed token is rejected on retrieval and accepted on enrichment when it
    carries no point of sale. Passing that in keeps the decision where the route
    is declared instead of leaving it to whoever reads the principal.
    """
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:  # bad signature, wrong alg, expired, malformed
        raise InvalidServiceToken from exc

    claims: dict[str, str] = {}
    for claim in required_claims:
        value = payload.get(claim)
        if value is None or not str(value).strip():
            raise InvalidServiceToken
        claims[claim] = str(value)

    # Carried when present even if not required, so a point-of-sale token used on
    # a catalog route still reports the scope it was issued with.
    if POS_CLAIM not in claims:
        optional = payload.get(POS_CLAIM)
        if optional is not None and str(optional).strip():
            claims[POS_CLAIM] = str(optional)

    return ServicePrincipal(**claims)
