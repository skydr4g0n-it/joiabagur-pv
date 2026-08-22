from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from catalog_pipeline.generate import build_records
from catalog_pipeline.reader import read_export

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_csv() -> Path:
    return FIXTURES / "catalog-fixture.csv"


@pytest.fixture
def fixture_xlsx(tmp_path: Path, fixture_csv: Path) -> Path:
    rows = read_export(fixture_csv)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Products"
    sheet.append(["SKU", "Name", "Description", "Price", "Collection"])
    for row in rows:
        sheet.append([row.sku, row.name, row.description, float(row.price), row.collection_name])
    path = tmp_path / "catalog-fixture.xlsx"
    workbook.save(path)
    return path


@pytest.fixture
def fixture_rows(fixture_csv: Path):
    return read_export(fixture_csv)


@pytest.fixture
def fixture_records(fixture_rows):
    return build_records(fixture_rows)


@pytest.fixture
def duplicates_csv() -> Path:
    return FIXTURES / "duplicates.csv"
