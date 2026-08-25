"""Constants for canonical source text and embeddings. Delivered by C11."""

from __future__ import annotations

SOURCE_TEXT_VERSION = "source-text/v1"
DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"
DEFAULT_EMBEDDING_BATCH_SIZE = 64
EMBEDDING_DIM = 1536
MAX_EMBED_ATTEMPTS = 3
EMBED_BACKOFF_BASE_SECONDS = 0.25
