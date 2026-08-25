"""Errors raised by the indexing library. Delivered by C11."""

from __future__ import annotations


class EmbeddingError(Exception):
    """Base error for the embedding client."""


class EmbeddingConfigError(EmbeddingError):
    """Runtime settings required to embed are missing."""


class EmbeddingDimensionError(EmbeddingError):
    """A provider vector did not match the frozen 1536-d space."""
