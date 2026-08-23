"""Errors for the C06b synthetic catalog CLI."""


class CatalogDataError(Exception):
    """Base error for generate / ingest / validate."""


class ValidationError(CatalogDataError):
    """A JSONL record or batch failed an invariant."""


class RatioError(CatalogDataError):
    """Quality-tier ratios sit outside the allowed window."""


class GenerateError(CatalogDataError):
    """Generate refused to run or could not talk to the LLM port."""


class IngestError(CatalogDataError):
    """Missing credentials or driver for ingest."""


class IngestAborted(CatalogDataError):
    """Ingest rolled back after a collision or invariant break."""
