"""In-memory feed, embed and repo fakes. No sockets, no RDS."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from jbg_ai.indexing.constants import DEFAULT_EMBEDDING_MODEL, EMBEDDING_DIM
from jbg_ai.indexing.embeddings import EmbedResult, document_version_key, model_version_key
from jbg_ai.indexing.feed import (
    CatalogFeedPage,
    CatalogTombstoneItem,
    CatalogUpsertItem,
    FeedCursor,
    PosFeedPage,
)
from jbg_ai.indexing.repository import (
    ProductDocumentWrite,
    StoredProductDocument,
    SyncCheckpoint,
    SyncFailureWrite,
)
from jbg_ai.indexing.source_text import ProductSourceText
from jbg_ai.indexing.sync_errors import IndexFeedConfigError


def make_upsert(
    *,
    sku: str,
    product_id: UUID | None = None,
    name: str = "Anillo",
    price: str = "48.00",
    price_band: str = "0-50",
    family_name: str | None = None,
    watermark: datetime | None = None,
) -> CatalogUpsertItem:
    return CatalogUpsertItem(
        kind="upsert",
        product_id=product_id or uuid4(),
        source_text=ProductSourceText(sku=sku, name=name, family_name=family_name),
        family_id=None,
        price=Decimal(price),
        price_band=price_band,
        is_active=True,
        watermark=watermark or datetime(2026, 8, 26, 10, 0, tzinfo=UTC),
    )


def make_tombstone(
    product_id: UUID,
    *,
    reason: str = "deactivated",
    at: datetime | None = None,
) -> CatalogTombstoneItem:
    return CatalogTombstoneItem(
        kind="tombstone",
        product_id=product_id,
        reason=reason,
        at=at or datetime(2026, 8, 26, 11, 0, tzinfo=UTC),
    )


def make_page(
    items: list[CatalogUpsertItem | CatalogTombstoneItem],
    *,
    next_cursor: FeedCursor | None = None,
    aggregate_hash: str = "0" * 64,
    page_size: int = 50,
) -> CatalogFeedPage:
    return CatalogFeedPage(
        items=list(items),
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
        page_size=page_size,
        aggregate_hash=aggregate_hash,
    )


class FakeIndexFeedClient:
    def __init__(
        self,
        pages: list[CatalogFeedPage] | None = None,
        *,
        fail: bool = False,
    ) -> None:
        self.pages = list(pages or [])
        self.catalog_calls: list[tuple[datetime | None, UUID | None]] = []
        self.pos_calls: list[tuple[datetime | None, UUID | None]] = []
        self.fail = fail
        self._index = 0

    async def fetch_catalog_page(
        self, since: datetime | None, since_id: UUID | None
    ) -> CatalogFeedPage:
        self.catalog_calls.append((since, since_id))
        if self.fail:
            raise IndexFeedConfigError("catalog feed is unavailable")
        if self._index >= len(self.pages):
            return make_page([], next_cursor=None, aggregate_hash="")
        page = self.pages[self._index]
        self._index += 1
        return page

    async def fetch_pos_page(
        self, since: datetime | None, since_id: UUID | None
    ) -> PosFeedPage:
        self.pos_calls.append((since, since_id))
        raise AssertionError("POS feed must not be called during catalog sync")


class FakeEmbeddingClient:
    def __init__(
        self,
        *,
        dimension: int = EMBEDDING_DIM,
        fail: bool = False,
    ) -> None:
        self.dimension = dimension
        self.fail = fail
        self.calls: list[list[str]] = []
        self.model_id = DEFAULT_EMBEDDING_MODEL
        self.document_version_key = document_version_key(self.model_id)
        self.model_version_key = model_version_key(self.model_id)

    async def embed(self, texts: list[str]) -> EmbedResult:
        self.calls.append(list(texts))
        if self.fail:
            raise RuntimeError("embed failed")
        vectors = [[0.01] * self.dimension for _ in texts]
        return EmbedResult(
            vectors=vectors,
            embedding_model=self.model_id,
            embedding_version=self.document_version_key,
            cache_hits=0,
        )


def _from_write(
    document: ProductDocumentWrite, embedding: list[float] | None
) -> StoredProductDocument:
    return StoredProductDocument(
        product_id=document.product_id,
        sku=document.sku,
        name=document.name,
        collection_name=document.collection_name,
        price=document.price,
        price_band=document.price_band,
        piece_type=document.piece_type,
        stone_type=document.stone_type,
        size_label=document.size_label,
        materials=list(document.materials),
        family_id=document.family_id,
        family_name=document.family_name,
        variant_label=document.variant_label,
        color_tags=list(document.color_tags),
        style_tags=list(document.style_tags),
        occasion_tags=list(document.occasion_tags),
        doc_text=document.doc_text,
        source_hash=document.source_hash,
        embedding=list(embedding) if embedding is not None else None,
        is_active=document.is_active,
        data_origin=document.data_origin,
        text_provenance=document.text_provenance,
        embedding_model=document.embedding_model,
        embedding_version=document.embedding_version,
        indexed_at=document.indexed_at,
        tsv=f"tsv:{document.doc_text}",
    )


class FakeProductDocumentRepo:
    def __init__(self) -> None:
        self.documents: dict[UUID, StoredProductDocument] = {}
        self.checkpoint: SyncCheckpoint | None = None
        self.failures: list[SyncFailureWrite] = []

    async def get_by_product_id(self, product_id: UUID) -> StoredProductDocument | None:
        return self.documents.get(product_id)

    async def upsert_with_embedding(
        self, document: ProductDocumentWrite, embedding: list[float]
    ) -> None:
        self.documents[document.product_id] = _from_write(document, embedding)

    async def update_columns(self, document: ProductDocumentWrite) -> None:
        previous = self.documents[document.product_id]
        stored = _from_write(document, previous.embedding)
        stored.embedding_model = previous.embedding_model
        stored.embedding_version = previous.embedding_version
        if document.embedding_model is not None:
            stored.embedding_model = document.embedding_model
        if document.embedding_version is not None:
            stored.embedding_version = document.embedding_version
        self.documents[document.product_id] = stored

    async def delete(self, product_id: UUID) -> int:
        if product_id not in self.documents:
            return 0
        del self.documents[product_id]
        return 1

    async def list_product_ids(self) -> list[UUID]:
        return list(self.documents)

    async def count(self) -> int:
        return len(self.documents)

    async def get_checkpoint(self, feed: str) -> SyncCheckpoint | None:
        if self.checkpoint is None or self.checkpoint.feed != feed:
            return None
        return self.checkpoint

    async def put_checkpoint(self, checkpoint: SyncCheckpoint) -> None:
        self.checkpoint = checkpoint

    async def insert_sync_failure(self, failure: SyncFailureWrite) -> None:
        self.failures.append(failure)
