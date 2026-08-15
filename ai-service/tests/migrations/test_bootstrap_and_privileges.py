"""The provisioning script and the ownership boundary it creates. Delivered by C05.

`bootstrap.sql` is a deliverable that no driver can execute — it uses psql
meta-commands — so it is the piece most likely to rot unnoticed. These tests run
the real file with psql inside the container and then ask PostgreSQL itself
whether the boundary holds, rather than reading the grants and believing them.

The boundary matters beyond tidiness: the design says Python never writes to
`public` and never reads it by SQL. Here that stops being a convention and
becomes something the server refuses.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import ProgrammingError

pytestmark = pytest.mark.db

AI = "ai"
SERVICE_ROLE = "jbg_ai"
SERVICE_PASSWORD = "bootstrap-test-password"


def _service_url(database_url: str) -> str:
    """The same database, reached as the dedicated role instead of the owner."""
    _, tail = database_url.split("://", 1)
    _, host_and_db = tail.split("@", 1)
    return f"postgresql+psycopg://{SERVICE_ROLE}:{SERVICE_PASSWORD}@{host_and_db}"


def test_bootstrap_provisions_extension_schema_and_role(
    run_bootstrap, database_url: str
) -> None:
    """One privileged run leaves everything the migration needs in place."""
    exit_code, output = run_bootstrap(SERVICE_PASSWORD)

    assert exit_code == 0, output
    assert "role jbg_ai created" in output or "already exists" in output

    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.execute(
                sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
            assert connection.execute(
                sa.text("SELECT 1 FROM pg_namespace WHERE nspname = :name"),
                {"name": AI},
            ).scalar()
            assert connection.execute(
                sa.text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
                {"name": SERVICE_ROLE},
            ).scalar()
    finally:
        engine.dispose()


def test_bootstrap_is_idempotent_and_keeps_the_existing_password(
    run_bootstrap,
) -> None:
    """Re-running must never silently rotate a production credential."""
    first_code, _ = run_bootstrap(SERVICE_PASSWORD)
    second_code, second_output = run_bootstrap("a-completely-different-password")

    assert first_code == 0
    assert second_code == 0, second_output
    assert "password left untouched" in second_output


def test_service_role_can_migrate_and_own_the_ai_schema(
    run_bootstrap, alembic_config: Config, database_url: str
) -> None:
    """The RDS path: the administrator provisions, the service role migrates.

    The dedicated role cannot install extensions, so this only works because
    provisioning checks before creating instead of relying on `IF NOT EXISTS`,
    which PostgreSQL rejects on privilege *before* its short-circuit.
    """
    run_bootstrap(SERVICE_PASSWORD)

    alembic_config.set_main_option("sqlalchemy.url", _service_url(database_url))
    command.upgrade(alembic_config, "head")

    engine = sa.create_engine(_service_url(database_url))
    try:
        with engine.connect() as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    sa.text("SELECT tablename FROM pg_tables WHERE schemaname = :s"),
                    {"s": AI},
                )
            }
    finally:
        engine.dispose()

    assert "product_document" in tables


def test_service_role_cannot_read_business_tables(
    run_bootstrap, database_url: str
) -> None:
    """`public` belongs to .NET. Python reads it over HTTP or not at all."""
    owner = sa.create_engine(database_url)
    try:
        with owner.begin() as connection:
            # Stand in for a table EF Core owns.
            connection.execute(sa.text('CREATE TABLE public."Products" (id int)'))
    finally:
        owner.dispose()

    run_bootstrap(SERVICE_PASSWORD)

    service = sa.create_engine(_service_url(database_url))
    try:
        with service.connect() as connection, pytest.raises(ProgrammingError) as denied:
            connection.execute(sa.text('SELECT count(*) FROM public."Products"'))
    finally:
        service.dispose()

    assert "permission denied" in str(denied.value).lower()


def test_service_role_cannot_create_in_the_business_schema(
    run_bootstrap, database_url: str
) -> None:
    run_bootstrap(SERVICE_PASSWORD)

    service = sa.create_engine(_service_url(database_url))
    try:
        with service.connect() as connection, pytest.raises(ProgrammingError) as denied:
            connection.execute(sa.text("CREATE TABLE public._probe (id int)"))
    finally:
        service.dispose()

    assert "permission denied" in str(denied.value).lower()


def test_migration_is_idempotent_when_already_provisioned(
    alembic_config: Config, database_url: str
) -> None:
    """Applying twice must be a no-op, not an error."""
    command.upgrade(alembic_config, "head")
    command.upgrade(alembic_config, "head")

    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as connection:
            revisions = connection.execute(
                sa.text("SELECT count(*) FROM ai.alembic_version")
            ).scalar()
    finally:
        engine.dispose()

    assert revisions == 1


def test_migration_without_provisioning_fails_identifiably(
    alembic_config: Config, database_url: str
) -> None:
    """A role that cannot provision, against a database nobody provisioned.

    The failure must name the cause and must not leave a half-built schema —
    the alternative is a database that looks migrated and is not.
    """
    owner = sa.create_engine(database_url, isolation_level="AUTOCOMMIT")
    try:
        with owner.connect() as connection:
            # Cluster-level, so it may survive from an earlier test in the session.
            if not _role_exists(connection, "unprivileged"):
                connection.execute(
                    sa.text(
                        "CREATE ROLE unprivileged LOGIN PASSWORD :password".replace(
                            ":password", f"'{SERVICE_PASSWORD}'"
                        )
                    )
                )
    finally:
        owner.dispose()

    _, tail = database_url.split("://", 1)
    _, host_and_db = tail.split("@", 1)
    alembic_config.set_main_option(
        "sqlalchemy.url",
        f"postgresql+psycopg://unprivileged:{SERVICE_PASSWORD}@{host_and_db}",
    )

    with pytest.raises(ProgrammingError) as failure:
        command.upgrade(alembic_config, "head")

    assert "permission denied" in str(failure.value).lower()

    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    sa.text("SELECT tablename FROM pg_tables WHERE schemaname = :s"),
                    {"s": AI},
                )
            }
    finally:
        engine.dispose()

    assert "product_document" not in tables, "a failed migration left a partial schema"


def _role_exists(connection: sa.Connection, name: str) -> bool:
    return bool(
        connection.execute(
            sa.text("SELECT 1 FROM pg_roles WHERE rolname = :name"), {"name": name}
        ).scalar()
    )
