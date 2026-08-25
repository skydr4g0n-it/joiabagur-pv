"""Canonical `source-text/v1` renderer and SHA-256 hash. Delivered by C11."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jbg_ai.indexing.constants import SOURCE_TEXT_VERSION

_OPTIONAL_SCALARS = (
    "description",
    "collection_name",
    "piece_type",
    "stone_type",
    "size_label",
    "family_name",
    "variant_label",
)


class ProductSourceText(BaseModel):
    """Input for `build_source_text`. No provenance, price or identifiers."""

    model_config = ConfigDict(extra="forbid")

    sku: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str | None = None
    collection_name: str | None = None
    piece_type: str | None = None
    materials: list[str] = Field(default_factory=list)
    stone_type: str | None = None
    size_label: str | None = None
    family_name: str | None = None
    variant_label: str | None = None
    color_tags: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    occasion_tags: list[str] = Field(default_factory=list)

    @field_validator("sku", "name", mode="before")
    @classmethod
    def reject_blank_required(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator(*_OPTIONAL_SCALARS, mode="before")
    @classmethod
    def blank_optional_is_absent(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("materials", "color_tags", "style_tags", "occasion_tags", mode="before")
    @classmethod
    def missing_list_is_empty(cls, value: object) -> object:
        if value is None:
            return []
        return value


def _sorted_join(values: Sequence[str]) -> str | None:
    cleaned = [item.strip() for item in values if item and item.strip()]
    if not cleaned:
        return None
    return ", ".join(sorted(cleaned, key=str.casefold))


def _scalar(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def build_source_text(record: ProductSourceText) -> str:
    """Render `source-text/v1`. Absent fields omit the line; lists are sorted."""
    _ = SOURCE_TEXT_VERSION
    lines: list[str] = [
        f"SKU: {record.sku.strip()}",
        f"Nombre: {record.name.strip()}",
    ]
    optional: list[tuple[str, str | None]] = [
        ("Descripción", _scalar(record.description)),
        ("Colección", _scalar(record.collection_name)),
        ("Tipo", _scalar(record.piece_type)),
        ("Materiales", _sorted_join(record.materials)),
        ("Piedra", _scalar(record.stone_type)),
        ("Talla", _scalar(record.size_label)),
        ("Familia", _scalar(record.family_name)),
        ("Variante", _scalar(record.variant_label)),
        ("Colores", _sorted_join(record.color_tags)),
        ("Estilo", _sorted_join(record.style_tags)),
        ("Ocasiones", _sorted_join(record.occasion_tags)),
    ]
    for label, value in optional:
        if value is not None:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def hash_source_text(doc_text: str) -> str:
    """SHA-256 of the exact UTF-8 `doc_text`, lowercase hex, 64 characters."""
    return hashlib.sha256(doc_text.encode("utf-8")).hexdigest()
