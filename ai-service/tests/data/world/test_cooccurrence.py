"""Co-occurrence counts only the same BulkOperationId."""

from __future__ import annotations

from jbg_ai.data.world.cooccurrence import derive_co_occurrence
from jbg_ai.data.world.records import SaleRow


def _sale(**kwargs) -> SaleRow:
    payload = {
        "sale_key": "s1",
        "sku": "SKU01",
        "pos_code": "CIU-CENTRE",
        "username": "admin",
        "quantity": 1,
        "occurred_at": "2025-07-01T12:00:00Z",
        "bulk_operation_id": None,
        "payment_method_code": "CASH",
    }
    payload.update(kwargs)
    return SaleRow(**payload)


def test_co_occurrence_only_counts_same_bulk_operation() -> None:
    same_day_different_bulk = [
        _sale(sale_key="a", sku="SKU01", bulk_operation_id="b1"),
        _sale(sale_key="b", sku="SKU02", bulk_operation_id="b2"),
    ]
    assert derive_co_occurrence(same_day_different_bulk) == []

    same_bulk = [
        _sale(sale_key="a", sku="SKU02", bulk_operation_id="b9"),
        _sale(sale_key="b", sku="SKU01", bulk_operation_id="b9"),
        _sale(sale_key="c", sku="SKU03", bulk_operation_id="b9"),
    ]
    pairs = derive_co_occurrence(same_bulk)
    keys = {(row.product_sku_a, row.product_sku_b) for row in pairs}
    assert ("SKU01", "SKU02") in keys
    assert ("SKU01", "SKU03") in keys
    assert ("SKU02", "SKU03") in keys
    assert all(row.product_sku_a < row.product_sku_b for row in pairs)
