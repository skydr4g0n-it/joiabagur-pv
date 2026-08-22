from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Literal

TextQualityTier = Literal["rich", "sparse", "original"]
TextProvenance = Literal["ai_assisted", "merchant"]


@dataclass(frozen=True)
class SourceRow:
    sku: str
    name: str
    description: str
    price: Decimal
    collection_name: str


@dataclass(frozen=True)
class FamilySeed:
    group_key: str
    member_skus: tuple[str, ...]


@dataclass(frozen=True)
class Grouping:
    variant_group_key: str
    variant_label: str | None
    family_seed: FamilySeed


@dataclass(frozen=True)
class QualityAssignment:
    text_quality_tier: TextQualityTier
    text_provenance: TextProvenance


@dataclass(frozen=True)
class ProductIdentity:
    id: str
    sku: str
    name: str
    price: Decimal
    collection_id: str | None


@dataclass
class EnrichedRecord:
    sku: str
    name: str
    description: str
    price: str
    collection_name: str
    data_origin: Literal["real"]
    text_provenance: TextProvenance
    text_quality_tier: TextQualityTier
    variant_group_key: str
    variant_label: str | None
    family_seed: FamilySeed
    product_id: str | None = field(default=None)

    def to_json_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "collection_name": self.collection_name,
            "data_origin": self.data_origin,
            "text_provenance": self.text_provenance,
            "text_quality_tier": self.text_quality_tier,
        }
        if self.product_id is not None:
            payload["product_id"] = self.product_id
        return payload


def record_from_json(payload: dict[str, Any]) -> EnrichedRecord:
    seed_raw = payload.get("family_seed") or {}
    member_skus = tuple(str(s) for s in seed_raw.get("member_skus") or ())
    group_key = str(seed_raw.get("group_key") or payload.get("variant_group_key") or "")
    return EnrichedRecord(
        sku=str(payload["sku"]),
        name=str(payload["name"]),
        description="" if payload.get("description") is None else str(payload["description"]),
        price=str(payload["price"]),
        collection_name=str(payload.get("collection_name") or ""),
        data_origin="real",
        text_provenance=payload["text_provenance"],
        text_quality_tier=payload["text_quality_tier"],
        variant_group_key=group_key,
        variant_label=payload.get("variant_label"),
        family_seed=FamilySeed(group_key=group_key, member_skus=member_skus),
        product_id=payload.get("product_id"),
    )


def identity_as_dict(identity: ProductIdentity) -> dict[str, Any]:
    return asdict(identity)
