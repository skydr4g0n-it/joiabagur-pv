"""SHA-256 of a product-id set, matching C12 `IndexFeedAggregateHash.OfProductIds`."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from uuid import UUID


def _dotnet_guid_sort_key(value: UUID) -> tuple[object, ...]:
    """Sort key equivalent to .NET `Guid.CompareTo` (signed Data1/Data2/Data3, then bytes)."""
    raw = value.bytes
    data1 = int.from_bytes(raw[0:4], "big", signed=True)
    data2 = int.from_bytes(raw[4:6], "big", signed=True)
    data3 = int.from_bytes(raw[6:8], "big", signed=True)
    return (data1, data2, data3, *raw[8:16])


def of_product_ids(product_ids: Iterable[UUID]) -> str:
    """Canonical UUID `D` format, .NET Guid order, UTF-8 concat, 64 lowercase hex."""
    ordered = sorted(product_ids, key=_dotnet_guid_sort_key)
    payload = "".join(str(item) for item in ordered)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
