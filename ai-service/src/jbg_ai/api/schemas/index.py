"""Index synchronisation contracts: upsert counters and drift status."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from jbg_ai.api.schemas.common import TracedResponse


class IndexSyncRequest(BaseModel):
    since: datetime | None = Field(
        default=None, description="Cursor of the previous sync; null requests a full pass"
    )
    full: bool = Field(default=False, description="Force a full re-index")
    batch_size: int = Field(default=100, ge=1, le=1000)


class IndexSyncResponse(TracedResponse):
    upserted: int = Field(..., ge=0)
    skipped: int = Field(..., ge=0)
    deleted: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    since: datetime | None = Field(default=None, description="Cursor the run started from")
    cursor: datetime | None = Field(default=None, description="Cursor to send on the next sync")


class IndexStatusResponse(TracedResponse):
    indexed_documents: int = Field(..., ge=0)
    drift_count: int = Field(..., ge=0, description="Documents known to be stale")
    last_full_sync_at: datetime | None = None
    last_incremental_sync_at: datetime | None = None
