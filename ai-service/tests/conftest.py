"""Shared pytest fixtures for jbg-ai tests.

Tests set required env in-process and never call LLM, embeddings, or RDS.
"""

from __future__ import annotations

import socket
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from jbg_ai.api.main import create_app
from jbg_ai.config.settings import Settings, get_settings
from support.paths import ALEMBIC_INI, MIGRATIONS_DIR
from support.settings import TEST_JWT_SECRET, TOKEN_POS_ID, TOKEN_TRACE_ID, build_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def minimal_settings() -> Settings:
    return build_settings()


@pytest.fixture
def client(minimal_settings: Settings) -> Iterator[TestClient]:
    """Client for the default profile: stubs on, development endpoints mounted."""
    with TestClient(create_app(minimal_settings)) as test_client:
        yield test_client


@pytest.fixture
def issue_token() -> Callable[..., str]:
    """Sign an internal service token; override claims or drop them with None."""

    def _issue(
        *,
        secret: str = TEST_JWT_SECRET,
        expires_in: int = 300,
        **claims: Any,
    ) -> str:
        now = datetime.now(tz=UTC)
        payload: dict[str, Any] = {
            "user_id": "u-1",
            "role": "Operator",
            "pos_id": TOKEN_POS_ID,
            "trace_id": TOKEN_TRACE_ID,
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
        }
        payload.update(claims)
        return jwt.encode(
            {key: value for key, value in payload.items() if value is not None},
            secret,
            algorithm="HS256",
        )

    return _issue


@pytest.fixture
def auth_headers(issue_token: Callable[..., str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token()}"}


@pytest.fixture
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn any socket connection into a failure: stubs must do no external I/O."""

    def _fail(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("stub mode must not open a network connection")

    monkeypatch.setattr(socket.socket, "connect", _fail)
    monkeypatch.setattr(socket, "create_connection", _fail)


#: Same image as `backend/docker-compose.yml`, so the tests exercise the engine
#: developers actually run against.
POSTGRES_IMAGE = "pgvector/pgvector:pg15"


@pytest.fixture(scope="session")
def postgres_container():
    """One container for the whole session; databases inside it are per test."""
    try:
        # Moved to `community` in testcontainers 4.x; the old path still works
        # but warns, and the fallback keeps this working on either version.
        from testcontainers.community.postgres import PostgresContainer
    except ImportError:
        try:
            from testcontainers.postgres import PostgresContainer
        except ImportError as exc:  # pragma: no cover - dependency is declared
            pytest.skip(f"testcontainers is not installed: {exc}")

    try:
        container = PostgresContainer(POSTGRES_IMAGE, driver="psycopg")
        container.start()
    except Exception as exc:  # noqa: BLE001 - any docker failure means "skip"
        pytest.skip(f"needs a reachable Docker daemon to run pgvector: {exc}")

    try:
        yield container
    finally:
        container.stop()


@pytest.fixture
def database_url(postgres_container) -> Iterator[str]:
    """A brand-new, empty database, dropped when the test ends.

    Created from the container's maintenance connection with AUTOCOMMIT, because
    `CREATE DATABASE` cannot run inside a transaction block.
    """
    admin_url = postgres_container.get_connection_url()
    name = f"c05_{uuid.uuid4().hex[:12]}"

    admin = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(sa.text(f'CREATE DATABASE "{name}"'))

    try:
        yield admin_url.rsplit("/", 1)[0] + f"/{name}"
    finally:
        with admin.connect() as connection:
            # Any pooled connection of the test would block the drop.
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": name},
            )
            connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    """Alembic driven exactly as an operator would drive it.

    The tests run the real migration rather than a copy of its DDL: a copy would
    drift from the revision and start asserting a schema nobody deploys.
    """
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
def migrated(alembic_config: Config, database_url: str) -> Iterator[sa.Engine]:
    """A database at `head`, with an engine to inspect what the migration built."""
    command.upgrade(alembic_config, "head")

    engine = sa.create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()
