"""In-memory `KnowledgeRepo` that never opens a socket. Delivered by C23."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from jbg_ai.knowledge.indexer import ChunkWrite, DocumentWrite, ExistingChunk


@dataclass
class FakeKnowledgeRepo:
    """Mirrors the real repository's contract, including the delete-then-upsert order."""

    documents: dict[UUID, DocumentWrite] = field(default_factory=dict)
    chunks: dict[UUID, dict[UUID, ChunkWrite]] = field(default_factory=dict)
    deleted: list[UUID] = field(default_factory=list)
    pruned: list[UUID] = field(default_factory=list)

    async def existing_chunks(self, document_id: UUID) -> dict[UUID, ExistingChunk]:
        return {
            key: ExistingChunk(
                id=key,
                content_hash=str(write.metadata.get("content_hash")),
                embedding_version=write.embedding_version,
                has_embedding=write.embedding is not None,
            )
            for key, write in self.chunks.get(document_id, {}).items()
        }

    async def write_document(
        self,
        document: DocumentWrite,
        chunks: Sequence[ChunkWrite],
        *,
        delete_ids: Sequence[UUID],
    ) -> None:
        self.documents[document.id] = document
        stored = self.chunks.setdefault(document.id, {})
        for key in delete_ids:
            stored.pop(key, None)
            self.deleted.append(key)
        for write in chunks:
            previous = stored.get(write.id)
            if write.embedding is None and previous is not None:
                # The skip path: content and metadata are refreshed, the vector and the
                # instant it was computed at are left exactly as they were.
                stored[write.id] = ChunkWrite(
                    id=write.id,
                    document_id=write.document_id,
                    chunk_index=write.chunk_index,
                    content=write.content,
                    metadata=write.metadata,
                    indexed_at=previous.indexed_at,
                    embedding=previous.embedding,
                    embedding_model=previous.embedding_model,
                    embedding_version=previous.embedding_version,
                )
            else:
                stored[write.id] = write

    async def prune_documents(self, keep_ids: Sequence[UUID]) -> int:
        keep = set(keep_ids)
        gone = [key for key in self.documents if key not in keep]
        for key in gone:
            self.documents.pop(key, None)
            self.chunks.pop(key, None)
            self.pruned.append(key)
        return len(gone)

    def all_chunks(self) -> list[ChunkWrite]:
        return [write for stored in self.chunks.values() for write in stored.values()]

    def citation_ids(self) -> set[str]:
        return {str(write.metadata["citation_id"]) for write in self.all_chunks()}
