"""In-memory `ai.pos_projection` repository. No sockets, no RDS. Delivered by C22.

It enforces the `qty_bucket` vocabulary the schema enforces with a `CHECK`, so a test that
would fail against PostgreSQL also fails here. A fake that accepted values the database
rejects would be worse than no fake at all: it would turn a schema violation into a green
unit test and a red drain.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from jbg_ai.indexing.feed import (
    QTY_BUCKETS,
    TOMBSTONE_BUCKET,
    PosFeedItem,
    PosTombstoneItem,
    PosUpsertItem,
)
from jbg_ai.indexing.pos_projection import PosProjectionRow
from jbg_ai.indexing.repository import SyncCheckpoint, SyncFailureWrite


class FakePosProjectionRepo:
    """Applies the same writes as the SQL port against an in-memory dictionary."""

    def __init__(self, *, fail_on_page: int | None = None) -> None:
        self.rows: dict[tuple[UUID, UUID], PosProjectionRow] = {}
        self.checkpoints: dict[str, SyncCheckpoint] = {}
        self.failures: list[SyncFailureWrite] = []
        self.pages_applied = 0
        #: One-based index of a page whose write must blow up, for the drain tests.
        self.fail_on_page = fail_on_page

    async def apply_page(
        self,
        items: list[PosFeedItem],
        *,
        computed_as_of: datetime | None,
        refreshed_at: datetime,
    ) -> tuple[int, int]:
        self.pages_applied += 1
        if self.fail_on_page == self.pages_applied:
            raise RuntimeError("simulated batch failure")

        upserted = 0
        soft_deleted = 0
        for item in items:
            if isinstance(item, PosUpsertItem):
                self._upsert(item, computed_as_of, refreshed_at)
                upserted += 1
            elif isinstance(item, PosTombstoneItem):
                self._soft_delete(item, refreshed_at)
                soft_deleted += 1
        return upserted, soft_deleted

    def _upsert(
        self,
        item: PosUpsertItem,
        computed_as_of: datetime | None,
        refreshed_at: datetime,
    ) -> None:
        if item.qty_bucket not in QTY_BUCKETS:
            raise ValueError(f"unknown qty_bucket: {item.qty_bucket!r}")
        self.rows[(item.point_of_sale_id, item.product_id)] = PosProjectionRow(
            pos_id=item.point_of_sale_id,
            product_id=item.product_id,
            is_assigned_hint=item.is_assigned_hint,
            qty_bucket=item.qty_bucket,
            sales_30d=item.sales_30d,
            sales_90d=item.sales_90d,
            last_sale_at=item.last_sale_at,
            refreshed_at=refreshed_at,
            computed_as_of=computed_as_of,
        )

    def _soft_delete(self, item: PosTombstoneItem, refreshed_at: datetime) -> None:
        """Never deletes. Sales history and the reference instant survive untouched."""
        key = (item.point_of_sale_id, item.product_id)
        existing = self.rows.get(key)
        self.rows[key] = PosProjectionRow(
            pos_id=item.point_of_sale_id,
            product_id=item.product_id,
            is_assigned_hint=False,
            qty_bucket=TOMBSTONE_BUCKET,
            sales_30d=existing.sales_30d if existing else 0,
            sales_90d=existing.sales_90d if existing else 0,
            last_sale_at=existing.last_sale_at if existing else None,
            refreshed_at=refreshed_at,
            computed_as_of=existing.computed_as_of if existing else None,
        )

    async def get(self, pos_id: UUID, product_id: UUID) -> PosProjectionRow | None:
        return self.rows.get((pos_id, product_id))

    async def count(self) -> int:
        return len(self.rows)

    async def get_checkpoint(self, feed: str) -> SyncCheckpoint | None:
        return self.checkpoints.get(feed)

    async def put_checkpoint(self, checkpoint: SyncCheckpoint) -> None:
        self.checkpoints[checkpoint.feed] = checkpoint

    async def insert_sync_failure(self, failure: SyncFailureWrite) -> None:
        self.failures.append(failure)
