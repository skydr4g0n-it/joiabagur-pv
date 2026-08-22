from __future__ import annotations

from decimal import Decimal

from catalog_pipeline.errors import IdentityError
from catalog_pipeline.models import EnrichedRecord, SourceRow
from catalog_pipeline.reader import format_price


def prices_equal(left: Decimal | str, right: Decimal | str) -> bool:
    return Decimal(str(left)).quantize(Decimal("0.01")) == Decimal(str(right)).quantize(Decimal("0.01"))


def identity_pairs(source: SourceRow, record: EnrichedRecord) -> dict[str, tuple[object, object]]:
    return {
        "sku": (source.sku, record.sku),
        "name": (source.name, record.name),
        "price": (format_price(source.price), record.price),
        "collection_name": (source.collection_name, record.collection_name),
    }


def identities_match(source: SourceRow, record: EnrichedRecord) -> bool:
    pairs = identity_pairs(source, record)
    return (
        pairs["sku"][0] == pairs["sku"][1]
        and pairs["name"][0] == pairs["name"][1]
        and prices_equal(source.price, record.price)
        and pairs["collection_name"][0] == pairs["collection_name"][1]
    )


def assert_identities(source_rows: list[SourceRow], records: list[EnrichedRecord]) -> None:
    by_sku = {row.sku: row for row in source_rows}
    for record in records:
        source = by_sku.get(record.sku)
        if source is None:
            raise IdentityError(f"JSONL SKU {record.sku!r} is not in the export.")
        if not identities_match(source, record):
            raise IdentityError(
                f"Identity mismatch for SKU {record.sku!r}: {identity_pairs(source, record)}"
            )
    record_skus = {record.sku for record in records}
    extra = [row.sku for row in source_rows if row.sku not in record_skus]
    if extra:
        raise IdentityError(f"Export SKUs missing from JSONL: {extra}")
