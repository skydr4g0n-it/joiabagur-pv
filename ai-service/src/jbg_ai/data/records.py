"""JSONL record for a synthetic catalog product. Delivered by C06b."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from jbg_ai.data.constants import FORBIDDEN_JSON_KEYS, JSONL_FIELDS
from jbg_ai.data.errors import ValidationError
from jbg_ai.data.quality import TextQualityTier


def format_price(value: Decimal | str | float) -> str:
    try:
        quantized = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"Invalid price: {value!r}") from exc
    return f"{quantized:.2f}"


@dataclass(frozen=True)
class SyntheticRecord:
    sku: str
    name: str
    description: str
    price: str
    collection_name: str
    data_origin: Literal["synthetic"] = "synthetic"
    text_provenance: Literal["synthetic"] = "synthetic"
    text_quality_tier: TextQualityTier = "rich"

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "collection_name": self.collection_name,
            "data_origin": self.data_origin,
            "text_provenance": self.text_provenance,
            "text_quality_tier": self.text_quality_tier,
        }


def record_from_json(payload: dict[str, Any]) -> SyntheticRecord:
    extra = [key for key in FORBIDDEN_JSON_KEYS if key in payload]
    if extra:
        raise ValidationError(f"Forbidden JSONL keys present: {extra}.")
    missing = [key for key in JSONL_FIELDS if key not in payload]
    if missing:
        raise ValidationError(f"JSONL line missing keys: {missing}.")
    tier = payload["text_quality_tier"]
    if tier not in {"rich", "sparse", "short"}:
        raise ValidationError(f"Invalid text_quality_tier: {tier!r}.")
    if payload["data_origin"] != "synthetic":
        raise ValidationError("data_origin must be 'synthetic'.")
    if payload["text_provenance"] != "synthetic":
        raise ValidationError("text_provenance must be 'synthetic'.")
    return SyntheticRecord(
        sku=str(payload["sku"]),
        name=str(payload["name"]),
        description="" if payload.get("description") is None else str(payload["description"]),
        price=format_price(payload["price"]),
        collection_name=str(payload["collection_name"]),
        text_quality_tier=tier,
    )
