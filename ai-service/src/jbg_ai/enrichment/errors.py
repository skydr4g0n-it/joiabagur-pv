"""Errors raised by the enrichment pipeline. Delivered by C09."""

from __future__ import annotations


class EnrichError(Exception):
    """Base error for the catalog enrichment pipeline."""


class EnrichParseError(EnrichError):
    """The model response was not valid JSON / schema after retry."""


class EnrichConfigError(EnrichError):
    """Runtime settings required for real enrichment are missing."""
