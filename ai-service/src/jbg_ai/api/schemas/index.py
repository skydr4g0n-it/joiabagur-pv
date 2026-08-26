"""Index synchronisation contracts: upsert counters, keyset cursor and drift status."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from jbg_ai.api.schemas.common import TracedResponse


class IndexSyncRequest(BaseModel):
    since: datetime | None = Field(
        default=None, description="Watermark of the catalog feed keyset; null with since_id null"
    )
    since_id: UUID | None = Field(
        default=None,
        description="Second component of the catalog feed keyset; not required when since is null",
    )
    full: bool = Field(default=False, description="Force a full re-index; ignores body and checkpoint")
    batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Ignored; catalog feed page size is the server-fixed 50",
    )


class IndexSyncResponse(TracedResponse):
    upserted: int = Field(..., ge=0)
    skipped: int = Field(..., ge=0, description="Items whose embedding was omitted")
    deleted: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    since: datetime | None = Field(default=None, description="Watermark the run started from")
    since_id: UUID | None = Field(default=None, description="Keyset id the run started from")
    cursor: datetime | None = Field(default=None, description="Watermark to send on the next sync")
    cursor_id: UUID | None = Field(default=None, description="Keyset id to send on the next sync")


class IndexStatusResponse(TracedResponse):
    indexed_documents: int = Field(..., ge=0)
    drift_count: int = Field(..., ge=0, description="Documents known to be stale")
    last_full_sync_at: datetime | None = None
    last_incremental_sync_at: datetime | None = None
