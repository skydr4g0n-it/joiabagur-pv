"""Connection pool shape and lazy construction. Delivered by C05.

None of these tests opens a connection: `create_async_engine` does not connect
eagerly, so the pool can be inspected without a database. That is deliberate —
these guard configuration, and configuration should not need a container.
"""

from __future__ import annotations

import pytest

from jbg_ai.config.settings import Settings
from jbg_ai.db import engine as engine_module
from jbg_ai.db.engine import (
    POOL_TIMEOUT_SECONDS,
    DatabaseNotConfiguredError,
    get_engine,
    get_sessionmaker,
)
from support.settings import build_settings

DUMMY_URL = "postgresql+psycopg://user:password@localhost:5432/jpv"


@pytest.fixture(autouse=True)
def _reset_engine_state():
    """The engine is process-wide, so each test starts from a clean slate."""
    engine_module._engine = None
    engine_module._sessionmaker = None
    yield
    engine_module._engine = None
    engine_module._sessionmaker = None


def _settings_with_database(**overrides: object) -> Settings:
    return build_settings(database_url=DUMMY_URL, **overrides)


def test_pool_is_capped_at_configured_size_without_overflow() -> None:
    """A ceiling of five must mean five.

    SQLAlchemy's default `max_overflow` is 10, which would let a pool declared
    as 5 open 15 connections under load — against a budget of 5-10 for the whole
    system, shared with the .NET API on the same instance.
    """
    pool = get_engine(_settings_with_database()).pool

    assert pool.size() == 5
    # No public accessor exists for the configured maximum overflow; the current
    # overflow counter (`pool.overflow()`) is a different number.
    assert pool._max_overflow == 0


def test_pool_size_follows_configuration() -> None:
    pool = get_engine(_settings_with_database(db_pool_size=3)).pool

    assert pool.size() == 3
    assert pool._max_overflow == 0


def test_pool_wait_is_shorter_than_the_caller_latency_budget() -> None:
    """The .NET client cuts retrieval at 0.8 s; SQLAlchemy waits 30 s by default.

    Anything above that budget is time spent serving a caller who already gave up.
    """
    pool = get_engine(_settings_with_database()).pool

    # `timeout` is a method on QueuePool, not a property: reading it without
    # calling it compares a bound method against a float and always fails.
    assert pool.timeout() == POOL_TIMEOUT_SECONDS
    assert pool.timeout() < 30.0, "the default would outlive the caller's own timeout"


def test_engine_pre_pings_connections() -> None:
    """RDS closes idle connections; without this the first query after a quiet
    period fails on a socket the pool still believes is open."""
    assert get_engine(_settings_with_database()).pool._pre_ping is True


def test_importing_the_module_creates_no_engine() -> None:
    """Boot must not depend on a database, so nothing is built at import time."""
    assert engine_module._engine is None
    assert engine_module._sessionmaker is None


def test_engine_is_built_once_and_reused() -> None:
    settings = _settings_with_database()

    assert get_engine(settings) is get_engine(settings)


def test_sessionmaker_is_built_once_and_reused() -> None:
    settings = _settings_with_database()

    assert get_sessionmaker(settings) is get_sessionmaker(settings)


def test_engine_without_database_url_fails_naming_the_missing_setting() -> None:
    """The failure belongs to first use, not to startup.

    Under `STUB_MODE` nothing requests a session, so a service with no database
    configured must still boot and serve.
    """
    with pytest.raises(DatabaseNotConfiguredError) as failure:
        get_engine(build_settings())

    assert "DATABASE_URL" in str(failure.value)


def test_sessionmaker_without_database_url_fails_the_same_way() -> None:
    with pytest.raises(DatabaseNotConfiguredError):
        get_sessionmaker(build_settings())
