"""Async engine over schema `ai`, with a pool that is capped for real.

Delivered by C05. No query lives here yet — C11 and C13 bring the first ones.

Three properties are deliberate and each one has a failure it prevents.

**Built on first use, never at import time.** `ai-service-dev-compose` guarantees
that `jbg-ai` boots without a database; constructing an engine while importing a
module would make that guarantee depend on nobody importing the wrong thing.

**Capped at `db_pool_size` with no overflow.** SQLAlchemy's default adds ten
more connections on top of the pool, which would turn a stated ceiling of five
into a real ceiling of fifteen — against a budget of 5-10 for the whole system,
shared with the .NET API on the same RDS instance.

**A short wait for a free connection.** The default is 30 seconds. The .NET side
cuts retrieval at 0.8 s with Polly, so anything longer is work done for a caller
who left. Queueing rather than failing is on purpose: the circuit breaker
already owns the decision to give up, and a second policy here would produce two
different degradation behaviours for the same symptom.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from jbg_ai.config.settings import Settings

#: Seconds to wait for a free connection. Comfortably inside the 0.8 s budget
#: the .NET client allows a retrieval call, so a caller never waits on a pool
#: for longer than the request that is waiting on them.
POOL_TIMEOUT_SECONDS = 2.0

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when the database is used without `DATABASE_URL` being set.

    Raised on first use rather than at startup: the service is expected to run
    without a database, and under `STUB_MODE` nothing ever asks for a session.
    """


def get_engine(settings: Settings) -> AsyncEngine:
    """Return the process-wide engine, building it the first time it is needed."""
    global _engine

    if _engine is None:
        if not settings.database_url:
            raise DatabaseNotConfiguredError(
                "DATABASE_URL is not set; the AI service cannot open a database "
                "session. Set it to a PostgreSQL connection string such as "
                "postgresql+psycopg://user:password@host:5432/db"
            )

        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            # No overflow: with the default of 10, a pool "capped at 5" would
            # actually open 15 connections under load.
            max_overflow=0,
            pool_timeout=POOL_TIMEOUT_SECONDS,
            # RDS drops idle connections; without this the first query after a
            # quiet period fails on a socket the pool still believes is open.
            pool_pre_ping=True,
        )

    return _engine


def get_sessionmaker(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session factory, built on first use."""
    global _sessionmaker

    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(settings),
            expire_on_commit=False,
        )

    return _sessionmaker


@asynccontextmanager
async def session_scope(settings: Settings) -> AsyncIterator[AsyncSession]:
    """Yield a session that commits on success and rolls back on failure."""
    factory = get_sessionmaker(settings)

    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Close every pooled connection and forget the engine.

    Used by tests and by an orderly shutdown; after this, the next call to
    `get_engine` builds a fresh engine.
    """
    global _engine, _sessionmaker

    if _engine is not None:
        await _engine.dispose()

    _engine = None
    _sessionmaker = None
