"""HTTP middleware for request correlation."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

TRACE_HEADER = "X-Trace-Id"
logger = logging.getLogger("jbg_ai")


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Bind trace_id from X-Trace-Id (or a new UUID) into logs and the response.

    An authenticated request may replace `request.state.trace_id` with the token
    claim; the effective value is re-read after the handler so logs and the
    response header agree with what the issuer sent.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = request.headers.get(TRACE_HEADER)
        trace_id = incoming.strip() if incoming and incoming.strip() else str(uuid.uuid4())
        request.state.trace_id = trace_id

        logger.info(
            "request_started method=%s path=%s",
            request.method,
            request.url.path,
            extra={"trace_id": trace_id},
        )

        response = await call_next(request)

        effective = getattr(request.state, "trace_id", None) or trace_id
        response.headers[TRACE_HEADER] = effective

        logger.info(
            "request_finished method=%s path=%s status=%s",
            request.method,
            request.url.path,
            response.status_code,
            extra={"trace_id": effective},
        )
        return response
