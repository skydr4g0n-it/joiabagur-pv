"""Pydantic schema the enrichment model must fill. Delivered by C09."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EnrichmentExtraction(BaseModel):
    """Structured extraction for one product. No title, description or family."""

    piece_type: str | None = None
    materials: list[str] = Field(default_factory=list)
    stone_type: str | None = None
    size_label: str | None = None
    color_tags: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    occasion_tags: list[str] = Field(default_factory=list)
    gem_mentioned: bool = False
