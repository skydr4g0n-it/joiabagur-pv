from __future__ import annotations

from copy import deepcopy

from catalog_pipeline.assist import draft_description
from catalog_pipeline.errors import ValidationError
from catalog_pipeline.generate import build_records
from catalog_pipeline.models import EnrichedRecord
from catalog_pipeline.validate import (
    assert_data_origin_and_provenance,
    validate_records,
)
import pytest


def _clone(record: EnrichedRecord, **overrides) -> EnrichedRecord:
    payload = record.to_json_dict()
    payload.update(overrides)
    from catalog_pipeline.models import record_from_json

    return record_from_json(payload)


def test_description_over_1000_is_rejected(fixture_records):
    record = _clone(fixture_records[0], description="x" * 1001)
    with pytest.raises(ValidationError, match="1000"):
        validate_records([record])


def test_original_tier_keeps_source_description(fixture_rows):
    row = next(item for item in fixture_rows if item.description)
    copied = draft_description(row, "original")
    assert copied == row.description
    records = build_records(fixture_rows)
    by_sku = {item.sku: item for item in fixture_rows}
    originals = [record for record in records if record.text_quality_tier == "original"]
    for record in originals:
        source = by_sku[record.sku]
        assert record.text_provenance == "merchant"
        assert record.description == source.description
    validate_records(records, source_rows=fixture_rows)


def test_original_tier_rejects_rewritten_text(fixture_records, fixture_rows):
    record = _clone(
        fixture_records[0],
        text_quality_tier="original",
        text_provenance="merchant",
        description="texto reescrito",
    )
    with pytest.raises(ValidationError, match="export Description"):
        validate_records([record], source_rows=fixture_rows)
    dirty = _clone(
        fixture_records[0],
        text_quality_tier="original",
        text_provenance="ai_assisted",
        description=fixture_rows[0].description,
    )
    with pytest.raises(ValidationError):
        validate_records([dirty])


def test_every_product_has_data_origin_and_text_provenance(fixture_records):
    assert_data_origin_and_provenance(fixture_records)
    validate_records(fixture_records)
    broken = deepcopy(fixture_records)
    broken[0].data_origin = "synthetic"  # type: ignore[assignment]
    with pytest.raises(ValidationError, match="data_origin"):
        validate_records(broken)


def test_assisted_copy_does_not_mention_photos_or_source_sheet(fixture_rows):
    records = build_records(fixture_rows)
    validate_records(records, source_rows=fixture_rows)
    forbidden = (
        "fotografía",
        "foto",
        "imagen",
        "ficha de origen",
        "no se cuentan piedras",
        "el catálogo no incluye",
    )
    by_sku = {row.sku: row for row in fixture_rows}
    for record in records:
        if record.text_quality_tier not in {"rich", "sparse"}:
            continue
        folded = record.description.casefold()
        for phrase in forbidden:
            assert phrase not in folded, f"{record.sku} contains {phrase!r}"
        source = by_sku[record.sku]
        if source.description.strip() == "plata de ley":
            assert "plata" in folded
