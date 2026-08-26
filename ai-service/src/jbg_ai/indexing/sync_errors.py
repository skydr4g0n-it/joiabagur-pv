"""Errors raised by the catalog indexer. Distinct from C11 embedding errors."""

from __future__ import annotations


class IndexSyncError(Exception):
    """Base error for catalog index synchronisation."""


class ProvenanceMapError(IndexSyncError):
    """`sku_provenance.json` is missing or unreadable."""


class IndexFeedConfigError(IndexSyncError):
    """A required feed setting is absent, or the catalog feed did not respond."""
