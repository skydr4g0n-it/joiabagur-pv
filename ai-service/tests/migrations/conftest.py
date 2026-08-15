"""Throwaway PostgreSQL with pgvector for the migration tests. Delivered by C05.

Two decisions here are worth stating, because both are easy to get wrong.

**A fresh database per test, not a shared one.** `test_upgrade_downgrade_is_reversible`
mutates the schema. Sharing a database would make these tests order-dependent,
which is exactly the failure mode `CLAUDE.md` records as poison in the .NET suite
— where a handful of tests already disagree between two runs of identical code.

**Skip, don't fail, when Docker is unreachable.** There is no CI running the
Python suite yet, so permanent red on a laptop would teach everyone to ignore
red, which costs more than these four tests are worth. The trade-off is real: a
green run does not by itself prove the migration was exercised. Check that the
`db` tests ran, not merely that nothing failed.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from support.paths import ALEMBIC_INI, MIGRATIONS_DIR

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
