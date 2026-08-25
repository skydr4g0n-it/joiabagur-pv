"""Embedding port, in-memory cache and LiteLLM adapter. Frozen by C11.

C13 persists `document_version_key`. C14 compares `model_version_key`.
C23 reuses this module and must not edit it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from jbg_ai.indexing.constants import (
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    EMBED_BACKOFF_BASE_SECONDS,
    EMBEDDING_DIM,
    MAX_EMBED_ATTEMPTS,
    SOURCE_TEXT_VERSION,
)
from jbg_ai.indexing.errors import EmbeddingConfigError, EmbeddingDimensionError, EmbeddingError
from jbg_ai.indexing.source_text import hash_source_text

logger = logging.getLogger(__name__)

EmbedBatchFn = Callable[[list[str]], Awaitable[list[list[float]]]]
SleepFn = Callable[[float], Awaitable[None]]


@dataclass
class EmbedResult:
    vectors: list[list[float]]
    embedding_model: str
    embedding_version: str
    cache_hits: int


class EmbeddingClient(Protocol):
    """Injectable embedding port. Implementations must not call EnrichLlm."""

    model_id: str
    document_version_key: str
    model_version_key: str

    async def embed(self, texts: list[str]) -> EmbedResult: ...


class InMemoryEmbeddingCache:
    """Process-local cache keyed by `(sha256(text), model, version)`. No TTL."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str, str], list[float]] = {}

    def get(self, text: str, model: str, version: str) -> list[float] | None:
        return self._store.get((hash_source_text(text), model, version))

    def put(self, text: str, model: str, version: str, vector: list[float]) -> None:
        self._store[(hash_source_text(text), model, version)] = vector


def document_version_key(model: str) -> str:
    return f"{model}:{EMBEDDING_DIM}:{SOURCE_TEXT_VERSION}"


def model_version_key(model: str) -> str:
    return f"{model}:{EMBEDDING_DIM}"


def require_embedding_dimension(vectors: Sequence[Sequence[float]]) -> None:
    """Reject any vector that would not fit `vector(1536)`."""
    for vector in vectors:
        if len(vector) != EMBEDDING_DIM:
            raise EmbeddingDimensionError(
                f"embedding dimension is {len(vector)}, expected {EMBEDDING_DIM}"
            )


def _is_retryable(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    if isinstance(status, int) and 500 <= status < 600:
        return True
    return type(exc).__name__ in {
        "RateLimitError",
        "ServiceUnavailableError",
        "InternalServerError",
        "Timeout",
        "APIConnectionError",
        "APITimeoutError",
    }


def _backoff_seconds(attempt: int) -> float:
    return EMBED_BACKOFF_BASE_SECONDS * (2**attempt)


def _vectors_from_response(response: object) -> list[list[float]]:
    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response["data"]
    if data is None:
        raise EmbeddingDimensionError("embedding response has no data")
    vectors: list[list[float]] = []
    for item in data:
        raw = item["embedding"] if isinstance(item, dict) else item.embedding
        vectors.append([float(value) for value in raw])
    return vectors


@dataclass
class LiteLlmEmbeddingClient:
    """LiteLLM `aembedding` adapter: batch, backoff, cache, assert 1536."""

    api_key: str | None
    model: str = DEFAULT_EMBEDDING_MODEL
    base_url: str | None = None
    batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE
    cache: InMemoryEmbeddingCache = field(default_factory=InMemoryEmbeddingCache)
    embed_batch: EmbedBatchFn | None = None
    sleep: SleepFn = field(default=asyncio.sleep)
    max_attempts: int = MAX_EMBED_ATTEMPTS

    def __post_init__(self) -> None:
        self.model_id = self.model
        self.document_version_key = document_version_key(self.model)
        self.model_version_key = model_version_key(self.model)
        if self.batch_size < 1:
            raise EmbeddingConfigError("JPV_EMBEDDING_BATCH_SIZE must be >= 1")

    async def embed(self, texts: list[str]) -> EmbedResult:
        if not self.api_key or not str(self.api_key).strip():
            raise EmbeddingConfigError(
                "JPV_EMBEDDING_API_KEY is required to embed; "
                "it is not interchangeable with JPV_RAG_LLM_API_KEY"
            )

        version = self.document_version_key
        vectors: list[list[float] | None] = [None] * len(texts)
        hits = 0
        misses: list[str] = []
        miss_indices: list[int] = []
        for index, text in enumerate(texts):
            cached = self.cache.get(text, self.model_id, version)
            if cached is not None:
                vectors[index] = cached
                hits += 1
            else:
                misses.append(text)
                miss_indices.append(index)

        logger.info(
            "embedding embed n=%s cache_hits=%s cache_misses=%s model=%s version=%s",
            len(texts),
            hits,
            len(misses),
            self.model_id,
            version,
        )

        if misses:
            fresh = await self._embed_uncached(misses)
            require_embedding_dimension(fresh)
            if len(fresh) != len(misses):
                raise EmbeddingDimensionError(
                    f"provider returned {len(fresh)} vectors for {len(misses)} texts"
                )
            for index, text, vector in zip(miss_indices, misses, fresh, strict=True):
                self.cache.put(text, self.model_id, version, vector)
                vectors[index] = vector

        resolved = [item for item in vectors if item is not None]
        return EmbedResult(
            vectors=resolved,
            embedding_model=self.model_id,
            embedding_version=version,
            cache_hits=hits,
        )

    async def _embed_uncached(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        size = self.batch_size
        for start in range(0, len(texts), size):
            chunk = texts[start : start + size]
            out.extend(await self._embed_chunk_with_retry(chunk))
        return out

    async def _embed_chunk_with_retry(self, texts: list[str]) -> list[list[float]]:
        last_error: BaseException | None = None
        for attempt in range(self.max_attempts):
            try:
                return await self._embed_chunk(texts)
            except Exception as exc:
                last_error = exc
                if not _is_retryable(exc) or attempt == self.max_attempts - 1:
                    raise
                delay = _backoff_seconds(attempt)
                logger.info(
                    "embedding retry attempt=%s delay_s=%s model=%s",
                    attempt + 1,
                    delay,
                    self.model_id,
                )
                await self.sleep(delay)
        raise EmbeddingError("embedding failed") from last_error

    async def _embed_chunk(self, texts: list[str]) -> list[list[float]]:
        if self.embed_batch is not None:
            return await self.embed_batch(texts)
        from litellm import aembedding

        kwargs: dict[str, object] = {
            "model": self.model_id,
            "input": texts,
            "api_key": self.api_key,
            "num_retries": 0,
        }
        if self.base_url:
            kwargs["api_base"] = self.base_url
        response = await aembedding(**kwargs)
        return _vectors_from_response(response)
