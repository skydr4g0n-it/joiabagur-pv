"""Evaluation run contracts. Development profile only — never a product API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from jbg_ai.api.schemas.common import TracedResponse


class EvalMetric(BaseModel):
    name: str = Field(..., description="Metric key, e.g. recall_at_10")
    value: float


class EvalRun(BaseModel):
    run_id: str
    suite: str
    status: str = Field(..., description="Run outcome, e.g. passed or failed")
    started_at: datetime
    finished_at: datetime | None = None
    metrics: list[EvalMetric] = Field(default_factory=list)


class EvalRunsResponse(TracedResponse):
    runs: list[EvalRun]
