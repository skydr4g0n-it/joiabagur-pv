"""text_provenance, sync_checkpoint, sync_failure cursor columns

Catalog indexer persistence (C13). Hand-written; do not autogenerate — C05
left HNSW/GIN indexes that autogen would rewrite.

* `ai.product_document.text_provenance` NOT NULL + CHECK + B-tree. The table
  is empty, so no backfill. Closed vocabulary is a CHECK, never an ENUM, so a
  revert does not leave an orphaned type.
* `ai.sync_checkpoint`: one row per feed, keyset bookmark. Not `sync_failure`.
* `ai.sync_failure` gains `cursor_since_id` and `product_id` (nullable). No FK
  into `public`.

Revision ID: b8e3c1a4d7f0
Revises: f46c55c056e2
Create Date: 2026-08-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8e3c1a4d7f0"
down_revision: str | None = "f46c55c056e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AI = "ai"


def upgrade() -> None:
    op.add_column(
        "product_document",
        sa.Column("text_provenance", sa.Text(), nullable=False),
        schema=AI,
    )
    op.create_check_constraint(
        "ck_product_document_text_provenance",
        "product_document",
        "text_provenance IN ('merchant', 'ai_assisted', 'synthetic')",
        schema=AI,
    )
    op.create_index(
        "ix_product_document_text_provenance",
        "product_document",
        ["text_provenance"],
        schema=AI,
    )

    op.create_table(
        "sync_checkpoint",
        sa.Column("feed", sa.Text(), primary_key=True),
        sa.Column("watermark", sa.TIMESTAMP(timezone=True)),
        sa.Column("since_id", postgresql.UUID(as_uuid=True)),
        sa.Column("last_full_sync_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("last_incremental_sync_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("last_aggregate_hash", sa.CHAR(64)),
        sa.Column("indexed_count", sa.Integer()),
        schema=AI,
    )

    op.add_column(
        "sync_failure",
        sa.Column("cursor_since_id", postgresql.UUID(as_uuid=True)),
        schema=AI,
    )
    op.add_column(
        "sync_failure",
        sa.Column("product_id", postgresql.UUID(as_uuid=True)),
        schema=AI,
    )


def downgrade() -> None:
    op.drop_column("sync_failure", "product_id", schema=AI)
    op.drop_column("sync_failure", "cursor_since_id", schema=AI)
    op.drop_table("sync_checkpoint", schema=AI)
    op.drop_index(
        "ix_product_document_text_provenance",
        table_name="product_document",
        schema=AI,
    )
    op.drop_constraint(
        "ck_product_document_text_provenance",
        "product_document",
        type_="check",
        schema=AI,
    )
    op.drop_column("product_document", "text_provenance", schema=AI)
