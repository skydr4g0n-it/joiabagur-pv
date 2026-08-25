"""Injectable embedding client that never opens a socket. Delivered by C11."""

from __future__ import annotations

import hashlib

from jbg_ai.indexing.constants import DEFAULT_EMBEDDING_BATCH_SIZE, DEFAULT_EMBEDDING_MODEL, EMBEDDING_DIM
from jbg_ai.indexing.embeddings import EmbedResult, LiteLlmEmbeddingClient


def _fake_vector(text: str, dimension: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [((digest[index % 32] / 127.5) - 1.0) for index in range(dimension)]


class FakeEmbeddingClient:
    """Counts provider batches; reuses the real cache and dimension assert."""

    def __init__(
        self,
        *,
        dimension: int = EMBEDDING_DIM,
        model: str = DEFAULT_EMBEDDING_MODEL,
        batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    ) -> None:
        self.dimension = dimension
        self.provider_calls: list[list[str]] = []

        async def _batch(texts: list[str]) -> list[list[float]]:
            self.provider_calls.append(list(texts))
            return [_fake_vector(text, dimension) for text in texts]

        self._inner = LiteLlmEmbeddingClient(
            api_key="fake-c11",
            model=model,
            batch_size=batch_size,
            embed_batch=_batch,
        )
        self.model_id = self._inner.model_id
        self.document_version_key = self._inner.document_version_key
        self.model_version_key = self._inner.model_version_key

    @property
    def call_count(self) -> int:
        return len(self.provider_calls)

    async def embed(self, texts: list[str]) -> EmbedResult:
        return await self._inner.embed(texts)
