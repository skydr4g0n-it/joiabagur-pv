"""Inventory proposal contracts: a prioritized list, never quantities.

Python proposes what deserves attention and why; the .NET API decides amounts
because it owns stock.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from jbg_ai.api.schemas.common import ScopedResponse


class InventoryFilters(BaseModel):
    materials: list[str] = Field(default_factory=list)
    category: str | None = None
    family_id: str | None = None


class InventoryProposeRequest(BaseModel):
    horizon_days: int = Field(default=30, ge=1, le=365)
    limit: int = Field(default=10, ge=1, le=50)
    filters: InventoryFilters = Field(default_factory=InventoryFilters)
    pos_id: str | None = Field(
        default=None,
        description="Accepted for client compatibility and ignored; scope comes from the token",
    )


class InventoryProposal(BaseModel):
    product_id: str
    sku: str
    family_id: str | None = Field(default=None, description="Null when the family is unknown")
    variant_label: str | None = Field(default=None, description="Null when the variant is unknown")
    priority: int = Field(..., ge=1, description="1 is the most urgent proposal")
    signal: str = Field(..., description="What triggered the proposal, e.g. coverage_gap")
    rationale: str = Field(
        ...,
        description="Prose rationale; stock figures stay as {{stock}} placeholders",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)


class InventoryProposeResponse(ScopedResponse):
    proposals: list[InventoryProposal]
    horizon_days: int = Field(..., ge=1)
