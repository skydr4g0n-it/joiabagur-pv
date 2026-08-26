"""C13 schema: text_provenance, sync_checkpoint, sync_failure cursor columns."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.db

AI = "ai"
C05 = "f46c55c056e2"
C05_TABLES = {
    "product_document",
    "knowledge_document",
    "knowledge_chunk",
    "pos_projection",
    "co_occurrence",
    "sync_failure",
}


def _tables(engine: sa.Engine, schema: str) -> set[str]:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.text("SELECT tablename FROM pg_tables WHERE schemaname = :schema"),
            {"schema": schema},
        )
        return {row[0] for row in rows}


def _index_method_for_column(engine: sa.Engine, table: str, column: str) -> set[str]:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                """
                SELECT am.amname
                FROM pg_index i
                JOIN pg_class t ON t.oid = i.indrelid
                JOIN pg_class idx ON idx.oid = i.indexrelid
                JOIN pg_am am ON am.oid = idx.relam
                JOIN pg_namespace n ON n.oid = t.relnamespace
                JOIN pg_attribute a
                  ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0]
                WHERE n.nspname = :schema
                  AND t.relname = :table
                  AND a.attname = :column
                """
            ),
            {"schema": AI, "table": table, "column": column},
        )
        return {row[0] for row in rows}


def _insert_product(connection: sa.Connection, **overrides: object) -> None:
    values = {
        "product_id": uuid.uuid4(),
        "sku": "SKU-1",
        "name": "Anillo",
        "doc_text": "anillo de plata",
        "source_hash": "0" * 64,
        "data_origin": "real",
        "text_provenance": "merchant",
    }
    values.update(overrides)
    columns = ", ".join(values)
    params = ", ".join(f":{key}" for key in values)
    connection.execute(
        sa.text(
            f"INSERT INTO ai.product_document ({columns}) VALUES ({params})"
        ),
        values,
    )


def test_text_provenance_check_rejects_unknown_value(migrated: sa.Engine) -> None:
    with migrated.begin() as connection, pytest.raises(IntegrityError):
        _insert_product(connection, text_provenance="guessed")


def test_text_provenance_is_not_null(migrated: sa.Engine) -> None:
    with migrated.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(
            sa.text(
                """
                INSERT INTO ai.product_document
                    (product_id, sku, name, doc_text, source_hash, data_origin)
                VALUES (:product_id, 'SKU-1', 'Anillo', 't', :hash, 'real')
                """
            ),
            {"product_id": uuid.uuid4(), "hash": "0" * 64},
        )


def test_sync_checkpoint_table_exists(migrated: sa.Engine) -> None:
    assert "sync_checkpoint" in _tables(migrated, AI)
    with migrated.connect() as connection:
        columns = {
            row[0]
            for row in connection.execute(
                sa.text(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = :schema AND table_name = 'sync_checkpoint'
                    """
                ),
                {"schema": AI},
            )
        }
    assert {
        "feed",
        "watermark",
        "since_id",
        "last_full_sync_at",
        "last_incremental_sync_at",
        "last_aggregate_hash",
        "indexed_count",
    } <= columns


def test_sync_failure_has_cursor_since_id_and_product_id(migrated: sa.Engine) -> None:
    with migrated.connect() as connection:
        columns = {
            row[0]
            for row in connection.execute(
                sa.text(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = :schema AND table_name = 'sync_failure'
                    """
                ),
                {"schema": AI},
            )
        }
    assert "cursor_since_id" in columns
    assert "product_id" in columns


def test_c13_downgrade_drops_new_objects_and_keeps_c05_tables(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "head")
    engine = sa.create_engine(database_url)
    try:
        assert "sync_checkpoint" in _tables(engine, AI)
        command.downgrade(alembic_config, C05)
        remaining = _tables(engine, AI)
        assert C05_TABLES <= remaining
        assert "sync_checkpoint" not in remaining
        with engine.connect() as connection:
            columns = {
                row[0]
                for row in connection.execute(
                    sa.text(
                        """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema = :schema AND table_name = 'product_document'
                        """
                    ),
                    {"schema": AI},
                )
            }
            failure_cols = {
                row[0]
                for row in connection.execute(
                    sa.text(
                        """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema = :schema AND table_name = 'sync_failure'
                        """
                    ),
                    {"schema": AI},
                )
            }
        assert "text_provenance" not in columns
        assert "cursor_since_id" not in failure_cols
        assert "product_id" not in failure_cols
    finally:
        engine.dispose()


def test_text_provenance_has_btree_index(migrated: sa.Engine) -> None:
    assert "btree" in _index_method_for_column(
        migrated, "product_document", "text_provenance"
    )
