"""FastAPI application factory for jbg-ai."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

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
    def health() -> dict[str, Any]:
        return {
            "status": "OK",
            "version": resolved.service_version,
        }

    for router in DOMAIN_ROUTERS:
        app.include_router(router)

    # Evals is a development tool: under a production profile the path must not
    # exist at all, rather than answer a documented but misleading 404.
    if resolved.enable_dev_endpoints:
        app.include_router(evals.router)

    return app
