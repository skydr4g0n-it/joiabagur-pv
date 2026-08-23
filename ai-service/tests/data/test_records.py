"""JSONL contract: required fields, no family/materials/product_id. Delivered by C06b."""

from __future__ import annotations

import json

import pytest

from jbg_ai.data.errors import ValidationError
from jbg_ai.data.records import SyntheticRecord, record_from_json


def _valid_payload() -> dict:
    return {
        "sku": "SKU437",
        "name": "Colgante Fuego S",
        "description": "Una pieza en plata y ónix.",
        "price": "89.00",
        "collection_name": "Fuego",
        "data_origin": "synthetic",
        "text_provenance": "synthetic",
        "text_quality_tier": "rich",
    }


def test_jsonl_omits_family_seed_fields() -> None:
    record = record_from_json(_valid_payload())
    payload = record.to_json_dict()
    dumped = json.loads(json.dumps(payload))
    assert dumped["data_origin"] == "synthetic"
    assert dumped["text_provenance"] == "synthetic"
    for key in ("variant_group_key", "variant_label", "family_seed", "materials", "product_id"):
        assert key not in dumped


def test_record_from_json_rejects_forbidden_keys() -> None:
    for key in ("variant_group_key", "variant_label", "family_seed", "materials", "product_id"):
        payload = {**_valid_payload(), key: "nope"}
        with pytest.raises(ValidationError):
            record_from_json(payload)


def test_synthetic_record_serializes_only_contract_fields() -> None:
    record = SyntheticRecord(
        sku="SKU437",
        name="Anillo",
        description="Plata.",
        price="10.00",
        collection_name="Fuego",
        text_quality_tier="short",
    )
    assert set(record.to_json_dict()) == {
        "sku",
        "name",
        "description",
        "price",
        "collection_name",
        "data_origin",
        "text_provenance",
        "text_quality_tier",
    }
