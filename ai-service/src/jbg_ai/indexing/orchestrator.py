"""Catalog index drain: feed → provenance → skip-embed / upsert / tombstone."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable
from uuid import UUID

from jbg_ai.indexing.constants import EMBEDDING_DIM
from jbg_ai.indexing.embeddings import EmbeddingClient
from jbg_ai.indexing.errors import EmbeddingDimensionError, EmbeddingError
from jbg_ai.indexing.feed import (
    CatalogFeedItem,
    CatalogTombstoneItem,
    CatalogUpsertItem,
    IndexFeedClient,
)
from jbg_ai.indexing.provenance import ProvenanceEntry
from jbg_ai.indexing.repository import (
    CATALOG_FEED,
    ProductDocumentRepo,
    ProductDocumentWrite,
    SyncCheckpoint,
    SyncFailureWrite,
    StoredProductDocument,
)
from jbg_ai.indexing.set_hash import of_product_ids
from jbg_ai.indexing.source_text import build_source_text, hash_source_text
from jbg_ai.indexing.sync_errors import IndexFeedConfigError, ProvenanceMapError

logger = logging.getLogger(__name__)

Clock = Callable[[], float]

_batch_size_warned = False


@dataclass
class CatalogSyncRequest:
    full: bool = False
    since: datetime | None = None
    since_id: UUID | None = None
    batch_size: int | None = None


@dataclass
class CatalogSyncResult:
    upserted: int = 0
    skipped: int = 0
    deleted: int = 0
    failed: int = 0
    since: datetime | None = None
    since_id: UUID | None = None
    cursor: datetime | None = None
    cursor_id: UUID | None = None


def warn_batch_size_ignored(batch_size: int | None) -> None:
    """Emit one process-wide warning: feed page size is C12's 50, not this field."""
    global _batch_size_warned
    if _batch_size_warned:
        return
    _batch_size_warned = True
    logger.warning(
        "batch_size=%s is ignored; catalog feed page size is the server-fixed 50",
        batch_size,
    )


def reset_batch_size_warning() -> None:
    global _batch_size_warned
    _batch_size_warned = False


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _item_cursor(item: CatalogFeedItem) -> tuple[datetime, UUID]:
    if isinstance(item, CatalogTombstoneItem):
        return item.at, item.product_id
    return item.watermark, item.product_id


def _item_payload(item: CatalogFeedItem) -> dict[str, object]:
    if isinstance(item, CatalogTombstoneItem):
        return {
            "kind": item.kind,
            "productId": str(item.product_id),
            "reason": item.reason,
            "at": item.at.isoformat(),
        }
    return {
        "kind": item.kind,
        "productId": str(item.product_id),
        "sku": item.source_text.sku,
    }


def _write_from_upsert(
    item: CatalogUpsertItem,
    *,
    doc_text: str,
    source_hash: str,
    provenance: ProvenanceEntry,
    embedding_model: str | None,
    embedding_version: str | None,
    indexed_at: datetime,
) -> ProductDocumentWrite:
    source = item.source_text
    return ProductDocumentWrite(
        product_id=item.product_id,
        sku=source.sku,
        name=source.name,
        collection_name=source.collection_name,
        price=item.price,
        price_band=item.price_band or None,
        piece_type=source.piece_type,
        stone_type=source.stone_type,
        size_label=source.size_label,
        materials=list(source.materials),
        family_id=item.family_id,
        family_name=source.family_name,
        variant_label=source.variant_label,
        color_tags=list(source.color_tags),
        style_tags=list(source.style_tags),
        occasion_tags=list(source.occasion_tags),
        doc_text=doc_text,
        source_hash=source_hash,
        is_active=item.is_active,
        data_origin=provenance["data_origin"],
        text_provenance=provenance["text_provenance"],
        embedding_model=embedding_model,
        embedding_version=embedding_version,
        indexed_at=indexed_at,
    )


def _has_vector(stored: StoredProductDocument | None) -> bool:
    return stored is not None and stored.embedding is not None and len(stored.embedding) == EMBEDDING_DIM


async def _record_failure(
    repo: ProductDocumentRepo,
    item: CatalogFeedItem,
    error: str,
    cursor: tuple[datetime, UUID] | None,
) -> None:
    watermark, since_id = cursor if cursor is not None else (None, None)
    product_id = item.product_id
    await repo.insert_sync_failure(
        SyncFailureWrite(
            feed=CATALOG_FEED,
            cursor_since=watermark,
            cursor_since_id=since_id,
            product_id=product_id,
            payload=_item_payload(item),
            error=error,
        )
    )


async def _persist_checkpoint(
    repo: ProductDocumentRepo,
    *,
    is_full: bool,
    cursor: tuple[datetime, UUID] | None,
    aggregate_hash: str,
    previous: SyncCheckpoint | None,
) -> None:
    indexed = await repo.count()
    now = _now()
    last_full = now if is_full else (previous.last_full_sync_at if previous else None)
    last_inc = previous.last_incremental_sync_at if previous else None
    if not is_full:
        last_inc = now
    await repo.put_checkpoint(
        SyncCheckpoint(
            feed=CATALOG_FEED,
            watermark=cursor[0] if cursor else None,
            since_id=cursor[1] if cursor else None,
            last_full_sync_at=last_full,
            last_incremental_sync_at=last_inc,
            last_aggregate_hash=aggregate_hash or None,
            indexed_count=indexed,
        )
    )


async def process_upsert(
    item: CatalogUpsertItem,
    *,
    repo: ProductDocumentRepo,
    embed: EmbeddingClient,
    provenance_map: dict[str, ProvenanceEntry],
) -> str:
    """Return 'upserted' or 'skipped'. Raises on isolated item failure."""
    sku = item.source_text.sku
    entry = provenance_map.get(sku)
    if entry is None:
        raise LookupError(f"SKU {sku} is absent from sku_provenance.json")
    doc_text = build_source_text(item.source_text)
    source_hash = hash_source_text(doc_text)
    stored = await repo.get_by_product_id(item.product_id)
    write = _write_from_upsert(
        item,
        doc_text=doc_text,
        source_hash=source_hash,
        provenance=entry,
        embedding_model=stored.embedding_model if stored else None,
        embedding_version=stored.embedding_version if stored else None,
        indexed_at=_now(),
    )
    if stored is not None and stored.source_hash == source_hash and _has_vector(stored):
        write.embedding_model = stored.embedding_model
        write.embedding_version = stored.embedding_version
        await repo.update_columns(write)
        return "skipped"
    result = await embed.embed([doc_text])
    if not result.vectors:
        raise EmbeddingError("embedding provider returned no vectors")
    vector = result.vectors[0]
    if len(vector) != EMBEDDING_DIM:
        raise EmbeddingDimensionError(
            f"embedding dimension is {len(vector)}, expected {EMBEDDING_DIM}"
        )
    write.embedding_model = result.embedding_model
    write.embedding_version = result.embedding_version or embed.document_version_key
    await repo.upsert_with_embedding(write, vector)
    return "upserted"


async def process_item(
    item: CatalogFeedItem,
    *,
    repo: ProductDocumentRepo,
    embed: EmbeddingClient,
    provenance_map: dict[str, ProvenanceEntry],
) -> str:
    if isinstance(item, CatalogTombstoneItem):
        removed = await repo.delete(item.product_id)
        return "deleted" if removed else "noop"
    return await process_upsert(
        item, repo=repo, embed=embed, provenance_map=provenance_map
    )


def resolve_start_cursor(
    request: CatalogSyncRequest,
    checkpoint: SyncCheckpoint | None,
) -> tuple[datetime | None, UUID | None]:
    """Precedence: full > complete body keyset > checkpoint > full."""
    if request.full:
        return None, None
    if request.since is not None and request.since_id is not None:
        return request.since, request.since_id
    if checkpoint is not None and (
        checkpoint.watermark is not None or checkpoint.since_id is not None
    ):
        return checkpoint.watermark, checkpoint.since_id
    return None, None


async def sync_catalog(
    request: CatalogSyncRequest,
    *,
    feed: IndexFeedClient,
    embed: EmbeddingClient,
    repo: ProductDocumentRepo,
    provenance_map: dict[str, ProvenanceEntry] | None,
    time_budget_seconds: float = 180,
    clock: Clock | None = None,
) -> CatalogSyncResult:
    """Drain catalog pages until nextCursor is null or the time budget elapses."""
    if provenance_map is None:
        raise ProvenanceMapError(
            "sku_provenance.json is missing; refusing catalog sync"
        )
    warn_batch_size_ignored(request.batch_size)
    tick = clock or time.monotonic
    started = tick()
    checkpoint = await repo.get_checkpoint(CATALOG_FEED)
    start_since, start_since_id = resolve_start_cursor(request, checkpoint)
    is_full = request.full or (start_since is None and start_since_id is None)
    result = CatalogSyncResult(since=start_since, since_id=start_since_id)
    cursor_since, cursor_id = start_since, start_since_id
    last_ok: tuple[datetime, UUID] | None = None
    last_hash = checkpoint.last_aggregate_hash if checkpoint else ""

    while True:
        page = await feed.fetch_catalog_page(cursor_since, cursor_id)
        last_hash = page.aggregate_hash or last_hash
        if not page.items and page.next_cursor is None:
            await _persist_checkpoint(
                repo,
                is_full=is_full,
                cursor=last_ok,
                aggregate_hash=last_hash or "",
                previous=checkpoint,
            )
            if last_ok:
                result.cursor, result.cursor_id = last_ok
            return result
        for item in page.items:
            try:
                outcome = await process_item(
                    item, repo=repo, embed=embed, provenance_map=provenance_map
                )
            except Exception as exc:
                result.failed += 1
                await _record_failure(repo, item, str(exc), last_ok)
            else:
                if outcome == "upserted":
                    result.upserted += 1
                elif outcome == "skipped":
                    result.skipped += 1
                elif outcome == "deleted":
                    result.deleted += 1
                last_ok = _item_cursor(item)
                await _persist_checkpoint(
                    repo,
                    is_full=is_full,
                    cursor=last_ok,
                    aggregate_hash=last_hash or "",
                    previous=checkpoint,
                )
            if tick() - started >= time_budget_seconds:
                if last_ok:
                    result.cursor, result.cursor_id = last_ok
                return result
        if page.next_cursor is None:
            if last_ok:
                result.cursor, result.cursor_id = last_ok
            return result
        cursor_since = page.next_cursor.since
        cursor_id = page.next_cursor.since_id


@dataclass
class CatalogStatusResult:
    indexed_documents: int
    drift_count: int
    last_full_sync_at: datetime | None
    last_incremental_sync_at: datetime | None


async def report_index_status(
    *,
    feed: IndexFeedClient,
    repo: ProductDocumentRepo,
) -> CatalogStatusResult:
    """One catalog GET. Equal set hashes → drift 0; feed errors → IndexFeedConfigError."""
    ids = await repo.list_product_ids()
    local_hash = of_product_ids(ids)
    try:
        page = await feed.fetch_catalog_page(None, None)
    except Exception as exc:
        raise IndexFeedConfigError("catalog feed is unavailable") from exc
    indexed = await repo.count()
    checkpoint = await repo.get_checkpoint(CATALOG_FEED)
    if local_hash == page.aggregate_hash:
        drift = 0
    else:
        checkpoint_count = checkpoint.indexed_count if checkpoint else 0
        drift = max(1, abs(indexed - checkpoint_count))
    return CatalogStatusResult(
        indexed_documents=indexed,
        drift_count=drift,
        last_full_sync_at=checkpoint.last_full_sync_at if checkpoint else None,
        last_incremental_sync_at=(
            checkpoint.last_incremental_sync_at if checkpoint else None
        ),
    )
