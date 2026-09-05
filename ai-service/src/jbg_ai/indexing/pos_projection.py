"""Injectable `ai.pos_projection` persistence. SQLAlchemy Core; no mapped class.

Two rules govern this module and both are easy to get backwards.

**A tombstone is a soft delete, never a `DELETE`.** The feed reports `isAssignedHint`
as true on every upsert it emits — the .NET mapper hardcodes it — so `false` is a value
only this drain can ever write. Deleting the row would make the field permanently
unreachable, and would destroy the only record that tells a product never carried at a
point of sale from one no longer carried there.

**The reference instant is stored per row, not once per run.** The feed is incremental:
a pair whose inventory row does not move is never re-emitted, so it keeps the sales
figures the run that wrote it computed. One projection can hold rows counted against
different instants, and only a per-row column can say which.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.indexing.feed import (
    QTY_BUCKETS,
    TOMBSTONE_BUCKET,
    PosFeedItem,
    PosTombstoneItem,
    PosUpsertItem,
)
from jbg_ai.indexing.repository import SyncCheckpoint, SyncFailureWrite, sync_checkpoint

#: The `feed` value this drain keeps its cursor under. Never `catalog`: the two cursors
#: are independent, and sharing the row would make each drain rewind the other.
POS_FEED = "pos-availability"


@dataclass(frozen=True)
class PosProjectionRow:
    """One stored assignment. `qty_bucket` is a bucket; no exact quantity exists here."""

    pos_id: UUID
    product_id: UUID
    is_assigned_hint: bool
    qty_bucket: str
    sales_30d: int
    sales_90d: int
    last_sale_at: datetime | None
    refreshed_at: datetime
    computed_as_of: datetime | None


class PosProjectionRepo(Protocol):
    """Implementations must not read or write schema `public`."""

    async def apply_page(
        self,
        items: list[PosFeedItem],
        *,
        computed_as_of: datetime | None,
        refreshed_at: datetime,
    ) -> tuple[int, int]:
        """Write one page atomically. Returns `(upserted, soft_deleted)`."""
        ...

    async def get(self, pos_id: UUID, product_id: UUID) -> PosProjectionRow | None: ...

    async def count(self) -> int: ...

    async def get_checkpoint(self, feed: str) -> SyncCheckpoint | None: ...

    async def put_checkpoint(self, checkpoint: SyncCheckpoint) -> None: ...

    async def insert_sync_failure(self, failure: SyncFailureWrite) -> None: ...


_UPSERT_SQL = text(
    """
    INSERT INTO ai.pos_projection (
        pos_id, product_id, is_assigned_hint, qty_bucket, sales_30d, sales_90d,
        last_sale_at, refreshed_at, computed_as_of
    ) VALUES (
        :pos_id, :product_id, :is_assigned_hint, :qty_bucket, :sales_30d, :sales_90d,
        :last_sale_at, :refreshed_at, :computed_as_of
    )
    ON CONFLICT (pos_id, product_id) DO UPDATE SET
        is_assigned_hint = EXCLUDED.is_assigned_hint,
        qty_bucket = EXCLUDED.qty_bucket,
        sales_30d = EXCLUDED.sales_30d,
        sales_90d = EXCLUDED.sales_90d,
        last_sale_at = EXCLUDED.last_sale_at,
        refreshed_at = EXCLUDED.refreshed_at,
        computed_as_of = EXCLUDED.computed_as_of
    """
)

# The soft delete. `sales_*`, `last_sale_at` and `computed_as_of` are deliberately left
# alone: the row stops being in scope, it does not stop having been sold. That history is
# the whole reason the row survives at all.
_SOFT_DELETE_SQL = text(
    """
    INSERT INTO ai.pos_projection (
        pos_id, product_id, is_assigned_hint, qty_bucket, refreshed_at
    ) VALUES (
        :pos_id, :product_id, FALSE, :bucket, :refreshed_at
    )
    ON CONFLICT (pos_id, product_id) DO UPDATE SET
        is_assigned_hint = FALSE,
        qty_bucket = EXCLUDED.qty_bucket,
        refreshed_at = EXCLUDED.refreshed_at
    """
)

_SELECT_ONE_SQL = text(
    """
    SELECT pos_id, product_id, is_assigned_hint, qty_bucket, sales_30d, sales_90d,
           last_sale_at, refreshed_at, computed_as_of
    FROM ai.pos_projection
    WHERE pos_id = :pos_id AND product_id = :product_id
    """
)

_INSERT_FAILURE_SQL = text(
    """
    INSERT INTO ai.sync_failure (
        feed, cursor_since, cursor_since_id, product_id, payload,
        error, attempts, next_retry_at
    ) VALUES (
        :feed, :cursor_since, :cursor_since_id, :product_id,
        CAST(:payload AS jsonb), :error, 1, now() + interval '5 minutes'
    )
    """
)


def upsert_params(
    item: PosUpsertItem,
    *,
    computed_as_of: datetime | None,
    refreshed_at: datetime,
) -> dict[str, Any]:
    """Bind one upsert. Raises on a bucket the contract does not define."""
    if item.qty_bucket not in QTY_BUCKETS:
        raise ValueError(f"unknown qty_bucket: {item.qty_bucket!r}")
    return {
        "pos_id": item.point_of_sale_id,
        "product_id": item.product_id,
        "is_assigned_hint": item.is_assigned_hint,
        "qty_bucket": item.qty_bucket,
        "sales_30d": item.sales_30d,
        "sales_90d": item.sales_90d,
        "last_sale_at": item.last_sale_at,
        "refreshed_at": refreshed_at,
        "computed_as_of": computed_as_of,
    }


def tombstone_params(item: PosTombstoneItem, *, refreshed_at: datetime) -> dict[str, Any]:
    return {
        "pos_id": item.point_of_sale_id,
        "product_id": item.product_id,
        "bucket": TOMBSTONE_BUCKET,
        "refreshed_at": refreshed_at,
    }


class SqlAlchemyPosProjectionRepo:
    """Core implementation over the existing engine (pool 5, max_overflow=0)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def apply_page(
        self,
        items: list[PosFeedItem],
        *,
        computed_as_of: datetime | None,
        refreshed_at: datetime,
    ) -> tuple[int, int]:
        """One transaction per page: 200 statements, not 200 transactions.

        A page is the unit a failure is recorded against, so it is also the unit that
        commits. Per-row transactions against a pool capped at five connections would
        turn a 6.720-row drain into 6.720 round trips for no isolation anyone wanted.
        """
        upserts = [item for item in items if isinstance(item, PosUpsertItem)]
        tombstones = [item for item in items if isinstance(item, PosTombstoneItem)]
        if not upserts and not tombstones:
            return 0, 0

        upsert_rows = [
            upsert_params(item, computed_as_of=computed_as_of, refreshed_at=refreshed_at)
            for item in upserts
        ]
        tombstone_rows = [
            tombstone_params(item, refreshed_at=refreshed_at) for item in tombstones
        ]

        async with session_scope(self._settings) as session:
            if upsert_rows:
                await session.execute(_UPSERT_SQL, upsert_rows)
            if tombstone_rows:
                await session.execute(_SOFT_DELETE_SQL, tombstone_rows)

        return len(upsert_rows), len(tombstone_rows)

    async def get(self, pos_id: UUID, product_id: UUID) -> PosProjectionRow | None:
        async with session_scope(self._settings) as session:
            row = (
                await session.execute(
                    _SELECT_ONE_SQL, {"pos_id": pos_id, "product_id": product_id}
                )
            ).mappings().first()
        return _to_row(dict(row)) if row is not None else None

    async def count(self) -> int:
        async with session_scope(self._settings) as session:
            value = (
                await session.execute(text("SELECT count(*) FROM ai.pos_projection"))
            ).scalar()
        return int(value or 0)

    async def get_checkpoint(self, feed: str) -> SyncCheckpoint | None:
        async with session_scope(self._settings) as session:
            row = (
                await session.execute(
                    select(sync_checkpoint).where(sync_checkpoint.c.feed == feed)
                )
            ).mappings().first()
        if row is None:
            return None
        return SyncCheckpoint(
            feed=str(row["feed"]),
            watermark=row["watermark"],
            since_id=row["since_id"],
            last_full_sync_at=row["last_full_sync_at"],
            last_incremental_sync_at=row["last_incremental_sync_at"],
            last_aggregate_hash=row["last_aggregate_hash"],
            indexed_count=int(row["indexed_count"] or 0),
        )

    async def put_checkpoint(self, checkpoint: SyncCheckpoint) -> None:
        values = {
            "feed": checkpoint.feed,
            "watermark": checkpoint.watermark,
            "since_id": checkpoint.since_id,
            "last_full_sync_at": checkpoint.last_full_sync_at,
            "last_incremental_sync_at": checkpoint.last_incremental_sync_at,
            "last_aggregate_hash": checkpoint.last_aggregate_hash,
            "indexed_count": checkpoint.indexed_count,
        }
        stmt = pg_insert(sync_checkpoint).values(values).on_conflict_do_update(
            index_elements=["feed"],
            set_={key: values[key] for key in values if key != "feed"},
        )
        async with session_scope(self._settings) as session:
            await session.execute(stmt)

    async def insert_sync_failure(self, failure: SyncFailureWrite) -> None:
        async with session_scope(self._settings) as session:
            await session.execute(
                _INSERT_FAILURE_SQL,
                {
                    "feed": failure.feed,
                    "cursor_since": failure.cursor_since,
                    "cursor_since_id": failure.cursor_since_id,
                    "product_id": failure.product_id,
                    "payload": json.dumps(failure.payload, default=str),
                    "error": failure.error,
                },
            )


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _to_row(row: dict[str, Any]) -> PosProjectionRow:
    return PosProjectionRow(
        pos_id=UUID(str(row["pos_id"])),
        product_id=UUID(str(row["product_id"])),
        is_assigned_hint=bool(row["is_assigned_hint"]),
        qty_bucket=str(row["qty_bucket"]),
        sales_30d=int(row["sales_30d"] or 0),
        sales_90d=int(row["sales_90d"] or 0),
        last_sale_at=row.get("last_sale_at"),
        refreshed_at=row["refreshed_at"],
        computed_as_of=row.get("computed_as_of"),
    )
