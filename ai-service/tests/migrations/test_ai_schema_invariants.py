"""Integrity the schema enforces by itself. Delivered by C05.

These are the invariants that must hold whatever the writing code believes:
closed vocabularies, a single orientation per co-occurrence pair, cascading
deletes inside the schema, and an embedding that may legitimately be absent.
Each one is a rule the database refuses to break, rather than a rule the next
change has to remember.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.db


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
    connection.execute(
        sa.text(
            """
            INSERT INTO ai.product_document
                (product_id, sku, name, doc_text, source_hash, data_origin, text_provenance)
            VALUES (
                :product_id, :sku, :name, :doc_text, :source_hash, :data_origin,
                :text_provenance
            )
            """
        ),
        values,
    )


def test_product_document_rejects_data_origin_outside_vocabulary(
    migrated: sa.Engine,
) -> None:
    """Every metric is reported broken down by origin (design §8.1.1)."""
    with migrated.begin() as connection, pytest.raises(IntegrityError):
        _insert_product(connection, data_origin="imaginary")


def test_product_document_accepts_row_without_embedding(migrated: sa.Engine) -> None:
    """A document may be upserted before its embedding exists.

    That is what lets C13 separate the upsert from the embedding call instead of
    holding one transaction open across a network round trip.
    """
    with migrated.begin() as connection:
        _insert_product(connection)

    with migrated.connect() as connection:
        stored = connection.execute(
            sa.text("SELECT embedding, tsv IS NOT NULL FROM ai.product_document")
        ).one()

    assert stored[0] is None
    # The generated column is populated by the database regardless.
    assert stored[1] is True


def test_pos_projection_rejects_quantity_outside_bucket_vocabulary(
    migrated: sa.Engine,
) -> None:
    """A bucket, never the exact quantity: the projection can be stale, and an
    exact number invites showing it. The real figure is .NET's to state."""
    with migrated.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(
            sa.text(
                """
                INSERT INTO ai.pos_projection (pos_id, product_id, qty_bucket)
                VALUES (:pos_id, :product_id, '7')
                """
            ),
            {"pos_id": uuid.uuid4(), "product_id": uuid.uuid4()},
        )


def test_co_occurrence_rejects_reversed_pair(migrated: sa.Engine) -> None:
    """Without the orientation rule the same pair is stored twice and C27
    doubles its complementary signal."""
    low, high = sorted([uuid.uuid4(), uuid.uuid4()], key=str)

    with migrated.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(
            sa.text(
                "INSERT INTO ai.co_occurrence (product_a, product_b) "
                "VALUES (:a, :b)"
            ),
            {"a": high, "b": low},
        )


def test_co_occurrence_rejects_the_same_pair_twice(migrated: sa.Engine) -> None:
    """The orientation rule alone is not enough: the pair must also be unique."""
    low, high = sorted([uuid.uuid4(), uuid.uuid4()], key=str)

    with migrated.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO ai.co_occurrence (product_a, product_b) VALUES (:a, :b)"
            ),
            {"a": low, "b": high},
        )

    with migrated.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(
            sa.text(
                "INSERT INTO ai.co_occurrence (product_a, product_b) VALUES (:a, :b)"
            ),
            {"a": low, "b": high},
        )


def test_pos_projection_records_its_own_refresh_instant(migrated: sa.Engine) -> None:
    """C22 reports `projection_age_seconds`, so freshness travels with the row."""
    with migrated.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO ai.pos_projection (pos_id, product_id, qty_bucket)
                VALUES (:pos_id, :product_id, '1-2')
                """
            ),
            {"pos_id": uuid.uuid4(), "product_id": uuid.uuid4()},
        )

    with migrated.connect() as connection:
        refreshed_at = connection.execute(
            sa.text("SELECT refreshed_at FROM ai.pos_projection")
        ).scalar()

    assert refreshed_at is not None
    assert refreshed_at.tzinfo is not None, "freshness must be timezone-aware"


def test_sync_failure_records_enough_context_to_retry(migrated: sa.Engine) -> None:
    """A failed batch must neither block the others nor be lost."""
    with migrated.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO ai.sync_failure
                    (feed, cursor_since, payload, error, attempts, next_retry_at)
                VALUES
                    ('catalog', now(), '{"batch": 3}'::jsonb, 'timeout', 1,
                     now() + interval '5 minutes')
                """
            )
        )

    with migrated.connect() as connection:
        row = connection.execute(
            sa.text(
                "SELECT feed, cursor_since, payload, error, attempts, next_retry_at "
                "FROM ai.sync_failure"
            )
        ).one()

    feed, cursor_since, payload, error, attempts, next_retry_at = row
    assert feed == "catalog"
    assert cursor_since is not None
    assert payload == {"batch": 3}
    assert error == "timeout"
    assert attempts == 1
    assert next_retry_at is not None


def test_deleting_knowledge_document_deletes_its_chunks(migrated: sa.Engine) -> None:
    """Cascade inside `ai` — no application logic involved."""
    document_id = uuid.uuid4()

    with migrated.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO ai.knowledge_document (id, doc_type, title) "
                "VALUES (:id, 'material', 'Plata de ley')"
            ),
            {"id": document_id},
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO ai.knowledge_chunk (id, document_id, chunk_index, content)
                VALUES (:id, :document_id, 0, 'La plata de ley se oxida con la humedad.')
                """
            ),
            {"id": uuid.uuid4(), "document_id": document_id},
        )

    with migrated.begin() as connection:
        connection.execute(
            sa.text("DELETE FROM ai.knowledge_document WHERE id = :id"),
            {"id": document_id},
        )

    with migrated.connect() as connection:
        orphans = connection.execute(
            sa.text("SELECT count(*) FROM ai.knowledge_chunk")
        ).scalar()

    assert orphans == 0


def test_knowledge_chunk_index_is_unique_within_its_document(
    migrated: sa.Engine,
) -> None:
    """A chunking invariant: two fragments cannot claim the same position."""
    document_id = uuid.uuid4()

    with migrated.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO ai.knowledge_document (id, doc_type, title) "
                "VALUES (:id, 'faq', 'Devoluciones')"
            ),
            {"id": document_id},
        )
        connection.execute(
            sa.text(
                "INSERT INTO ai.knowledge_chunk (id, document_id, chunk_index, content) "
                "VALUES (:id, :document_id, 0, 'primero')"
            ),
            {"id": uuid.uuid4(), "document_id": document_id},
        )

    with migrated.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(
            sa.text(
                "INSERT INTO ai.knowledge_chunk (id, document_id, chunk_index, content) "
                "VALUES (:id, :document_id, 0, 'duplicado')"
            ),
            {"id": uuid.uuid4(), "document_id": document_id},
        )
