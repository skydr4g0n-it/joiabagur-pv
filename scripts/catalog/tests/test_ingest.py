from __future__ import annotations

from decimal import Decimal

import pytest

from catalog_pipeline.errors import IngestAborted
from catalog_pipeline.ingest import FakeCatalogStore, run_ingest


def _store_rows(records, *, include_unmatched: bool = False) -> dict[str, dict]:
    rows = {}
    for index, record in enumerate(records):
        if record.sku == "UNMATCH-99" and not include_unmatched:
            continue
        rows[record.sku] = {
            "id": f"id-{index}",
            "name": record.name,
            "price": Decimal(record.price),
            "collection_id": f"col-{index}",
            "description": "original",
        }
    return rows


def test_ingest_lists_unmatched_without_insert(fixture_records):
    store = FakeCatalogStore(_store_rows(fixture_records))
    before = store.row_count()
    result = run_ingest(store, fixture_records)
    assert "UNMATCH-99" in result.unmatched
    assert store.row_count() == before
    assert "UNMATCH-99" not in store.rows
    assert store.insert_attempts == 0
    matched = [record for record in fixture_records if record.sku != "UNMATCH-99"]
    for record in matched:
        assert store.rows[record.sku]["description"] == record.description
        assert store.rows[record.sku]["name"] == record.name
        assert store.rows[record.sku]["price"] == Decimal(record.price)


def test_ingest_rolls_back_when_identity_would_change(fixture_records):
    store = FakeCatalogStore(_store_rows(fixture_records), tamper_name_on_reread=True)
    originals = {sku: dict(row) for sku, row in store.rows.items()}
    with pytest.raises(IngestAborted, match="Identity changed"):
        run_ingest(store, fixture_records)
    assert store.rows == originals
    assert store.committed is False
