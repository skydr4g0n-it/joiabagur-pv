"""CLI: `python -m jbg_ai.indexing sync [--full]`. Same drain as POST /v1/index/sync."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

import httpx

from jbg_ai.config.settings import Settings, get_settings
from jbg_ai.indexing.constants import DEFAULT_EMBEDDING_MODEL
from jbg_ai.indexing.embeddings import EmbeddingClient, LiteLlmEmbeddingClient
from jbg_ai.indexing.feed import FEED_TIMEOUT_SECONDS, HttpxIndexFeedClient, IndexFeedClient
from jbg_ai.indexing.orchestrator import CatalogSyncRequest, CatalogSyncResult, sync_catalog
from jbg_ai.indexing.provenance import ProvenanceEntry, load_provenance_map
from jbg_ai.indexing.repository import ProductDocumentRepo, SqlAlchemyProductDocumentRepo
from jbg_ai.indexing.sync_errors import IndexFeedConfigError, ProvenanceMapError


async def run_cli_sync(
    *,
    full: bool = False,
    settings: Settings | None = None,
    feed: IndexFeedClient | None = None,
    embed: EmbeddingClient | None = None,
    repo: ProductDocumentRepo | None = None,
    provenance_map: dict[str, ProvenanceEntry] | None = None,
) -> CatalogSyncResult:
    resolved = settings or get_settings()
    mapping = provenance_map if provenance_map is not None else load_provenance_map()
    if feed is not None and embed is not None and repo is not None:
        return await sync_catalog(
            CatalogSyncRequest(full=full),
            feed=feed,
            embed=embed,
            repo=repo,
            provenance_map=mapping,
            time_budget_seconds=resolved.jpv_index_sync_time_budget_seconds,
        )
    if not resolved.jpv_index_feed_base_url:
        raise IndexFeedConfigError("JPV_INDEX_FEED_BASE_URL")
    if not resolved.jpv_index_feed_api_key:
        raise IndexFeedConfigError("JPV_INDEX_FEED_API_KEY")
    if not resolved.jpv_embedding_api_key:
        raise IndexFeedConfigError("JPV_EMBEDDING_API_KEY")
    async with httpx.AsyncClient(
        base_url=resolved.jpv_index_feed_base_url.rstrip("/"),
        timeout=FEED_TIMEOUT_SECONDS,
    ) as client:
        live_feed = feed or HttpxIndexFeedClient(client, resolved.jpv_index_feed_api_key)
        live_embed = embed or LiteLlmEmbeddingClient(
            api_key=resolved.jpv_embedding_api_key,
            model=resolved.jpv_embedding_model or DEFAULT_EMBEDDING_MODEL,
            base_url=resolved.jpv_embedding_base_url,
            batch_size=resolved.jpv_embedding_batch_size,
        )
        live_repo = repo or SqlAlchemyProductDocumentRepo(resolved)
        return await sync_catalog(
            CatalogSyncRequest(full=full),
            feed=live_feed,
            embed=live_embed,
            repo=live_repo,
            provenance_map=mapping,
            time_budget_seconds=resolved.jpv_index_sync_time_budget_seconds,
        )


def run_module(argv: Sequence[str] | None = None) -> int:
    """Process entry point for `python -m jbg_ai.indexing`.

    Loads `backend/.env` — the same file Compose interpolates, and the single place
    the local credentials live — before any setting is read. Until this existed the
    command silently depended on the variables already being exported by hand, while
    `python -m jbg_ai.data` had been loading them since C06b.

    It lives here and not inside `main` on purpose: tests call `main` directly, and
    `support.settings.build_settings` pins the optional fields to `None` precisely so
    that a developer's exported credentials cannot make an "absent configuration" case
    stop failing as it should. Loading the file from a code path a test can reach would
    undo that guarantee.
    """
    from jbg_ai.data.envload import load_local_env

    load_local_env()
    return main(argv)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m jbg_ai.indexing")
    sub = parser.add_subparsers(dest="command", required=True)
    sync_parser = sub.add_parser("sync", help="Drain the catalog index feed")
    sync_parser.add_argument(
        "--full",
        action="store_true",
        help="Ignore checkpoint and body cursor; start without query params",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command != "sync":
        parser.error("unknown command")
    try:
        result = asyncio.run(run_cli_sync(full=args.full))
    except (IndexFeedConfigError, ProvenanceMapError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    sys.stdout.write(
        f"upserted={result.upserted} skipped={result.skipped} "
        f"deleted={result.deleted} failed={result.failed}\n"
    )
    return 0
