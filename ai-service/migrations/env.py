"""Alembic environment for schema `ai`. Delivered by C05.

Two things here are load-bearing and neither is obvious.

**The version table lives in `ai`, not in `public`.** The design boundary (§6.3)
says Python never writes to `public`; Alembic's default would break that rule in
the project's very first Python migration, silently.

**The schema is provisioned here, not in the first revision.** Alembic
materialises its version table *before* running any revision script, so a
`CREATE SCHEMA` inside `upgrade()` would arrive after the failure it was meant
to prevent. The first revision declares the schema and the extension anyway,
idempotently, so its SQL stays self-describing.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

AI_SCHEMA = "ai"

config = context.config

if config.config_file_name is not None:
    # `disable_existing_loggers=False` is not optional here. The default is True, and
    # it disables every logger the ini does not name — which is all of `jbg_ai`.
    # Harmless under the Alembic CLI, where the process exits straight afterwards, and
    # destructive in-process: the migration tests run Alembic inside the same
    # interpreter as the rest of the suite, so the default left the service's loggers
    # dead for every test that ran later. It surfaced as two retrieval tests asserting
    # on log output and finding none, passing in isolation and failing in a full run.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Migrations are hand-written: `autogenerate` cannot express HNSW operator
# classes, GIN over arrays or generated columns, so there is no metadata to
# compare against and no ORM models in this change (design §11).
target_metadata = None


def _database_url() -> str:
    """Resolve the connection string: explicit config first, environment second.

    `alembic.ini` deliberately carries no `sqlalchemy.url`, so in normal operation
    this reads `DATABASE_URL` — one variable, resolved the same way locally and on
    RDS, with no credential in version control.

    The precedence matters for one caller: the migration tests set the URL on the
    Config so each test drives its own throwaway database. With the environment
    winning instead, a developer who happens to have `DATABASE_URL` exported would
    have those tests migrate and drop against their own development database.
    """
    url = config.get_main_option("sqlalchemy.url") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Alembic needs a PostgreSQL connection string, "
            "for example postgresql+psycopg://user:password@localhost:5433/joiabagur_pv"
        )
    return url


def _provision(connection) -> None:
    """Ensure schema and extension exist before the version table is created.

    Deliberately *check first, then create* rather than `IF NOT EXISTS`.

    PostgreSQL evaluates the privilege before the `IF NOT EXISTS` short-circuit,
    so `CREATE SCHEMA IF NOT EXISTS ai` raises "permission denied for database"
    for an unprivileged role **even when the schema already exists**. That would
    break the RDS path, where the administrator provisions everything up front
    and the service role only migrates — which is exactly the arrangement that
    lets one DATABASE_URL serve both worlds (design §4).

    Checking first makes the already-provisioned case a true no-op: no DDL is
    attempted, so no privilege is required.
    """
    schema_exists = connection.execute(
        text("SELECT 1 FROM pg_namespace WHERE nspname = :name"),
        {"name": AI_SCHEMA},
    ).scalar()
    if not schema_exists:
        connection.execute(text(f'CREATE SCHEMA "{AI_SCHEMA}"'))

    extension_exists = connection.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
    ).scalar()
    if not extension_exists:
        connection.execute(text("CREATE EXTENSION vector"))


def run_migrations_offline() -> None:
    """Emit SQL without a connection (`alembic upgrade --sql`)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=AI_SCHEMA,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _provision(connection)
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=AI_SCHEMA,
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
