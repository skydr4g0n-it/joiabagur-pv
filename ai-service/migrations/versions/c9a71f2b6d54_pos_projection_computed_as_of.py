"""pos_projection.computed_as_of

POS projection persistence (C22). Hand-written; do not autogenerate — C05
left HNSW/GIN indexes that autogen would rewrite.

* `ai.pos_projection.computed_as_of`, nullable, no default. The reference
  instant the feed counted `sales_30d` / `sales_90d` against, stored per row
  and not once per synchronisation: the availability feed is incremental, so a
  pair it does not re-emit keeps the figures the run that wrote it computed.
  One projection can therefore hold rows counted against different instants,
  and only a per-row column can tell them apart.

Additive and reversible. The table is empty when this revision first runs, so
there is no backfill; nullable with no default means no rewrite even when it
is not. No table is created, altered or dropped.

Revision ID: c9a71f2b6d54
Revises: b8e3c1a4d7f0
Create Date: 2026-09-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9a71f2b6d54"
down_revision: str | None = "b8e3c1a4d7f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AI = "ai"


def upgrade() -> None:
    op.add_column(
        "pos_projection",
        sa.Column("computed_as_of", sa.TIMESTAMP(timezone=True)),
        schema=AI,
    )


def downgrade() -> None:
    op.drop_column("pos_projection", "computed_as_of", schema=AI)
