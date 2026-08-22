class CatalogError(Exception):
    """Base error for the offline catalog pipeline."""


class CatalogReadError(CatalogError):
    """Export is unreadable or violates SKU rules."""


class IdentityError(CatalogError):
    """SKU / name / price / collection would change."""


class ValidationError(CatalogError):
    """JSONL or sidecar failed an invariant."""


class RatioError(ValidationError):
    """Product-level quality ratios are outside tolerance."""


class IngestError(CatalogError):
    """Local ingest aborted (invariant, connection, or rowcount)."""


class IngestAborted(IngestError):
    """Transaction rolled back; no description from this run is committed."""
