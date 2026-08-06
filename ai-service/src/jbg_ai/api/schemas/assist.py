"""Sale assistance contracts: family-grouped results plus generated prose.

The `pitch` never contains a resolved price or stock figure — it carries the
`{{price}}` and `{{stock}}` placeholders for the .NET API to substitute.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from jbg_ai.api.schemas.common import ScopedResponse, Usage


class AssistContext(BaseModel):
    """Optional hints the operator can pass along with the query."""

    occasion: str | None = None
    recipient: str | None = None
    preferred_materials: list[str] = Field(default_factory=list)
    notes: str | None = None


class AssistRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20, description="Families wanted after hydration")
    context: AssistContext | None = None
    locale: str = Field(default="es-ES")
    pos_id: str | None = Field(
        default=None,
        description="Accepted for client compatibility and ignored; scope comes from the token",
    )


class AssistGroupMember(BaseModel):
    product_id: str
    sku: str
    variant_label: str | None = Field(default=None, description="Null when the variant is unknown")
    materials: list[str] = Field(default_factory=list)
    score: float = Field(..., ge=0.0, le=1.0)


class AssistGroup(BaseModel):
    """One product family; members are the variants the operator can disambiguate."""

    family_id: str
    family_label: str | None = None
    members: list[AssistGroupMember]


class Citation(BaseModel):
    source: str = Field(..., description="Corpus document or product the claim comes from")
    snippet: str
    product_id: str | None = None


class AssistResponse(ScopedResponse):
    intent: str = Field(..., description="Detected intent, open vocabulary while stubbed")
    groups: list[AssistGroup]
    pitch: str = Field(
        ...,
        description="Generated prose with unresolved {{price}} / {{stock}} placeholders",
    )
    citations: list[Citation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    usage: Usage
