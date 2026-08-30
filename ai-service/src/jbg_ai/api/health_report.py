"""Enriched health report for `GET /health`. Delivered by C17.

Four properties are deliberate, and each one prevents a failure with a name.

**The provider is never called.** The report says whether the embedding
credential is *configured*, not whether the provider is answering. A probe that
depends on a third party turns somebody else's outage into a failed deployment
and, with a container runtime watching it, into a restart loop. None of the
three consumers — the container health check, post-deployment verification, and
the administrator card on the dashboard — needs to know the provider is up. What
they need to know is whether somebody forgot to configure the credential, which
is the failure that actually happens.

**The configured embedding model is contrasted against the index.** Querying
with a model other than the one that produced the indexed vectors compares two
different vector spaces: the answer is noise, the status code is 200, and
nothing is logged. It is the most silent failure in the whole deployment, and
the index already records the model per row, so detecting it needs no new
schema.

**The result is cached for a short window.** The connection pool is capped at
five for the whole system and shared with the .NET API. A probe that opened a
connection per call could be the thing that exhausts the pool during an
incident: the probe causing the outage it reports.

**The shape stays an open mapping.** No Pydantic response model and no new
route, so the frozen OpenAPI snapshot — and the drift test that guards it —
are unaffected. Splitting this into liveness and readiness probes *would* move
the contract, and is recorded as deferred rather than done here.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import text

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.indexing.constants import DEFAULT_EMBEDDING_MODEL

logger = logging.getLogger(__name__)

#: How long a report is reused. Short enough that an operator refreshing the
#: dashboard sees the environment change within seconds; long enough that a
#: container health check every 30 s and a human clicking about cannot together
#: monopolise a pool of five connections.
HEALTH_CACHE_TTL_SECONDS = 10.0

STATUS_OK = "OK"
STATUS_DEGRADED = "degraded"

DATABASE_OK = "ok"
DATABASE_UNAVAILABLE = "unavailable"
#: A third state, and not a pedantic one. The service is specified to boot and
#: serve without a database — that is what `ai-service-dev-compose` guarantees
#: and what stub mode relies on — so an absent `DATABASE_URL` is a documented
#: configuration, not an outage. Collapsing it into `unavailable` would report
#: every local run and every test run as degraded. In the demo environment the
#: variable is always set, so this value never appears there, and
#: post-deployment verification requires `ok` rather than merely "not broken".
DATABASE_NOT_CONFIGURED = "not_configured"

INDEX_OK = "ok"
INDEX_MODEL_MISMATCH = "model_mismatch"
INDEX_UNAVAILABLE = "unavailable"

PROVIDER_CONFIGURED = "configured"
PROVIDER_MISSING = "missing"


@dataclass(frozen=True)
class IndexSnapshot:
    """What one look at the database found.

    `models` holds the DISTINCT `embedding_model` values present on the index
    rows — a tuple rather than a single value because an index half-reindexed
    with a second model is a real state, and reporting only one of the two
    models would hide it.
    """

    database_reachable: bool
    documents: int = 0
    models: tuple[str, ...] = ()
    #: False only when no `DATABASE_URL` is configured at all. See
    #: DATABASE_NOT_CONFIGURED.
    database_configured: bool = True


class HealthProbe(Protocol):
    """One database round trip, injectable so tests never need a database."""

    async def snapshot(self) -> IndexSnapshot: ...


class SqlAlchemyHealthProbe:
    """Both questions in ONE session, so the report costs one connection."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def snapshot(self) -> IndexSnapshot:
        # Asked before any connection is attempted: an absent DATABASE_URL is a
        # configuration, not a failure, and `session_scope` would raise for it.
        if not self._settings.database_url:
            return IndexSnapshot(database_reachable=False, database_configured=False)

        try:
            async with session_scope(self._settings) as session:
                documents = (
                    await session.execute(text("SELECT count(*) FROM ai.product_document"))
                ).scalar()
                models = (
                    await session.execute(
                        text(
                            "SELECT DISTINCT embedding_model FROM ai.product_document "
                            "WHERE embedding_model IS NOT NULL"
                        )
                    )
                ).scalars().all()
        except Exception:  # noqa: BLE001 - any failure to reach the database is one answer
            # Deliberately broad, and deliberately not re-raised. This endpoint
            # exists to REPORT that the database is unreachable; raising would
            # turn the report into the outage.
            logger.warning("health_probe_database_unreachable", exc_info=True)
            return IndexSnapshot(database_reachable=False)

        return IndexSnapshot(
            database_reachable=True,
            documents=int(documents or 0),
            models=tuple(sorted(str(model) for model in models)),
        )


def configured_embedding_model(settings: Settings) -> str:
    """The model retrieval would embed a query with, resolved the same way it is."""
    return settings.jpv_embedding_model or DEFAULT_EMBEDDING_MODEL


async def build_health_report(settings: Settings, probe: HealthProbe) -> dict[str, Any]:
    """Compose the report. Never raises, never calls the embedding provider."""
    configured_model = configured_embedding_model(settings)
    provider = PROVIDER_CONFIGURED if settings.jpv_embedding_api_key else PROVIDER_MISSING

    snapshot = await probe.snapshot()

    if not snapshot.database_reachable:
        index: dict[str, Any] = {
            "documents": 0,
            "model": None,
            "configured_model": configured_model,
            "status": INDEX_UNAVAILABLE,
        }
        return {
            # A database that was never configured is not a degradation: the
            # service is required to boot and answer without one.
            "status": STATUS_OK if not snapshot.database_configured else STATUS_DEGRADED,
            "version": settings.service_version,
            "database": (
                DATABASE_NOT_CONFIGURED
                if not snapshot.database_configured
                else DATABASE_UNAVAILABLE
            ),
            "index": index,
            "provider": provider,
        }

    # An empty index is NOT a mismatch. There is no indexed model to disagree
    # with, and reporting one would make a brand-new environment — which is
    # exactly the state the deployment starts in — look broken rather than
    # empty. Emptiness is caught by post-deployment verification, which requires
    # a document count above zero, and that is the right place for it.
    if not snapshot.models:
        indexed_model: str | None = None
        index_status = INDEX_OK
    elif set(snapshot.models) == {configured_model}:
        indexed_model = snapshot.models[0]
        index_status = INDEX_OK
    else:
        # Both models are named in the body on purpose: "mismatch" alone leaves
        # the reader to guess which of the two is wrong, and the answer decides
        # whether the fix is a configuration change or a reindex.
        indexed_model = ", ".join(snapshot.models)
        index_status = INDEX_MODEL_MISMATCH

    return {
        "status": STATUS_OK if index_status == INDEX_OK else STATUS_DEGRADED,
        "version": settings.service_version,
        "database": DATABASE_OK,
        "index": {
            "documents": snapshot.documents,
            "model": indexed_model,
            "configured_model": configured_model,
            "status": index_status,
        },
        "provider": provider,
    }


async def cached_health_report(
    state: Any,
    settings: Settings,
    probe: HealthProbe,
    *,
    ttl_seconds: float = HEALTH_CACHE_TTL_SECONDS,
) -> dict[str, Any]:
    """Reuse the last report for `ttl_seconds`.

    The cache lives on the application state rather than in a module global, so
    two applications in one process — which is every test file here — cannot
    serve each other's answers.
    """
    cached = getattr(state, "health_cache", None)
    now = time.monotonic()

    if cached is not None and now < cached[0]:
        return cached[1]  # type: ignore[no-any-return]

    report = await build_health_report(settings, probe)
    state.health_cache = (now + ttl_seconds, report)
    return report
