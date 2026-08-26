"""Detectors for the silent failures of the `ai` schema. Delivered by C05.

A test that only checks "the migration applies" is theatre: applying it already
proves that. Every test in this module targets a failure that produces **no
error at all** and would therefore reach September intact:

* an HNSW index whose operator class disagrees with the query operator is simply
  never used — no error, no warning, just a sequential scan that is invisible at
  ~1,500 vectors;
* Alembic's version table landing in `public` breaks the ownership boundary
  without anything complaining;
* an orphaned type surviving a revert breaks the *next* upgrade, weeks later,
  with nothing pointing at the cause;
* a full-text column built with the default configuration searches in English
  and still returns rows.

All of them need a real PostgreSQL, hence `db`. See `conftest.py` for why they
skip rather than fail when Docker is unreachable.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.db

AI = "ai"

EXPECTED_TABLES = {
    "product_document",
    "knowledge_document",
    "knowledge_chunk",
    "pos_projection",
    "co_occurrence",
    "sync_failure",
    "sync_checkpoint",
}

#: Both embedding columns must be reachable by the cosine operator `<=>`.
VECTOR_INDEXES = {
    "ix_product_document_embedding_hnsw": ("product_document", "embedding"),
    "ix_knowledge_chunk_embedding_hnsw": ("knowledge_chunk", "embedding"),
}


def _tables(engine: sa.Engine, schema: str) -> set[str]:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT tablename FROM pg_tables WHERE schemaname = :schema"
            ),
            {"schema": schema},
        )
        return {row[0] for row in rows}


def _index_access_method_and_opclass(
    engine: sa.Engine, index_name: str
) -> tuple[str, str] | None:
    """Read the index's access method and operator class from the catalog.

    Deliberately a catalog join rather than a substring search in
    `pg_indexes.indexdef`. Both detect the defect, because PostgreSQL *omits* an
    operator class from the rendered definition when it is the default one — so
    an L2 index renders as `USING hnsw (embedding)` and a substring check fails.
    But that depends on a rendering rule, while this depends on a fact.
    """
    with engine.connect() as connection:
        return connection.execute(
            sa.text(
                """
                SELECT am.amname, opc.opcname
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indexrelid
                JOIN pg_am am ON am.oid = c.relam
                JOIN pg_opclass opc ON opc.oid = i.indclass[0]
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = :schema AND c.relname = :index
                """
            ),
            {"schema": AI, "index": index_name},
        ).first()


def _index_method_for_column(
    engine: sa.Engine, table: str, column: str
) -> set[str]:
    """Access methods of every index whose leading column is `column`."""
    with engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                """
                SELECT am.amname
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indexrelid
                JOIN pg_class t ON t.oid = i.indrelid
                JOIN pg_am am ON am.oid = c.relam
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


def test_migration_creates_vector_extension_and_ai_schema(migrated: sa.Engine) -> None:
    """The extension, the schema, the six tables — and nothing in `public`."""
    with migrated.connect() as connection:
        extension = connection.execute(
            sa.text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        schema_exists = connection.execute(
            sa.text("SELECT 1 FROM pg_namespace WHERE nspname = :name"),
            {"name": AI},
        ).scalar()

    assert extension is not None, "the `vector` extension was not installed"
    assert schema_exists, "schema `ai` was not created"
    assert EXPECTED_TABLES <= _tables(migrated, AI)


def test_migration_keeps_alembic_bookkeeping_out_of_public(migrated: sa.Engine) -> None:
    """The design boundary says Python never writes to `public`.

    Alembic's default would put `alembic_version` there and nothing would ever
    complain — the project's very first Python migration breaking its own rule.
    """
    assert "alembic_version" in _tables(migrated, AI)
    assert "alembic_version" not in _tables(migrated, "public")


def test_migration_creates_no_table_outside_the_ai_schema(migrated: sa.Engine) -> None:
    """Everything this migration builds belongs to `ai`."""
    public_tables = _tables(migrated, "public")

    assert not (EXPECTED_TABLES & public_tables)
    assert public_tables == set(), (
        "the migration must not create anything in `public`; "
        f"found {sorted(public_tables)}"
    )


@pytest.mark.parametrize(
    ("index_name", "table_and_column"),
    sorted(VECTOR_INDEXES.items()),
)
def test_hnsw_index_uses_cosine_operator_class(
    migrated: sa.Engine, index_name: str, table_and_column: tuple[str, str]
) -> None:
    """The one defect that costs the most and announces itself the least.

    pgvector's default operator class is `vector_l2_ops`. Writing
    `USING hnsw (embedding)` therefore yields an L2 index, and every query using
    the cosine operator `<=>` silently stops using it. `CREATE INDEX` raises
    nothing, the queries keep returning correct rows, and on this corpus the
    latency difference is not even perceptible.
    """
    found = _index_access_method_and_opclass(migrated, index_name)

    assert found is not None, f"index {index_name} does not exist"
    access_method, operator_class = found

    assert access_method == "hnsw"
    assert operator_class == "vector_cosine_ops", (
        f"{index_name} is built with {operator_class!r}; queries use the cosine "
        "operator `<=>`, so this index would never be used and nothing would say so"
    )


def test_gin_index_exists_on_materials(migrated: sa.Engine) -> None:
    """Material filters are overlap and containment over an array (design §7.3).

    Without a GIN index they degrade to a sequential scan — correct results,
    quietly wrong plan.
    """
    assert "gin" in _index_method_for_column(migrated, "product_document", "materials")


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("product_document", "tsv"),
        ("knowledge_chunk", "tsv"),
        ("knowledge_chunk", "metadata"),
    ],
)
def test_gin_index_exists_on_searchable_column(
    migrated: sa.Engine, table: str, column: str
) -> None:
    """Full-text and JSON containment need GIN too (design §7.2)."""
    assert "gin" in _index_method_for_column(migrated, table, column)


@pytest.mark.parametrize(
    "column", ["family_id", "piece_type", "price_band", "data_origin", "text_provenance"]
)
def test_structural_filter_column_has_btree_index(
    migrated: sa.Engine, column: str
) -> None:
    """Structural filters (§7.2) and the reporting dimension of §8.1.1.

    At ~1,500 rows none of these improves a measurable latency. They exist
    because adding them later costs a migration and having them costs nothing.
    """
    assert "btree" in _index_method_for_column(migrated, "product_document", column)


def test_retry_queue_is_indexed(migrated: sa.Engine) -> None:
    """The retry queue is read by due date; without an index it is a table scan."""
    assert "btree" in _index_method_for_column(
        migrated, "sync_failure", "next_retry_at"
    )


@pytest.mark.parametrize(
    ("table", "source"),
    [("product_document", "doc_text"), ("knowledge_chunk", "content")],
)
def test_tsvector_column_is_generated_with_spanish_configuration(
    migrated: sa.Engine, table: str, source: str
) -> None:
    """The language is a fact of the schema, not a convention of the write path.

    The two-argument `to_tsvector` is IMMUTABLE and therefore legal in a
    generated column; the one-argument form depends on the session's
    `default_text_search_config`, which is precisely how the language could
    drift without anyone noticing.
    """
    with migrated.connect() as connection:
        expression = connection.execute(
            sa.text(
                """
                SELECT generation_expression
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = :table
                  AND column_name = 'tsv'
                  AND is_generated = 'ALWAYS'
                """
            ),
            {"schema": AI, "table": table},
        ).scalar()

    assert expression is not None, f"{table}.tsv is not a generated column"
    assert "spanish" in expression
    assert source in expression


def test_ai_schema_declares_no_foreign_key_into_public(migrated: sa.Engine) -> None:
    """Product, POS and family ids are plain uuids on purpose.

    A real constraint would couple this schema to EF Core's tables: a .NET
    migration touching `Products` would start failing on a dependency it never
    knew it had.
    """
    with migrated.connect() as connection:
        crossing = connection.execute(
            sa.text(
                """
                SELECT con.conname, target_ns.nspname
                FROM pg_constraint con
                JOIN pg_namespace n ON n.oid = con.connamespace
                JOIN pg_class target ON target.oid = con.confrelid
                JOIN pg_namespace target_ns ON target_ns.oid = target.relnamespace
                WHERE n.nspname = :schema
                  AND con.contype = 'f'
                  AND target_ns.nspname <> :schema
                """
            ),
            {"schema": AI},
        ).all()

    assert crossing == [], f"foreign keys crossing the schema boundary: {crossing}"


def test_upgrade_downgrade_is_reversible(
    alembic_config: Config, database_url: str
) -> None:
    """Three legs, not two.

    Apply, revert, **apply again**. The third leg is the whole point: without it
    an orphaned type or index survives unnoticed and breaks a future upgrade
    instead of this test.
    """
    command.upgrade(alembic_config, "head")

    engine = sa.create_engine(database_url)
    try:
        assert EXPECTED_TABLES <= _tables(engine, AI)

        command.downgrade(alembic_config, "base")

        assert not (EXPECTED_TABLES & _tables(engine, AI))
        with engine.connect() as connection:
            # The reason closed vocabularies are CHECK constraints and not
            # enumerated types: a type survives dropping its table, and the
            # *next* upgrade then fails with "type already exists" weeks later.
            orphaned_types = connection.execute(
                sa.text(
                    """
                    SELECT t.typname
                    FROM pg_type t
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE n.nspname = :schema AND t.typtype = 'e'
                    """
                ),
                {"schema": AI},
            ).scalars().all()
            assert orphaned_types == [], (
                f"reverting left enumerated types behind: {orphaned_types}"
            )

            # The extension is shared database-wide and the schema holds the
            # version table, so neither is dropped.
            assert connection.execute(
                sa.text("SELECT 1 FROM pg_namespace WHERE nspname = :name"),
                {"name": AI},
            ).scalar()
            assert connection.execute(
                sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).scalar()

        command.upgrade(alembic_config, "head")

        assert EXPECTED_TABLES <= _tables(engine, AI)
    finally:
        engine.dispose()
