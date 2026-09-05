"""C22 schema: the one additive column `ai.pos_projection.computed_as_of`.

The revision is deliberately the smallest thing that can be true. These tests pin
both halves of that: the column exists and behaves as declared, and **nothing else
moved** — because the change was proposed, and its ticket and story written, as
carrying no migration at all. Opening one is a correction; letting a second thing
ride along with it would be how the correction turns into a habit.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.db

AI = "ai"
C13 = "b8e3c1a4d7f0"
C22 = "c9a71f2b6d54"


def _columns(engine: sa.Engine, table: str) -> dict[str, sa.engine.Row]:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                """
                SELECT column_name, is_nullable, column_default, data_type
                FROM information_schema.columns
                WHERE table_schema = :schema AND table_name = :table
                """
            ),
            {"schema": AI, "table": table},
        ).all()
    return {row[0]: row for row in rows}


def test_pos_projection_carries_the_reference_instant(migrated: sa.Engine) -> None:
    """The instant the feed counted the sales windows against, stored per row.

    Per row and not once per synchronisation: the availability feed is incremental,
    so a pair it does not re-emit keeps the figures the run that wrote it computed.
    One projection can hold rows counted against different instants, and only a
    per-row column can tell them apart.
    """
    as_of = datetime(2026, 8, 23, 23, 59, 59, tzinfo=UTC)
    with migrated.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO ai.pos_projection
                    (pos_id, product_id, qty_bucket, computed_as_of)
                VALUES (:pos_id, :product_id, '1-2', :computed_as_of)
                """
            ),
            {
                "pos_id": uuid.uuid4(),
                "product_id": uuid.uuid4(),
                "computed_as_of": as_of,
            },
        )

    with migrated.connect() as connection:
        stored = connection.execute(
            sa.text("SELECT computed_as_of FROM ai.pos_projection")
        ).scalar()

    assert stored == as_of
    assert stored.tzinfo is not None, "the reference instant must be timezone-aware"


def test_computed_as_of_is_nullable_and_has_no_default(migrated: sa.Engine) -> None:
    """Nullable with no default is what makes the revision free of a table rewrite."""
    column = _columns(migrated, "pos_projection")["computed_as_of"]

    assert column.is_nullable == "YES"
    assert column.column_default is None
    assert column.data_type == "timestamp with time zone"


def test_a_row_without_a_reference_instant_is_accepted(migrated: sa.Engine) -> None:
    """A drain against a feed that declares no instant is still a legitimate drain."""
    with migrated.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO ai.pos_projection (pos_id, product_id, qty_bucket)
                VALUES (:pos_id, :product_id, '0')
                """
            ),
            {"pos_id": uuid.uuid4(), "product_id": uuid.uuid4()},
        )

    with migrated.connect() as connection:
        assert (
            connection.execute(
                sa.text("SELECT computed_as_of FROM ai.pos_projection")
            ).scalar()
            is None
        )


def test_the_revision_touches_nothing_else(migrated: sa.Engine) -> None:
    """Additive means additive: same tables, same other columns, same constraint."""
    columns = _columns(migrated, "pos_projection")

    assert set(columns) == {
        "pos_id",
        "product_id",
        "is_assigned_hint",
        "qty_bucket",
        "sales_30d",
        "sales_90d",
        "last_sale_at",
        "refreshed_at",
        "computed_as_of",
    }

    with migrated.connect() as connection:
        checks = {
            row[0]
            for row in connection.execute(
                sa.text(
                    """
                    SELECT conname FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    WHERE n.nspname = :schema AND t.relname = 'pos_projection'
                      AND c.contype = 'c'
                    """
                ),
                {"schema": AI},
            )
        }

    assert "ck_pos_projection_qty_bucket" in checks


def test_upgrade_downgrade_is_reversible(
    alembic_config: Config, database_url: str
) -> None:
    """Downgrading to C13 removes the column and leaves the C05 table intact."""
    command.upgrade(alembic_config, "head")
    engine = sa.create_engine(database_url)
    try:
        assert "computed_as_of" in _columns(engine, "pos_projection")

        command.downgrade(alembic_config, C13)
        after = _columns(engine, "pos_projection")
        assert "computed_as_of" not in after
        assert "qty_bucket" in after, "the C05 table must survive the downgrade"

        command.upgrade(alembic_config, C22)
        assert "computed_as_of" in _columns(engine, "pos_projection")
    finally:
        engine.dispose()
