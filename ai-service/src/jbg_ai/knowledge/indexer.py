"""Idempotent indexing of the knowledge corpus into the two C05 tables. Delivered by C23.

**No schema object is created, altered or dropped here.** `ai.knowledge_document` and
`ai.knowledge_chunk` have existed with their final shape since C05, and every field this
change would otherwise need lives in `metadata jsonb`, which already carries its GIN index.

Four properties, and the reason each one is not the obvious alternative:

**Identity is deterministic, and it is not the position.** `uuid5` over the slug for a
document and over `<documento>#<sección>` for a chunk. The unique constraint on
`(document_id, chunk_index)` makes the pair look like a natural key, and it is a trap:
inserting a section in the middle shifts the index of every later one and **silently
repoints every later citation** — no error, no visible change, and the worst failure a
system of attribution can have.

**Reordering is handled, not hoped for.** Because `chunk_index` is still written and is
still unique per document, swapping two sections would collide mid-upsert. The surviving
rows are therefore parked in a negative scratch range inside the same transaction before
the final indices are written.

**The embedding version is this package's own.** `knowledge_version_key` is computed here
and `indexing.embeddings.document_version_key` is deliberately not imported: that one seals
`source-text/v1`, the version of the *product* text renderer. Sharing it would mean a change
to the product text marks the whole knowledge corpus stale — waste, but visible — and, far
worse, that a change to these chunking rules would invalidate nothing, leaving vectors that
report themselves current while describing a text that no longer exists.

**The embedding client is injected and never modified.** `indexing/embeddings.py` is frozen
by C11 and says so in its own docstring; it is imported for its type and reused as it is.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.indexing.constants import EMBEDDING_DIM
from jbg_ai.indexing.embeddings import EmbeddingClient
from jbg_ai.knowledge.chunking import KnowledgeChunk, chunk_document, citation_id
from jbg_ai.knowledge.constants import KNOWLEDGE_NAMESPACE, KNOWLEDGE_PREPROCESSING_VERSION
from jbg_ai.knowledge.corpus import KnowledgeCorpus
from jbg_ai.knowledge.errors import KnowledgeIndexError

logger = logging.getLogger(__name__)


def document_id(document_slug: str) -> UUID:
    """`uuid5` over the document slug. Stable across reindexing, and across machines."""
    return uuid.uuid5(KNOWLEDGE_NAMESPACE, document_slug)


def chunk_id(document_slug: str, section_slug: str) -> UUID:
    """`uuid5` over `<documento>#<sección>`, the same pair the citation names."""
    return uuid.uuid5(KNOWLEDGE_NAMESPACE, citation_id(document_slug, section_slug))


def knowledge_version_key(model: str) -> str:
    """`<modelo>:<dimensión>:knowledge/v1`. Computed here on purpose — see the module docstring."""
    return f"{model}:{EMBEDDING_DIM}:{KNOWLEDGE_PREPROCESSING_VERSION}"


@dataclass(frozen=True)
class ExistingChunk:
    """What the database already holds for one chunk, and only what decides re-embedding."""

    id: UUID
    content_hash: str | None
    embedding_version: str | None
    has_embedding: bool


@dataclass(frozen=True)
class DocumentWrite:
    id: UUID
    doc_type: str
    title: str
    source_ref: str | None


@dataclass(frozen=True)
class ChunkWrite:
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    metadata: dict[str, Any]
    indexed_at: datetime
    embedding: list[float] | None = None
    embedding_model: str | None = None
    embedding_version: str | None = None

    @property
    def writes_embedding(self) -> bool:
        return self.embedding is not None


class KnowledgeRepo(Protocol):
    """Injectable persistence. Implementations must not read or write schema `public`."""

    async def existing_chunks(self, document_id: UUID) -> dict[UUID, ExistingChunk]: ...

    async def write_document(
        self,
        document: DocumentWrite,
        chunks: Sequence[ChunkWrite],
        *,
        delete_ids: Sequence[UUID],
    ) -> None:
        """Apply one document atomically: prune, park indices, upsert."""
        ...

    async def prune_documents(self, keep_ids: Sequence[UUID]) -> int:
        """Delete documents the corpus no longer contains. Chunks follow by cascade."""
        ...


@dataclass
class KnowledgeSyncResult:
    documents: int = 0
    chunks: int = 0
    embedded: int = 0
    skipped: int = 0
    deleted_chunks: int = 0
    deleted_documents: int = 0
    embedding_model: str = ""
    embedding_version: str = ""
    cache_hits: int = 0
    failed: list[str] = field(default_factory=list)


def describe(result: KnowledgeSyncResult) -> str:
    return (
        f"documents={result.documents} chunks={result.chunks} "
        f"embedded={result.embedded} skipped={result.skipped} "
        f"deleted_chunks={result.deleted_chunks} deleted_documents={result.deleted_documents} "
        f"version={result.embedding_version}"
    )


def _needs_embedding(
    chunk: KnowledgeChunk,
    existing: ExistingChunk | None,
    *,
    version: str,
    full: bool,
) -> bool:
    if full or existing is None:
        return True
    if not existing.has_embedding:
        return True
    return existing.content_hash != chunk.content_hash or existing.embedding_version != version


async def sync_knowledge(
    corpus: KnowledgeCorpus,
    *,
    embed: EmbeddingClient,
    repo: KnowledgeRepo,
    full: bool = False,
) -> KnowledgeSyncResult:
    """Index the corpus. Running it twice over an unchanged corpus leaves the same rows.

    `full` does not mean "start from a cursor": there is no feed and no cursor here, the
    corpus in git is the whole truth. It means **re-embed everything**, which is what a
    change of embedding model or a suspicion about the stored vectors calls for.
    """
    version = knowledge_version_key(embed.model_id)
    result = KnowledgeSyncResult(embedding_model=embed.model_id, embedding_version=version)
    now = datetime.now(tz=UTC)

    plans: list[tuple[DocumentWrite, tuple[KnowledgeChunk, ...], list[UUID], list[bool]]] = []
    pending_texts: list[str] = []
    pending_slots: list[tuple[int, int]] = []

    for document in corpus.documents:
        doc_uuid = document_id(document.slug)
        chunks = chunk_document(document)
        produced = {chunk_id(document.slug, chunk.section_slug) for chunk in chunks}
        existing = await repo.existing_chunks(doc_uuid)
        obsolete = [key for key in existing if key not in produced]

        wants: list[bool] = []
        for position, chunk in enumerate(chunks):
            key = chunk_id(document.slug, chunk.section_slug)
            needed = _needs_embedding(chunk, existing.get(key), version=version, full=full)
            wants.append(needed)
            if needed:
                pending_slots.append((len(plans), position))
                pending_texts.append(chunk.content)
            else:
                result.skipped += 1

        plans.append(
            (
                DocumentWrite(
                    id=doc_uuid,
                    doc_type=document.doc_type,
                    title=document.title,
                    source_ref=document.source_ref,
                ),
                chunks,
                obsolete,
                wants,
            )
        )

    vectors: dict[tuple[int, int], list[float]] = {}
    if pending_texts:
        embedded = await embed.embed(pending_texts)
        if len(embedded.vectors) != len(pending_texts):
            raise KnowledgeIndexError(
                f"the embedding client returned {len(embedded.vectors)} vectors for "
                f"{len(pending_texts)} chunks"
            )
        result.cache_hits = embedded.cache_hits
        vectors = dict(zip(pending_slots, embedded.vectors, strict=True))

    for plan_index, (document, chunks, obsolete, wants) in enumerate(plans):
        writes: list[ChunkWrite] = []
        for position, chunk in enumerate(chunks):
            vector = vectors.get((plan_index, position))
            writes.append(
                ChunkWrite(
                    id=chunk_id(chunk.document_slug, chunk.section_slug),
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    metadata=chunk.metadata(),
                    indexed_at=now,
                    embedding=vector,
                    embedding_model=embed.model_id if vector is not None else None,
                    embedding_version=version if vector is not None else None,
                )
            )
            if vector is not None:
                result.embedded += 1

        await repo.write_document(document, writes, delete_ids=obsolete)
        result.documents += 1
        result.chunks += len(writes)
        result.deleted_chunks += len(obsolete)

    result.deleted_documents = await repo.prune_documents([plan[0].id for plan in plans])

    logger.info(
        "stage=knowledge_index documents=%s chunks=%s embedded=%s skipped=%s "
        "deleted_chunks=%s deleted_documents=%s cache_hits=%s version=%s",
        result.documents,
        result.chunks,
        result.embedded,
        result.skipped,
        result.deleted_chunks,
        result.deleted_documents,
        result.cache_hits,
        result.embedding_version,
    )
    return result


_SELECT_CHUNKS_SQL = text(
    """
    SELECT id,
           metadata ->> 'content_hash' AS content_hash,
           embedding_version,
           (embedding IS NOT NULL) AS has_embedding
    FROM ai.knowledge_chunk
    WHERE document_id = :document_id
    """
)

_UPSERT_DOCUMENT_SQL = text(
    """
    INSERT INTO ai.knowledge_document (id, doc_type, title, source_ref)
    VALUES (:id, :doc_type, :title, :source_ref)
    ON CONFLICT (id) DO UPDATE SET
        doc_type = EXCLUDED.doc_type,
        title = EXCLUDED.title,
        source_ref = EXCLUDED.source_ref
    """
)

_DELETE_CHUNKS_SQL = text(
    "DELETE FROM ai.knowledge_chunk WHERE id = ANY(CAST(:ids AS uuid[]))"
)

# The scratch range. `chunk_index` is non-negative for every produced chunk, so parking the
# survivors at `-1 - index` cannot collide with anything the upsert is about to write, and
# the unique constraint stays satisfied at every point inside the transaction.
_PARK_INDEX_SQL = text(
    """
    UPDATE ai.knowledge_chunk
    SET chunk_index = -1 - chunk_index
    WHERE document_id = :document_id AND chunk_index >= 0
    """
)

_UPSERT_CHUNK_WITH_EMBEDDING_SQL = text(
    """
    INSERT INTO ai.knowledge_chunk (
        id, document_id, chunk_index, content, metadata,
        embedding, embedding_model, embedding_version, indexed_at
    ) VALUES (
        :id, :document_id, :chunk_index, :content, CAST(:metadata AS jsonb),
        CAST(:embedding AS vector), :embedding_model, :embedding_version, :indexed_at
    )
    ON CONFLICT (id) DO UPDATE SET
        document_id = EXCLUDED.document_id,
        chunk_index = EXCLUDED.chunk_index,
        content = EXCLUDED.content,
        metadata = EXCLUDED.metadata,
        embedding = EXCLUDED.embedding,
        embedding_model = EXCLUDED.embedding_model,
        embedding_version = EXCLUDED.embedding_version,
        indexed_at = EXCLUDED.indexed_at
    """
)

# The skip path. `embedding`, `embedding_model`, `embedding_version` and `indexed_at` are
# left exactly as they were: the vector is still the vector of this content, and rewriting
# `indexed_at` would make an untouched row look re-indexed.
_UPSERT_CHUNK_KEEPING_EMBEDDING_SQL = text(
    """
    INSERT INTO ai.knowledge_chunk (
        id, document_id, chunk_index, content, metadata
    ) VALUES (
        :id, :document_id, :chunk_index, :content, CAST(:metadata AS jsonb)
    )
    ON CONFLICT (id) DO UPDATE SET
        document_id = EXCLUDED.document_id,
        chunk_index = EXCLUDED.chunk_index,
        content = EXCLUDED.content,
        metadata = EXCLUDED.metadata
    """
)

_PRUNE_DOCUMENTS_SQL = text(
    "DELETE FROM ai.knowledge_document WHERE NOT (id = ANY(CAST(:ids AS uuid[])))"
)


def vector_literal(embedding: Sequence[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"


class SqlAlchemyKnowledgeRepo:
    """SQLAlchemy Core over the existing engine (pool 5, no overflow). No mapped class."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def existing_chunks(self, document_id: UUID) -> dict[UUID, ExistingChunk]:
        try:
            async with session_scope(self._settings) as session:
                rows = (
                    await session.execute(_SELECT_CHUNKS_SQL, {"document_id": document_id})
                ).mappings().all()
        except SQLAlchemyError as exc:
            raise KnowledgeIndexError(f"database query failed: {exc}") from exc
        return {
            UUID(str(row["id"])): ExistingChunk(
                id=UUID(str(row["id"])),
                content_hash=row["content_hash"],
                embedding_version=row["embedding_version"],
                has_embedding=bool(row["has_embedding"]),
            )
            for row in rows
        }

    async def write_document(
        self,
        document: DocumentWrite,
        chunks: Sequence[ChunkWrite],
        *,
        delete_ids: Sequence[UUID],
    ) -> None:
        try:
            async with session_scope(self._settings) as session:
                await session.execute(
                    _UPSERT_DOCUMENT_SQL,
                    {
                        "id": document.id,
                        "doc_type": document.doc_type,
                        "title": document.title,
                        "source_ref": document.source_ref,
                    },
                )
                if delete_ids:
                    await session.execute(
                        _DELETE_CHUNKS_SQL, {"ids": [str(item) for item in delete_ids]}
                    )
                await session.execute(_PARK_INDEX_SQL, {"document_id": document.id})
                for chunk in chunks:
                    params: dict[str, Any] = {
                        "id": chunk.id,
                        "document_id": chunk.document_id,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "metadata": json.dumps(chunk.metadata, ensure_ascii=False),
                    }
                    if chunk.writes_embedding:
                        params.update(
                            {
                                "embedding": vector_literal(chunk.embedding or []),
                                "embedding_model": chunk.embedding_model,
                                "embedding_version": chunk.embedding_version,
                                "indexed_at": chunk.indexed_at,
                            }
                        )
                        await session.execute(_UPSERT_CHUNK_WITH_EMBEDDING_SQL, params)
                    else:
                        await session.execute(_UPSERT_CHUNK_KEEPING_EMBEDDING_SQL, params)
        except SQLAlchemyError as exc:
            raise KnowledgeIndexError(f"database write failed: {exc}") from exc

    async def prune_documents(self, keep_ids: Sequence[UUID]) -> int:
        try:
            async with session_scope(self._settings) as session:
                result = await session.execute(
                    _PRUNE_DOCUMENTS_SQL, {"ids": [str(item) for item in keep_ids]}
                )
        except SQLAlchemyError as exc:
            raise KnowledgeIndexError(f"database write failed: {exc}") from exc
        return int(result.rowcount or 0)
