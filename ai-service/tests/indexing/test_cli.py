"""CLI entrypoint shares the catalog drain with the HTTP router."""

from __future__ import annotations

from uuid import UUID

from jbg_ai.indexing.cli import main, run_cli_sync
from support.index_fakes import (
    FakeEmbeddingClient,
    FakeIndexFeedClient,
    FakeProductDocumentRepo,
    make_page,
    make_upsert,
)
from support.settings import build_settings

A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
MAP = {"SKU01": {"data_origin": "real", "text_provenance": "ai_assisted"}}


def test_cli_sync_invokes_same_orchestrator() -> None:
    import asyncio

    item = make_upsert(sku="SKU01", product_id=A)
    feed = FakeIndexFeedClient([make_page([item])])
    embed = FakeEmbeddingClient()
    repo = FakeProductDocumentRepo()
    result = asyncio.run(
        run_cli_sync(
            full=True,
            settings=build_settings(
                stub_mode=False,
                jpv_index_feed_base_url="http://feed.test",
                jpv_index_feed_api_key="k",
                jpv_embedding_api_key="e",
            ),
            feed=feed,
            embed=embed,
            repo=repo,
            provenance_map=MAP,
        )
    )
    assert result.upserted == 1
    assert feed.catalog_calls[0] == (None, None)
    assert feed.pos_calls == []


def test_cli_full_flag_parses() -> None:
    captured: dict[str, object] = {}

    async def _fake_run(*, full: bool, **_kwargs):
        from jbg_ai.indexing.orchestrator import CatalogSyncResult

        captured["full"] = full
        return CatalogSyncResult()

    import jbg_ai.indexing.cli as cli

    original = cli.run_cli_sync
    cli.run_cli_sync = _fake_run  # type: ignore[assignment]
    try:
        assert main(["sync", "--full"]) == 0
        assert captured["full"] is True
        captured.clear()
        assert main(["sync"]) == 0
        assert captured["full"] is False
    finally:
        cli.run_cli_sync = original
