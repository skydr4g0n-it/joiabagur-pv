"""POS feed typing and `ai.pos_projection` persistence. Delivered by C22.

The offline half runs against the in-memory fake. The `db` half runs the real SQL against
an ephemeral PostgreSQL, because the two traps this change exists to avoid — deleting a
tombstoned row, and letting a bucket outside the vocabulary through — are both properties
of statements, and a fake that never executed one would prove nothing about either.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from jbg_ai.config.settings import Settings
from jbg_ai.indexing.feed import (
    PosTombstoneItem,
    PosUpsertItem,
    parse_pos_item,
    parse_pos_page,
)
from jbg_ai.indexing.pos_projection import (
    SqlAlchemyPosProjectionRepo,
    tombstone_params,
    upsert_params,
)
from support.async_db import run_db
from support.fake_pos_projection import FakePosProjectionRepo

POS_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
PRODUCT_A = uuid.UUID("22222222-2222-2222-2222-222222222222")
PRODUCT_B = uuid.UUID("33333333-3333-3333-3333-333333333333")

AS_OF = datetime(2026, 8, 23, 23, 59, 59, tzinfo=UTC)
REFRESHED = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)


def run(coro):
    """Drive one coroutine. The suite installs no asyncio plugin, by convention."""
    return asyncio.run(coro)


def repo_for(settings: Settings, database_url: str) -> SqlAlchemyPosProjectionRepo:
    return SqlAlchemyPosProjectionRepo(
        settings.model_copy(update={"database_url": database_url})
    )


def upsert_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "kind": "upsert",
        "pointOfSaleId": str(POS_A),
        "productId": str(PRODUCT_A),
        "qtyBucket": "1-2",
        "isAssignedHint": True,
        "sales30d": 3,
        "sales90d": 7,
        "lastSaleAt": "2026-08-21T09:00:00Z",
        "watermark": "2026-08-22T10:00:00Z",
    }
    payload.update(overrides)
    return payload


def tombstone_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "kind": "tombstone",
        "pointOfSaleId": str(POS_A),
        "productId": str(PRODUCT_A),
        "reason": "unassigned",
        "at": "2026-08-24T10:00:00Z",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- parsing


def test_pos_upsert_maps_camel_case_onto_the_typed_item() -> None:
    item = parse_pos_item(upsert_payload())

    assert isinstance(item, PosUpsertItem)
    assert item.point_of_sale_id == POS_A
    assert item.product_id == PRODUCT_A
    assert item.qty_bucket == "1-2"
    assert item.is_assigned_hint is True
    assert item.sales_30d == 3
    assert item.sales_90d == 7
    assert item.last_sale_at == datetime(2026, 8, 21, 9, 0, tzinfo=UTC)
    assert item.watermark == datetime(2026, 8, 22, 10, 0, tzinfo=UTC)


def test_pos_upsert_accepts_a_pair_that_never_sold() -> None:
    item = parse_pos_item(upsert_payload(lastSaleAt=None, sales30d=0, sales90d=0))

    assert isinstance(item, PosUpsertItem)
    assert item.last_sale_at is None


def test_pos_tombstone_maps_onto_the_typed_item() -> None:
    item = parse_pos_item(tombstone_payload())

    assert isinstance(item, PosTombstoneItem)
    assert item.reason == "unassigned"
    assert item.at == datetime(2026, 8, 24, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize("bucket", ["", "2", "1-3", "many", "0 ", "3+ "])
def test_a_bucket_outside_the_vocabulary_is_rejected_while_parsing(bucket: str) -> None:
    """Rejected here, not left for the database CHECK to abort a batch over."""
    with pytest.raises(ValueError, match="qtyBucket"):
        parse_pos_item(upsert_payload(qtyBucket=bucket))


def test_an_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown POS feed kind"):
        parse_pos_item(upsert_payload(kind="patch"))


def test_page_carries_the_reference_instant() -> None:
    page = parse_pos_page(
        {
            "items": [upsert_payload()],
            "nextCursor": {"since": "2026-08-22T10:00:00Z", "sinceId": str(PRODUCT_A)},
            "hasMore": True,
            "pageSize": 200,
            "aggregateHash": "a" * 64,
            "computedAsOf": "2026-08-23T23:59:59Z",
        }
    )

    assert page.computed_as_of == AS_OF
    assert page.has_more is True
    assert page.next_cursor is not None
    assert len(page.items) == 1


def test_a_page_without_the_reference_instant_is_still_a_page() -> None:
    """A feed older than the field is a legitimate feed; the column is nullable for it."""
    page = parse_pos_page({"items": [upsert_payload()], "pageSize": 200})

    assert page.computed_as_of is None
    assert len(page.items) == 1


# --------------------------------------------------------------------------- binding


def test_upsert_params_refuse_a_bucket_the_schema_would_refuse() -> None:
    item = parse_pos_item(upsert_payload())
    forged = PosUpsertItem(**{**item.__dict__, "qty_bucket": "7"})

    with pytest.raises(ValueError, match="qty_bucket"):
        upsert_params(forged, computed_as_of=AS_OF, refreshed_at=REFRESHED)


def test_tombstone_params_always_bind_the_zero_bucket() -> None:
    item = parse_pos_item(tombstone_payload())
    assert isinstance(item, PosTombstoneItem)

    assert tombstone_params(item, refreshed_at=REFRESHED)["bucket"] == "0"


# --------------------------------------------------------------------------- in-memory


def test_applying_the_same_page_twice_does_not_duplicate() -> None:
    repo = FakePosProjectionRepo()
    items = [parse_pos_item(upsert_payload())]

    run(repo.apply_page(items, computed_as_of=AS_OF, refreshed_at=REFRESHED))
    run(repo.apply_page(items, computed_as_of=AS_OF, refreshed_at=REFRESHED))

    assert run(repo.count()) == 1


def test_the_fake_refuses_what_the_check_constraint_refuses() -> None:
    repo = FakePosProjectionRepo()
    item = parse_pos_item(upsert_payload())
    forged = PosUpsertItem(**{**item.__dict__, "qty_bucket": "9"})

    with pytest.raises(ValueError, match="qty_bucket"):
        run(repo.apply_page([forged], computed_as_of=AS_OF, refreshed_at=REFRESHED))


# --------------------------------------------------------------------------- SQL


@pytest.mark.db
def test_upsert_is_idempotent_and_stores_the_reference_instant(
    migrated: sa.Engine, database_url: str, minimal_settings: Settings
) -> None:
    repo = repo_for(minimal_settings, database_url)
    items = [parse_pos_item(upsert_payload())]

    async def scenario():
        first = await repo.apply_page(
            items, computed_as_of=AS_OF, refreshed_at=REFRESHED
        )
        second = await repo.apply_page(
            items, computed_as_of=AS_OF, refreshed_at=REFRESHED + timedelta(minutes=5)
        )
        return first, second, await repo.count(), await repo.get(POS_A, PRODUCT_A)

    first, second, count, row = run_db(scenario)

    assert first == (1, 0)
    assert second == (1, 0)
    assert count == 1

    assert row is not None
    assert row.qty_bucket == "1-2"
    assert row.is_assigned_hint is True
    assert row.sales_30d == 3
    assert row.computed_as_of == AS_OF
    assert row.refreshed_at == REFRESHED + timedelta(minutes=5)


@pytest.mark.db
def test_the_schema_refuses_a_bucket_outside_the_vocabulary(migrated: sa.Engine) -> None:
    """The parser guards the drain; this pins that the database guards the parser."""
    with migrated.begin() as connection, pytest.raises(sa.exc.IntegrityError):
        connection.execute(
            sa.text(
                "INSERT INTO ai.pos_projection (pos_id, product_id, qty_bucket) "
                "VALUES (:pos, :product, :bucket)"
            ),
            {"pos": POS_A, "product": PRODUCT_A, "bucket": "2"},
        )


@pytest.mark.db
def test_a_tombstone_soft_deletes_and_keeps_the_history(
    migrated: sa.Engine, database_url: str, minimal_settings: Settings
) -> None:
    repo = repo_for(minimal_settings, database_url)
    later = REFRESHED + timedelta(hours=1)

    async def scenario():
        await repo.apply_page(
            [parse_pos_item(upsert_payload())],
            computed_as_of=AS_OF,
            refreshed_at=REFRESHED,
        )
        counts = await repo.apply_page(
            [parse_pos_item(tombstone_payload())],
            computed_as_of=AS_OF,
            refreshed_at=later,
        )
        return counts, await repo.count(), await repo.get(POS_A, PRODUCT_A)

    counts, count, row = run_db(scenario)

    assert counts == (0, 1)
    assert count == 1, "a tombstone must never remove the row"

    assert row is not None
    assert row.is_assigned_hint is False
    assert row.qty_bucket == "0"
    assert row.refreshed_at == later
    assert row.sales_30d == 3, "the row stops being carried, not having sold"
    assert row.computed_as_of == AS_OF


@pytest.mark.db
def test_a_tombstone_for_an_unknown_pair_inserts_the_soft_deleted_row(
    migrated: sa.Engine, database_url: str, minimal_settings: Settings
) -> None:
    """The cursor window can start after the upsert that created the pair."""
    repo = repo_for(minimal_settings, database_url)

    async def scenario():
        await repo.apply_page(
            [parse_pos_item(tombstone_payload(productId=str(PRODUCT_B)))],
            computed_as_of=AS_OF,
            refreshed_at=REFRESHED,
        )
        return await repo.get(POS_A, PRODUCT_B)

    row = run_db(scenario)

    assert row is not None
    assert row.is_assigned_hint is False
    assert row.qty_bucket == "0"
    assert row.sales_30d == 0


@pytest.mark.db
def test_a_reassignment_after_a_tombstone_brings_the_row_back_into_scope(
    migrated: sa.Engine, database_url: str, minimal_settings: Settings
) -> None:
    repo = repo_for(minimal_settings, database_url)

    async def scenario():
        await repo.apply_page(
            [parse_pos_item(tombstone_payload())],
            computed_as_of=AS_OF,
            refreshed_at=REFRESHED,
        )
        await repo.apply_page(
            [parse_pos_item(upsert_payload(qtyBucket="3+"))],
            computed_as_of=AS_OF,
            refreshed_at=REFRESHED + timedelta(hours=2),
        )
        return await repo.get(POS_A, PRODUCT_A)

    row = run_db(scenario)

    assert row is not None
    assert row.is_assigned_hint is True
    assert row.qty_bucket == "3+"
