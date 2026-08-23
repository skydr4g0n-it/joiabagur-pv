"""Validators for length, price, SKU and collections. Delivered by C06b."""

from __future__ import annotations

import pytest

from jbg_ai.data.briefs import default_briefs
from jbg_ai.data.errors import ValidationError
from jbg_ai.data.records import SyntheticRecord
from jbg_ai.data.validate import (
    assert_collection_names,
    assert_description_length,
    assert_prices,
    validate_records,
)


def _record(**overrides: object) -> SyntheticRecord:
    values = {
        "sku": "SKU437",
        "name": "Colgante Fuego S",
        "description": "Plata.",
        "price": "89.00",
        "collection_name": "Fuego",
        "text_quality_tier": "rich",
    }
    values.update(overrides)
    return SyntheticRecord(**values)  # type: ignore[arg-type]


def test_description_over_1000_is_rejected() -> None:
    with pytest.raises(ValidationError, match="1000"):
        assert_description_length([_record(description="x" * 1001)])


def test_price_at_or_above_50000_is_rejected() -> None:
    with pytest.raises(ValidationError, match="50000"):
        assert_prices([_record(price="50000.00")])


def test_channel_collection_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="channel"):
        assert_collection_names(
            [_record(collection_name="Hotel")],
            real_collections=set(),
        )


def _ten_collection_records() -> list[SyntheticRecord]:
    briefs = default_briefs()
    records: list[SyntheticRecord] = []
    for index, brief in enumerate(briefs):
        records.append(
            _record(
                sku=f"SKU{437 + index}",
                name=f"Pieza {brief.name}",
                collection_name=brief.name,
            )
        )
    return records


def test_validate_records_accepts_design_collections() -> None:
    validate_records(
        _ten_collection_records(),
        real_skus={"SKU01"},
        real_collections={"Colección Biniacolla"},
    )


def test_empty_collection_name_is_allowed() -> None:
    records = _ten_collection_records()
    records.append(
        _record(
            sku="SKU447",
            name="Colgante suelto",
            collection_name="",
        )
    )
    validate_records(
        records,
        real_skus={"SKU01"},
        real_collections={"Colección Biniacolla"},
        enforce_mix=False,
    )
