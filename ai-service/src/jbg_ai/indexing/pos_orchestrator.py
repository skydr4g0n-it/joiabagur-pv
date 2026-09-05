"""POS availability drain: feed page → typed items → `ai.pos_projection`, page by page.

Deliberately not part of the catalog drain, and not merely as tidiness. The two feeds have
independent cursors, and sharing `ai.sync_checkpoint` would make each drain rewind the other
every time it ran. They also fail differently: the catalog drain can lose one product to an
embedding provider and carry on, while this one embeds nothing and its unit of failure is a
whole page of assignments.

There is no scheduler here and no `/v1` route. Freshness is not bought with a hidden cron:
the retrieval response reports how old the projection is, and acts on it.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable
from uuid import UUID

from jbg_ai.indexing.feed import (
    IndexFeedClient,
    PosFeedItem,
    PosFeedPage,
    PosTombstoneItem,
)
from jbg_ai.indexing.pos_projection import POS_FEED, PosProjectionRepo
from jbg_ai.indexing.repository import SyncCheckpoint, SyncFailureWrite

logger = logging.getLogger(__name__)

Clock = Callable[[], float]

#: The keyset of this feed is `(watermark, Inventory.Id)`, and the inventory identifier
#: never reaches the client. On the last page there is no `nextCursor` to store, so the
#: resume position becomes `(last watermark seen, this)`. The predicate is strictly greater,
#: so a run resuming there re-delivers every row sharing that exact watermark — idempotent,
#: by construction — and skips everything older. Storing a product identifier here instead
#: would compare against a different column entirely and silently skip rows.
EXHAUSTED_SINCE_ID = UUID(int=0)


@dataclass
class PosSyncRequest:
    full: bool = False
    since: datetime | None = None
    since_id: UUID | None = None


def new_trace_id() -> str:
    """A correlation id for one drain.

    The retrieval path takes its `trace_id` from the token; a drain has no inbound request
    to take one from, and "there is nobody to correlate with" is not the same as "nothing to
    correlate". One run writes 34 pages and can fail on any of them, so without an id the
    entries of two overlapping runs — a cron firing while somebody runs it by hand — are
    indistinguishable in the log.
    """
    return f"sync-pos-{uuid.uuid4().hex[:12]}"


@dataclass
class PosSyncResult:
    upserted: int = 0
    soft_deleted: int = 0
    pages: int = 0
    failed_pages: int = 0
    computed_as_of: datetime | None = None
    cursor: datetime | None = None
    cursor_id: UUID | None = None


def _now() -> datetime:
    return datetime.now(tz=UTC)


def resolve_start_cursor(
    request: PosSyncRequest,
    checkpoint: SyncCheckpoint | None,
) -> tuple[datetime | None, UUID | None]:
    """Precedence: full > complete body keyset > checkpoint > full.

    The same rule the catalog drain follows, so an operator does not have to remember two.
    """
    if request.full:
        return None, None
    if request.since is not None and request.since_id is not None:
        return request.since, request.since_id
    if checkpoint is not None and (
        checkpoint.watermark is not None or checkpoint.since_id is not None
    ):
        return checkpoint.watermark, checkpoint.since_id
    return None, None


def item_watermark(item: PosFeedItem) -> datetime:
    """When this assignment last moved. Items arrive ordered by it, ascending."""
    return item.at if isinstance(item, PosTombstoneItem) else item.watermark


def resume_position(
    page: PosFeedPage,
    fallback: tuple[datetime | None, UUID | None],
) -> tuple[datetime | None, UUID | None]:
    """Where the next run should start after this page was applied."""
    if page.next_cursor is not None:
        return page.next_cursor.since, page.next_cursor.since_id
    if page.items:
        return max(item_watermark(item) for item in page.items), EXHAUSTED_SINCE_ID
    return fallback


def page_failure_payload(
    page: PosFeedPage, cursor: tuple[datetime | None, UUID | None]
) -> dict[str, object]:
    """What a failed batch records. Counts and the cursor, never a page of rows."""
    since, since_id = cursor
    return {
        "feed": POS_FEED,
        "items": len(page.items),
        "since": since.isoformat() if since else None,
        "sinceId": str(since_id) if since_id else None,
        "aggregateHash": page.aggregate_hash,
    }


async def sync_pos_availability(
    request: PosSyncRequest,
    *,
    feed: IndexFeedClient,
    repo: PosProjectionRepo,
    time_budget_seconds: float = 180,
    clock: Clock | None = None,
    trace_id: str | None = None,
) -> PosSyncResult:
    """Drain POS pages until `nextCursor` is null or the time budget elapses."""
    tick = clock or time.monotonic
    started = tick()
    trace = trace_id or new_trace_id()

    checkpoint = await repo.get_checkpoint(POS_FEED)
    start_since, start_since_id = resolve_start_cursor(request, checkpoint)
    is_full = request.full or (start_since is None and start_since_id is None)

    result = PosSyncResult()
    cursor_since, cursor_id = start_since, start_since_id
    resume: tuple[datetime | None, UUID | None] = (cursor_since, cursor_id)
    last_hash = checkpoint.last_aggregate_hash if checkpoint else ""

    while True:
        page = await feed.fetch_pos_page(cursor_since, cursor_id)
        result.pages += 1
        last_hash = page.aggregate_hash or last_hash
        if page.computed_as_of is not None:
            result.computed_as_of = page.computed_as_of

        applied = True
        if page.items:
            try:
                upserted, soft_deleted = await repo.apply_page(
                    page.items,
                    computed_as_of=page.computed_as_of,
                    refreshed_at=_now(),
                )
            except Exception as exc:  # noqa: BLE001 - one page must not end the drain
                # Recorded and skipped rather than raised. A page that fails is a page to
                # retry from `ai.sync_failure`; aborting here would leave every later page
                # undrained because of one bad batch.
                applied = False
                result.failed_pages += 1
                logger.warning(
                    "stage=pos_sync trace_id=%s page_failed page=%s since=%s items=%s "
                    "error=%s",
                    trace,
                    result.pages,
                    cursor_since,
                    len(page.items),
                    exc,
                    extra={"trace_id": trace},
                )
                await repo.insert_sync_failure(
                    SyncFailureWrite(
                        feed=POS_FEED,
                        cursor_since=cursor_since,
                        cursor_since_id=cursor_id,
                        product_id=None,
                        payload=page_failure_payload(page, (cursor_since, cursor_id)),
                        error=str(exc),
                    )
                )
            else:
                result.upserted += upserted
                result.soft_deleted += soft_deleted

        if applied:
            # Only a page that was actually written moves the bookmark — but a *later* page
            # that succeeds does move it past a failed one, and that is deliberate: a drain
            # that refused to advance would let one permanently bad page block every page
            # after it, for ever. The failed page is therefore not recovered by the cursor.
            # It is recovered from `ai.sync_failure`, which stores its exact keyset, or by a
            # `--full` run. Saying otherwise here would be a comment that reads like a
            # guarantee and is not one.
            resume = resume_position(page, resume)

        await _persist_checkpoint(
            repo,
            is_full=is_full,
            cursor=resume,
            aggregate_hash=last_hash or "",
            previous=checkpoint,
        )
        result.cursor, result.cursor_id = resume

        if page.next_cursor is None:
            logger.info(
                "stage=pos_sync trace_id=%s done pages=%s upserted=%s soft_deleted=%s "
                "failed_pages=%s computed_as_of=%s",
                trace,
                result.pages,
                result.upserted,
                result.soft_deleted,
                result.failed_pages,
                result.computed_as_of.isoformat() if result.computed_as_of else None,
                extra={"trace_id": trace},
            )
            return result

        cursor_since = page.next_cursor.since
        cursor_id = page.next_cursor.since_id

        if tick() - started >= time_budget_seconds:
            logger.warning(
                "stage=pos_sync trace_id=%s budget_exhausted pages=%s upserted=%s",
                trace,
                result.pages,
                result.upserted,
                extra={"trace_id": trace},
            )
            return result


async def _persist_checkpoint(
    repo: PosProjectionRepo,
    *,
    is_full: bool,
    cursor: tuple[datetime | None, UUID | None],
    aggregate_hash: str,
    previous: SyncCheckpoint | None,
) -> None:
    """Write the POS cursor. Never touches the `catalog` row: a different `feed` key.

    `last_incremental_sync_at` is bumped on every run, full or not. It answers *when did we
    last look*, which is what the retrieval freshness guard reads; leaving it untouched on a
    full run would make the first drain of a fresh deployment report an unbounded age and
    degrade the very request it just made serviceable.
    """
    indexed = await repo.count()
    now = _now()
    await repo.put_checkpoint(
        SyncCheckpoint(
            feed=POS_FEED,
            watermark=cursor[0],
            since_id=cursor[1],
            last_full_sync_at=(
                now if is_full else (previous.last_full_sync_at if previous else None)
            ),
            last_incremental_sync_at=now,
            last_aggregate_hash=aggregate_hash or None,
            indexed_count=indexed,
        )
    )


def describe(result: PosSyncResult) -> str:
    """One line of counters for the CLI. No row content, no identifiers."""
    as_of = result.computed_as_of.isoformat() if result.computed_as_of else "none"
    return (
        f"upserted={result.upserted} soft_deleted={result.soft_deleted} "
        f"pages={result.pages} failed_pages={result.failed_pages} computed_as_of={as_of}"
    )
