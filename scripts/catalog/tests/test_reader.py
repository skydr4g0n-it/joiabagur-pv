from __future__ import annotations

from catalog_pipeline.errors import CatalogReadError
from catalog_pipeline.reader import read_export
import pytest


def test_reader_returns_all_fixture_rows(fixture_csv, fixture_xlsx):
    from_csv = read_export(fixture_csv)
    from_xlsx = read_export(fixture_xlsx)
    assert [row.sku for row in from_csv] == [
        "RING-S",
        "RING-M",
        "RING-L",
        "NECK-01",
        "BRAC-01",
        "EAR-01",
        "UNMATCH-99",
    ]
    assert [row.sku for row in from_xlsx] == [row.sku for row in from_csv]
    assert [row.name for row in from_xlsx] == [row.name for row in from_csv]


def test_reader_rejects_duplicate_sku(duplicates_csv):
    with pytest.raises(CatalogReadError, match="duplicate SKU"):
        read_export(duplicates_csv)


def test_reader_rejects_row_without_sku(tmp_path):
    path = tmp_path / "missing-sku.csv"
    path.write_text(
        "SKU,Name,Description,Price,Collection\n,Anillo huérfano,plata,10.00,A\n",
        encoding="utf-8",
    )
    with pytest.raises(CatalogReadError, match="SKU is required"):
        read_export(path)


def test_reader_reads_overlong_source_row():
    from pathlib import Path

    rows = read_export(Path(__file__).parent / "fixtures" / "overlong.csv")
    assert len(rows) == 1
    assert rows[0].sku == "OVER-1001"
    assert len(rows[0].description) == 1001
