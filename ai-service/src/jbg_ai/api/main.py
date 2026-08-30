"""FastAPI application factory for jbg-ai."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request

from jbg_ai.api.health_report import (
    HealthProbe,
    SqlAlchemyHealthProbe,
    cached_health_report,
)
from jbg_ai.api.middleware import TraceIdMiddleware
from jbg_ai.api.routers import DOMAIN_ROUTERS, evals
from jbg_ai.config import Settings, get_settings


def configure_logging(log_level: str) -> None:
    """Configure structured-friendly logging with a trace_id field when present."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    class TraceIdFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if not hasattr(record, "trace_id"):
                record.trace_id = "-"
            return True

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s trace_id=%(trace_id)s %(name)s %(message)s"
        )
    )
    handler.addFilter(TraceIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app with settings, health, and trace middleware."""
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)

    app = FastAPI(
        title="jbg-ai",
        version=resolved.service_version,
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = resolved
    app.add_middleware(TraceIdMiddleware)

    @app.get("/health", tags=["health"], summary="Public liveness probe")
    async def health(request: Request) -> dict[str, Any]:
        # The return annotation stays an open mapping and the path stays the
        # same: enriching the payload does not move the frozen contract, whereas
        # a response model or a second route would, and `openapi.json` is agreed
        # with the .NET side (C17 D12).
        #
        # `app.state.health_probe` is the injection point tests use, following
        # the same idiom as the retrieval and index routers. In production it is
        # absent and the real probe is built here.
        probe: HealthProbe = getattr(request.app.state, "health_probe", None) or (
            SqlAlchemyHealthProbe(resolved)
        )
        return await cached_health_report(request.app.state, resolved, probe)

    for router in DOMAIN_ROUTERS:
        app.include_router(router)

    # Evals is a development tool: under a production profile the path must not
    # exist at all, rather than answer a documented but misleading 404.
    if resolved.enable_dev_endpoints:
        app.include_router(evals.router)

    return app
