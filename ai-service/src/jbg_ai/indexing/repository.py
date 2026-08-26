"""Injectable product-document persistence. SQLAlchemy Core; no mapped class."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import (
    CHAR,
    Column,
    Integer,
    MetaData,
    Table,
    Text,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.indexing.provenance import DataOrigin, TextProvenance

AI_METADATA = MetaData(schema="ai")
CATALOG_FEED = "catalog"

sync_checkpoint = Table(
    "sync_checkpoint",
    AI_METADATA,
    Column("feed", Text, primary_key=True),
    Column("watermark", TIMESTAMP(timezone=True)),
    Column("since_id", PG_UUID(as_uuid=True)),
    Column("last_full_sync_at", TIMESTAMP(timezone=True)),
    Column("last_incremental_sync_at", TIMESTAMP(timezone=True)),
    Column("last_aggregate_hash", CHAR(64)),
    Column("indexed_count", Integer),
)


@dataclass
class StoredProductDocument:
    product_id: UUID
    sku: str
    name: str
    collection_name: str | None
    price: Decimal | None
    price_band: str | None
    piece_type: str | None
    stone_type: str | None
    size_label: str | None
    materials: list[str]
    family_id: UUID | None
    family_name: str | None
    variant_label: str | None
    color_tags: list[str]
    style_tags: list[str]
    occasion_tags: list[str]
    doc_text: str
    source_hash: str
    embedding: list[float] | None
    is_active: bool
    data_origin: DataOrigin
    text_provenance: TextProvenance
    embedding_model: str | None
    embedding_version: str | None
    indexed_at: datetime | None
    tsv: str | None = None


@dataclass
class ProductDocumentWrite:
    product_id: UUID
    sku: str
    name: str
    collection_name: str | None
    price: Decimal | None
    price_band: str | None
    piece_type: str | None
    stone_type: str | None
    size_label: str | None
    materials: list[str]
    family_id: UUID | None
    family_name: str | None
    variant_label: str | None
    color_tags: list[str]
    style_tags: list[str]
    occasion_tags: list[str]
    doc_text: str
    source_hash: str
    is_active: bool
    data_origin: DataOrigin
    text_provenance: TextProvenance
    embedding_model: str | None
    embedding_version: str | None
    indexed_at: datetime


@dataclass
class SyncCheckpoint:
    feed: str
    watermark: datetime | None
    since_id: UUID | None
    last_full_sync_at: datetime | None
    last_incremental_sync_at: datetime | None
    last_aggregate_hash: str | None
    indexed_count: int


@dataclass
class SyncFailureWrite:
    feed: str
    cursor_since: datetime | None
    cursor_since_id: UUID | None
    product_id: UUID | None
    payload: dict[str, Any]
    error: str


class ProductDocumentRepo(Protocol):
    async def get_by_product_id(self, product_id: UUID) -> StoredProductDocument | None: ...

    async def upsert_with_embedding(
        self, document: ProductDocumentWrite, embedding: list[float]
    ) -> None: ...

    async def update_columns(self, document: ProductDocumentWrite) -> None: ...

    async def delete(self, product_id: UUID) -> int: ...

    async def list_product_ids(self) -> list[UUID]: ...

    async def count(self) -> int: ...

    async def get_checkpoint(self, feed: str) -> SyncCheckpoint | None: ...

    async def put_checkpoint(self, checkpoint: SyncCheckpoint) -> None: ...

    async def insert_sync_failure(self, failure: SyncFailureWrite) -> None: ...


_UPSERT_SQL = text(
    """
    INSERT INTO ai.product_document (
        product_id, sku, name, collection_name, price, price_band, piece_type,
        stone_type, size_label, materials, family_id, family_name, variant_label,
        color_tags, style_tags, occasion_tags, doc_text, source_hash, embedding,
        is_active, data_origin, text_provenance, embedding_model, embedding_version,
        indexed_at
    ) VALUES (
        :product_id, :sku, :name, :collection_name, :price, :price_band, :piece_type,
        :stone_type, :size_label, CAST(:materials AS text[]), :family_id, :family_name,
        :variant_label, CAST(:color_tags AS text[]), CAST(:style_tags AS text[]),
        CAST(:occasion_tags AS text[]), :doc_text, :source_hash, CAST(:embedding AS vector),
        :is_active, :data_origin, :text_provenance, :embedding_model, :embedding_version,
        :indexed_at
    )
    ON CONFLICT (product_id) DO UPDATE SET
        sku = EXCLUDED.sku,
        name = EXCLUDED.name,
        collection_name = EXCLUDED.collection_name,
        price = EXCLUDED.price,
        price_band = EXCLUDED.price_band,
        piece_type = EXCLUDED.piece_type,
        stone_type = EXCLUDED.stone_type,
        size_label = EXCLUDED.size_label,
        materials = EXCLUDED.materials,
        family_id = EXCLUDED.family_id,
        family_name = EXCLUDED.family_name,
        variant_label = EXCLUDED.variant_label,
        color_tags = EXCLUDED.color_tags,
        style_tags = EXCLUDED.style_tags,
        occasion_tags = EXCLUDED.occasion_tags,
        doc_text = EXCLUDED.doc_text,
        source_hash = EXCLUDED.source_hash,
        embedding = EXCLUDED.embedding,
        is_active = EXCLUDED.is_active,
        data_origin = EXCLUDED.data_origin,
        text_provenance = EXCLUDED.text_provenance,
        embedding_model = EXCLUDED.embedding_model,
        embedding_version = EXCLUDED.embedding_version,
        indexed_at = EXCLUDED.indexed_at
    """
)

_UPDATE_COLUMNS_SQL = text(
    """
    UPDATE ai.product_document SET
        sku = :sku,
        name = :name,
        collection_name = :collection_name,
        price = :price,
        price_band = :price_band,
        piece_type = :piece_type,
        stone_type = :stone_type,
        size_label = :size_label,
        materials = CAST(:materials AS text[]),
        family_id = :family_id,
        family_name = :family_name,
        variant_label = :variant_label,
        color_tags = CAST(:color_tags AS text[]),
        style_tags = CAST(:style_tags AS text[]),
        occasion_tags = CAST(:occasion_tags AS text[]),
        doc_text = :doc_text,
        source_hash = :source_hash,
        is_active = :is_active,
        data_origin = :data_origin,
        text_provenance = :text_provenance,
        indexed_at = :indexed_at
    WHERE product_id = :product_id
    """
)


def _write_params(document: ProductDocumentWrite) -> dict[str, Any]:
    return {
        "product_id": document.product_id,
        "sku": document.sku,
        "name": document.name,
        "collection_name": document.collection_name,
        "price": document.price,
        "price_band": document.price_band,
        "piece_type": document.piece_type,
        "stone_type": document.stone_type,
        "size_label": document.size_label,
        "materials": document.materials,
        "family_id": document.family_id,
        "family_name": document.family_name,
        "variant_label": document.variant_label,
        "color_tags": document.color_tags,
        "style_tags": document.style_tags,
        "occasion_tags": document.occasion_tags,
        "doc_text": document.doc_text,
        "source_hash": document.source_hash,
        "is_active": document.is_active,
        "data_origin": document.data_origin,
        "text_provenance": document.text_provenance,
        "embedding_model": document.embedding_model,
        "embedding_version": document.embedding_version,
        "indexed_at": document.indexed_at,
    }


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"


class SqlAlchemyProductDocumentRepo:
    """Core implementation over the existing engine (pool 5, max_overflow=0)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def get_by_product_id(self, product_id: UUID) -> StoredProductDocument | None:
        async with session_scope(self._settings) as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT product_id, sku, name, collection_name, price, price_band,
                               piece_type, stone_type, size_label, materials, family_id,
                               family_name, variant_label, color_tags, style_tags,
                               occasion_tags, doc_text, source_hash, embedding::text,
                               is_active, data_origin, text_provenance, embedding_model,
                               embedding_version, indexed_at, tsv::text AS tsv
                        FROM ai.product_document
                        WHERE product_id = :product_id
                        """
                    ),
                    {"product_id": product_id},
                )
            ).mappings().first()
        if row is None:
            return None
        return _row_to_stored(dict(row))

    async def upsert_with_embedding(
        self, document: ProductDocumentWrite, embedding: list[float]
    ) -> None:
        params = _write_params(document)
        params["embedding"] = _vector_literal(embedding)
        async with session_scope(self._settings) as session:
            await session.execute(_UPSERT_SQL, params)

    async def update_columns(self, document: ProductDocumentWrite) -> None:
        async with session_scope(self._settings) as session:
            await session.execute(_UPDATE_COLUMNS_SQL, _write_params(document))

    async def delete(self, product_id: UUID) -> int:
        async with session_scope(self._settings) as session:
            result = await session.execute(
                text("DELETE FROM ai.product_document WHERE product_id = :product_id"),
                {"product_id": product_id},
            )
        return result.rowcount or 0

    async def list_product_ids(self) -> list[UUID]:
        async with session_scope(self._settings) as session:
            rows = (
                await session.execute(text("SELECT product_id FROM ai.product_document"))
            ).scalars().all()
        return [UUID(str(item)) for item in rows]

    async def count(self) -> int:
        async with session_scope(self._settings) as session:
            value = (
                await session.execute(text("SELECT count(*) FROM ai.product_document"))
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
                text(
                    """
                    INSERT INTO ai.sync_failure (
                        feed, cursor_since, cursor_since_id, product_id, payload,
                        error, attempts, next_retry_at
                    ) VALUES (
                        :feed, :cursor_since, :cursor_since_id, :product_id,
                        CAST(:payload AS jsonb), :error, 1, now() + interval '5 minutes'
                    )
                    """
                ),
                {
                    "feed": failure.feed,
                    "cursor_since": failure.cursor_since,
                    "cursor_since_id": failure.cursor_since_id,
                    "product_id": failure.product_id,
                    "payload": json.dumps(failure.payload, default=str),
                    "error": failure.error,
                },
            )


def _parse_vector(value: object) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [float(item) for item in value]
    text_value = str(value).strip().strip("[]")
    if not text_value:
        return []
    return [float(item) for item in text_value.split(",")]


def _parse_text_array(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _row_to_stored(row: dict[str, Any]) -> StoredProductDocument:
    return StoredProductDocument(
        product_id=UUID(str(row["product_id"])),
        sku=str(row["sku"]),
        name=str(row["name"]),
        collection_name=row.get("collection_name"),
        price=Decimal(str(row["price"])) if row.get("price") is not None else None,
        price_band=row.get("price_band"),
        piece_type=row.get("piece_type"),
        stone_type=row.get("stone_type"),
        size_label=row.get("size_label"),
        materials=_parse_text_array(row.get("materials")),
        family_id=UUID(str(row["family_id"])) if row.get("family_id") else None,
        family_name=row.get("family_name"),
        variant_label=row.get("variant_label"),
        color_tags=_parse_text_array(row.get("color_tags")),
        style_tags=_parse_text_array(row.get("style_tags")),
        occasion_tags=_parse_text_array(row.get("occasion_tags")),
        doc_text=str(row["doc_text"]),
        source_hash=str(row["source_hash"]).strip(),
        embedding=_parse_vector(row.get("embedding")),
        is_active=bool(row["is_active"]),
        data_origin=row["data_origin"],
        text_provenance=row["text_provenance"],
        embedding_model=row.get("embedding_model"),
        embedding_version=row.get("embedding_version"),
        indexed_at=row.get("indexed_at"),
        tsv=row.get("tsv"),
    )
