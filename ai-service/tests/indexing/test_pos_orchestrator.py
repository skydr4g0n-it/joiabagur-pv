"""POS drain: cursor, checkpoint isolation, per-page failure, CLI surface. C22.

Offline throughout: an injected feed and the in-memory projection. Nothing here opens a
socket, and nothing reads schema `public`.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from jbg_ai.indexing import cli
from jbg_ai.indexing.feed import FeedCursor, PosFeedPage, parse_pos_item
from jbg_ai.indexing.pos_orchestrator import (
    EXHAUSTED_SINCE_ID,
    PosSyncRequest,
    describe,
    resolve_start_cursor,
    resume_position,
    sync_pos_availability,
)
from jbg_ai.indexing.pos_projection import POS_FEED
from jbg_ai.indexing.repository import CATALOG_FEED, SyncCheckpoint
from support.fake_pos_projection import FakePosProjectionRepo

POS_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
PRODUCT_A = uuid.UUID("22222222-2222-2222-2222-222222222222")
PRODUCT_B = uuid.UUID("33333333-3333-3333-3333-333333333333")
INVENTORY_A = uuid.UUID("44444444-4444-4444-4444-444444444444")

AS_OF = datetime(2026, 8, 23, 23, 59, 59, tzinfo=UTC)
WATERMARK = datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 22, 11, 0, 0, tzinfo=UTC)


def run(coro):
    return asyncio.run(coro)


def upsert(product_id: uuid.UUID, watermark: datetime, bucket: str = "1-2"):
    return parse_pos_item(
        {
            "kind": "upsert",
            "pointOfSaleId": str(POS_A),
            "productId": str(product_id),
            "qtyBucket": bucket,
            "isAssignedHint": True,
            "sales30d": 1,
            "sales90d": 2,
            "lastSaleAt": None,
            "watermark": watermark.isoformat(),
        }
    )


def tombstone(product_id: uuid.UUID, at: datetime):
    return parse_pos_item(
        {
            "kind": "tombstone",
            "pointOfSaleId": str(POS_A),
            "productId": str(product_id),
            "reason": "unassigned",
            "at": at.isoformat(),
        }
    )


def page(items, *, next_cursor=None, computed_as_of=AS_OF, aggregate_hash="a" * 64):
    return PosFeedPage(
        items=list(items),
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
        page_size=200,
        aggregate_hash=aggregate_hash,
        computed_as_of=computed_as_of,
    )


class FakePosFeed:
    """Serves prepared pages and records the cursor every request carried."""

    def __init__(self, pages: list[PosFeedPage]) -> None:
        self.pages = pages
        self.requests: list[tuple[datetime | None, uuid.UUID | None]] = []

    async def fetch_catalog_page(self, since, since_id):  # pragma: no cover - never called
        raise AssertionError("the POS drain must not touch the catalog feed")

    async def fetch_pos_page(self, since, since_id) -> PosFeedPage:
        self.requests.append((since, since_id))
        index = min(len(self.requests) - 1, len(self.pages) - 1)
        return self.pages[index]


# --------------------------------------------------------------------------- cursor


def test_a_full_run_ignores_a_stored_cursor() -> None:
    stored = SyncCheckpoint(
        feed=POS_FEED,
        watermark=WATERMARK,
        since_id=INVENTORY_A,
        last_full_sync_at=None,
        last_incremental_sync_at=None,
        last_aggregate_hash=None,
        indexed_count=0,
    )

    assert resolve_start_cursor(PosSyncRequest(full=True), stored) == (None, None)


def test_an_incremental_run_resumes_from_the_stored_cursor() -> None:
    stored = SyncCheckpoint(
        feed=POS_FEED,
        watermark=WATERMARK,
        since_id=INVENTORY_A,
        last_full_sync_at=None,
        last_incremental_sync_at=None,
        last_aggregate_hash=None,
        indexed_count=0,
    )

    assert resolve_start_cursor(PosSyncRequest(), stored) == (WATERMARK, INVENTORY_A)


def test_the_exhausted_cursor_is_the_last_watermark_and_a_zero_id() -> None:
    """The inventory identifier never reaches the client, so it cannot be echoed back.

    The keyset predicate is strictly greater on `(watermark, Inventory.Id)`. A zero
    identifier re-delivers every row sharing that exact watermark — harmless, the writes
    are idempotent — and skips everything older. Storing a product identifier here would
    compare against a different column and silently skip rows.
    """
    exhausted = page([upsert(PRODUCT_A, WATERMARK), upsert(PRODUCT_B, LATER)])

    assert resume_position(exhausted, (None, None)) == (LATER, EXHAUSTED_SINCE_ID)


def test_a_page_with_a_next_cursor_resumes_from_it() -> None:
    cursor = FeedCursor(since=LATER, since_id=INVENTORY_A)
    assert resume_position(page([upsert(PRODUCT_A, WATERMARK)], next_cursor=cursor), (None, None)) == (
        LATER,
        INVENTORY_A,
    )


# --------------------------------------------------------------------------- drain


def test_a_drain_writes_the_page_and_stores_its_own_checkpoint() -> None:
    feed = FakePosFeed([page([upsert(PRODUCT_A, WATERMARK), tombstone(PRODUCT_B, LATER)])])
    repo = FakePosProjectionRepo()

    result = run(sync_pos_availability(PosSyncRequest(full=True), feed=feed, repo=repo))

    assert (result.upserted, result.soft_deleted) == (1, 1)
    assert result.pages == 1
    assert result.computed_as_of == AS_OF
    assert feed.requests == [(None, None)], "a full run starts without query params"

    checkpoint = repo.checkpoints[POS_FEED]
    assert checkpoint.indexed_count == 2
    assert checkpoint.last_full_sync_at is not None
    assert checkpoint.last_incremental_sync_at is not None
    assert checkpoint.last_aggregate_hash == "a" * 64


def test_the_catalog_checkpoint_row_is_never_touched() -> None:
    feed = FakePosFeed([page([upsert(PRODUCT_A, WATERMARK)])])
    repo = FakePosProjectionRepo()
    repo.checkpoints[CATALOG_FEED] = SyncCheckpoint(
        feed=CATALOG_FEED,
        watermark=WATERMARK,
        since_id=INVENTORY_A,
        last_full_sync_at=WATERMARK,
        last_incremental_sync_at=WATERMARK,
        last_aggregate_hash="c" * 64,
        indexed_count=1168,
    )

    run(sync_pos_availability(PosSyncRequest(full=True), feed=feed, repo=repo))

    catalog = repo.checkpoints[CATALOG_FEED]
    assert catalog.watermark == WATERMARK
    assert catalog.indexed_count == 1168
    assert catalog.last_aggregate_hash == "c" * 64
    assert POS_FEED in repo.checkpoints, "the POS cursor lives under its own feed key"


def test_a_second_run_resumes_instead_of_restarting() -> None:
    repo = FakePosProjectionRepo()
    first = FakePosFeed([page([upsert(PRODUCT_A, WATERMARK)])])
    run(sync_pos_availability(PosSyncRequest(full=True), feed=first, repo=repo))

    second = FakePosFeed([page([])])
    run(sync_pos_availability(PosSyncRequest(), feed=second, repo=repo))

    assert second.requests == [(WATERMARK, EXHAUSTED_SINCE_ID)]


def test_full_ignores_the_cursor_the_previous_run_stored() -> None:
    repo = FakePosProjectionRepo()
    first = FakePosFeed([page([upsert(PRODUCT_A, WATERMARK)])])
    run(sync_pos_availability(PosSyncRequest(full=True), feed=first, repo=repo))

    second = FakePosFeed([page([upsert(PRODUCT_A, WATERMARK)])])
    run(sync_pos_availability(PosSyncRequest(full=True), feed=second, repo=repo))

    assert second.requests == [(None, None)]


def test_the_drain_follows_the_next_cursor_across_pages() -> None:
    cursor = FeedCursor(since=WATERMARK, since_id=INVENTORY_A)
    feed = FakePosFeed(
        [
            page([upsert(PRODUCT_A, WATERMARK)], next_cursor=cursor),
            page([upsert(PRODUCT_B, LATER)]),
        ]
    )
    repo = FakePosProjectionRepo()

    result = run(sync_pos_availability(PosSyncRequest(full=True), feed=feed, repo=repo))

    assert result.pages == 2
    assert result.upserted == 2
    assert feed.requests == [(None, None), (WATERMARK, INVENTORY_A)]


# --------------------------------------------------------------------------- failure


def test_a_failed_page_is_recorded_and_the_remaining_pages_still_drain() -> None:
    cursor = FeedCursor(since=WATERMARK, since_id=INVENTORY_A)
    feed = FakePosFeed(
        [
            page([upsert(PRODUCT_A, WATERMARK)], next_cursor=cursor),
            page([upsert(PRODUCT_B, LATER)]),
        ]
    )
    repo = FakePosProjectionRepo(fail_on_page=1)

    result = run(sync_pos_availability(PosSyncRequest(full=True), feed=feed, repo=repo))

    assert result.failed_pages == 1
    assert result.upserted == 1, "the page after the failure still drained"
    assert len(repo.failures) == 1

    failure = repo.failures[0]
    assert failure.feed == POS_FEED
    assert failure.product_id is None, "the unit of failure is a page, not a product"
    assert failure.payload["items"] == 1
    assert "simulated batch failure" in failure.error


def test_a_failed_page_does_not_advance_the_bookmark_past_itself() -> None:
    """A retry has to start before the page that failed, never after it."""
    feed = FakePosFeed([page([upsert(PRODUCT_A, WATERMARK)])])
    repo = FakePosProjectionRepo(fail_on_page=1)

    run(sync_pos_availability(PosSyncRequest(full=True), feed=feed, repo=repo))

    checkpoint = repo.checkpoints[POS_FEED]
    assert checkpoint.watermark is None
    assert checkpoint.since_id is None


# --------------------------------------------------------------------------- CLI


def test_the_cli_exposes_sync_pos_with_full() -> None:
    feed = FakePosFeed([page([upsert(PRODUCT_A, WATERMARK)])])
    repo = FakePosProjectionRepo()

    result = run(
        cli.run_cli_sync_pos(full=True, settings=_settings(), feed=feed, repo=repo)
    )

    assert result.upserted == 1
    assert feed.requests == [(None, None)]


def test_the_cli_reports_counters_without_row_content() -> None:
    line = describe(
        run(
            sync_pos_availability(
                PosSyncRequest(full=True),
                feed=FakePosFeed([page([upsert(PRODUCT_A, WATERMARK)])]),
                repo=FakePosProjectionRepo(),
            )
        )
    )

    assert "upserted=1" in line
    assert "soft_deleted=0" in line
    assert "failed_pages=0" in line
    assert str(PRODUCT_A) not in line


def test_no_v1_route_and_no_scheduler_were_added() -> None:
    """The `/v1` surface is enumerated in a MUST; a drain nobody calls needs no route."""
    from jbg_ai.api.main import create_app
    from support.settings import build_settings

    paths = set(create_app(build_settings()).openapi()["paths"])

    assert not any("pos-availability" in path or "sync-pos" in path for path in paths)
    assert all(not path.startswith("/v1/index/pos") for path in paths)

    import inspect

    from jbg_ai.indexing import pos_orchestrator

    source = inspect.getsource(pos_orchestrator)
    for forbidden in ("create_task", "BackgroundTasks", "APScheduler", "add_event_handler"):
        assert forbidden not in source, f"{forbidden} would be an in-process scheduler"


@pytest.mark.parametrize("command", ["sync-pos"])
def test_the_parser_accepts_the_command(command: str, monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    async def _fake(*, full: bool):
        called["full"] = full
        from jbg_ai.indexing.pos_orchestrator import PosSyncResult

        return PosSyncResult(upserted=3, pages=1)

    monkeypatch.setattr(cli, "run_cli_sync_pos", _fake)

    assert cli.main([command, "--full"]) == 0
    assert called["full"] is True


def _settings():
    from support.settings import build_settings

    return build_settings()
