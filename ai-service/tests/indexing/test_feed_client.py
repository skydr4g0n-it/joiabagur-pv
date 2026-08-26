"""Catalog feed client: mapping and httpx adapter with MockTransport (no sockets)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import httpx
import pytest

from jbg_ai.indexing.feed import (
    CATALOG_PATH,
    FEED_KEY_HEADER,
    HttpxIndexFeedClient,
    POS_PATH,
    parse_catalog_item,
    parse_catalog_page,
)
from jbg_ai.indexing.sync_errors import IndexFeedConfigError


PRODUCT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def test_catalog_upsert_maps_camel_case_onto_source_text() -> None:
    item = parse_catalog_item(
        {
            "kind": "upsert",
            "productId": str(PRODUCT_ID),
            "sku": "SKU01",
            "name": "Pendientes",
            "description": "Mini",
            "collectionName": "Biniacolla",
            "pieceType": "pendientes",
            "materials": ["plata"],
            "stoneType": None,
            "sizeLabel": "mini",
            "familyId": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "familyName": "Erizo",
            "variantLabel": "mini",
            "colorTags": ["plata"],
            "styleTags": ["minimal"],
            "occasionTags": [],
            "price": 48.00,
            "priceBand": "0-50",
            "isActive": True,
            "watermark": "2026-08-26T10:00:00Z",
        }
    )
    assert item.kind == "upsert"
    assert item.product_id == PRODUCT_ID
    assert item.source_text.sku == "SKU01"
    assert item.source_text.collection_name == "Biniacolla"
    assert item.source_text.piece_type == "pendientes"
    assert item.family_id == UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    assert item.price == Decimal("48.0")
    assert item.price_band == "0-50"
    assert item.is_active is True


def test_catalog_tombstone_parses_kind_product_reason_at() -> None:
    item = parse_catalog_item(
        {
            "kind": "tombstone",
            "productId": str(PRODUCT_ID),
            "reason": "deactivated",
            "at": "2026-08-26T12:00:00Z",
        }
    )
    assert item.kind == "tombstone"
    assert item.product_id == PRODUCT_ID
    assert item.reason == "deactivated"
    assert item.at == datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def test_first_catalog_page_omits_query_params() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "items": [],
                "nextCursor": None,
                "hasMore": False,
                "pageSize": 50,
                "aggregateHash": "ab" * 32,
            },
        )

    transport = httpx.MockTransport(handler)

    async def _run() -> None:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://feed.test"
        ) as client:
            feed = HttpxIndexFeedClient(client, api_key="feed-secret-not-jwt")
            page = await feed.fetch_catalog_page(None, None)
            assert page.page_size == 50
            assert page.aggregate_hash == "ab" * 32

    import asyncio

    asyncio.run(_run())
    assert captured[0].url.path == CATALOG_PATH
    assert captured[0].url.query in (b"", b"")
    assert captured[0].headers[FEED_KEY_HEADER] == "feed-secret-not-jwt"


def test_subsequent_catalog_page_sends_since_and_since_id() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "items": [],
                "nextCursor": None,
                "hasMore": False,
                "pageSize": 50,
                "aggregateHash": "cd" * 32,
            },
        )

    async def _run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://feed.test"
        ) as client:
            feed = HttpxIndexFeedClient(client, api_key="k")
            await feed.fetch_catalog_page(
                datetime(2026, 8, 26, 10, 0, tzinfo=UTC), PRODUCT_ID
            )

    import asyncio

    asyncio.run(_run())
    query = str(captured[0].url.query)
    assert "since=" in query
    assert f"sinceId={PRODUCT_ID}" in query


def test_pos_path_is_present_on_the_client() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "items": [],
                "nextCursor": None,
                "hasMore": False,
                "pageSize": 200,
                "aggregateHash": "ef" * 32,
            },
        )

    async def _run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://feed.test"
        ) as client:
            feed = HttpxIndexFeedClient(client, api_key="k")
            await feed.fetch_pos_page(None, None)

    import asyncio

    asyncio.run(_run())
    assert captured[0].url.path == POS_PATH


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown catalog feed kind"):
        parse_catalog_item({"kind": "merge", "productId": str(PRODUCT_ID)})


def test_parse_page_reads_next_cursor() -> None:
    page = parse_catalog_page(
        {
            "items": [],
            "nextCursor": {"since": "2026-08-26T10:00:00Z", "sinceId": str(PRODUCT_ID)},
            "hasMore": True,
            "pageSize": 50,
            "aggregateHash": "11" * 32,
        }
    )
    assert page.next_cursor is not None
    assert page.next_cursor.since_id == PRODUCT_ID
    assert page.has_more is True


def test_catalog_5xx_is_feed_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"title": "down"})

    async def _run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://feed.test"
        ) as client:
            feed = HttpxIndexFeedClient(client, api_key="k")
            await feed.fetch_catalog_page(None, None)

    with pytest.raises(IndexFeedConfigError, match="catalog feed is unavailable"):
        import asyncio

        asyncio.run(_run())


def test_catalog_401_is_not_mapped_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"title": "bad key"})

    async def _run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://feed.test"
        ) as client:
            feed = HttpxIndexFeedClient(client, api_key="k")
            await feed.fetch_catalog_page(None, None)

    with pytest.raises(httpx.HTTPStatusError) as caught:
        import asyncio

        asyncio.run(_run())
    assert caught.value.response.status_code == 401


def test_catalog_transport_error_is_feed_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    async def _run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://feed.test"
        ) as client:
            feed = HttpxIndexFeedClient(client, api_key="k")
            await feed.fetch_catalog_page(None, None)

    with pytest.raises(IndexFeedConfigError, match="catalog feed is unavailable"):
        import asyncio

        asyncio.run(_run())
