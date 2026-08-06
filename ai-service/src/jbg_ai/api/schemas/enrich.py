"""Catalog enrichment contracts: proposed profiles with per-field confidence.

Every proposed value is a suggestion for human or .NET-side review, so the
confidence travels with the value instead of in a parallel structure.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from jbg_ai.api.schemas.common import TracedResponse, Usage

MAX_BATCH_SIZE = 50


class EnrichProductInput(BaseModel):
    product_id: str = Field(..., min_length=1)
    sku: str = Field(..., min_length=1)
    name: str | None = None
    description: str | None = None
    raw_attributes: dict[str, str] = Field(default_factory=dict)


class EnrichRequest(BaseModel):
    products: list[EnrichProductInput] = Field(..., min_length=1, max_length=MAX_BATCH_SIZE)
    locale: str = Field(default="es-ES")


class ProposedText(BaseModel):
    value: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class ProposedList(BaseModel):
    value: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


class ProposedProfile(BaseModel):
    product_id: str
    sku: str
    title: ProposedText | None = None
    description: ProposedText | None = None
    materials: ProposedList
    family_id: ProposedText | None = None
    variant_label: ProposedText | None = None
    tags: ProposedList
    warnings: list[str] = Field(default_factory=list)


class EnrichResponse(TracedResponse):
    profiles: list[ProposedProfile]
    usage: Usage
