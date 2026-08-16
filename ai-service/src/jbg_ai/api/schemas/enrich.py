"""Catalog enrichment contracts: proposed profiles with per-field confidence and provenance.

Every proposed value is a suggestion for human or .NET-side review, so the
confidence and the provenance travel with the value instead of in a parallel
structure.

Provenance is not decoration. The consuming side routes a sensitive field to a
human when a model inferred it and exempts it when a deterministic rule produced
it, so a contract without `source` makes that policy unimplementable — which is
why C08 renegotiated this shape before writing a line against it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from jbg_ai.api.schemas.common import TracedResponse, Usage

MAX_BATCH_SIZE = 50

#: Where a proposed value came from. `rule` means a deterministic normalization
#: produced it — a size read off the SKU by regex, an attribute copied from an
#: existing structured field — and `inferred` means a model did.
FieldSource = Literal["rule", "inferred"]


class EnrichProductInput(BaseModel):
    product_id: str = Field(..., min_length=1)
    sku: str = Field(..., min_length=1)
    name: str | None = None
    description: str | None = None
    raw_attributes: dict[str, str] = Field(default_factory=dict)


class EnrichRequest(BaseModel):
    products: list[EnrichProductInput] = Field(..., min_length=1, max_length=MAX_BATCH_SIZE)
    locale: str = Field(default="es-ES")


class ProposedValue(BaseModel):
    """What every proposed field carries besides its value."""

    confidence: float = Field(..., ge=0.0, le=1.0)
    source: FieldSource = Field(
        ..., description="`rule` for a deterministic normalization, `inferred` for a model"
    )


class ProposedText(ProposedValue):
    value: str


class ProposedList(ProposedValue):
    value: list[str] = Field(default_factory=list)


class ProposedProfile(BaseModel):
    """One product's proposed attributes.

    The sensitive fields — `piece_type`, `materials`, `stone_type`, `size_label` —
    are the ones whose error reaches a customer, and each is proposed
    individually so its provenance can be judged individually.

    Commercial tags are split into three lists rather than one flat `tags`,
    matching the columns the vector index already declares: collapsing them here
    would force the split to be reinvented downstream, by whoever needed it first.
    """

    product_id: str
    sku: str
    title: ProposedText | None = None
    description: ProposedText | None = None
    piece_type: ProposedText | None = None
    materials: ProposedList
    stone_type: ProposedText | None = None
    size_label: ProposedText | None = None
    color_tags: ProposedList
    style_tags: ProposedList
    occasion_tags: ProposedList
    family_id: ProposedText | None = None
    variant_label: ProposedText | None = None
    warnings: list[str] = Field(default_factory=list)


class EnrichResponse(TracedResponse):
    profiles: list[ProposedProfile]
    usage: Usage
    prompt_version: str = Field(
        ...,
        description=(
            "Version of the extraction prompt behind this batch. Cheap to emit and impossible "
            "to reconstruct afterwards, which is why it is here rather than deferred"
        ),
    )
