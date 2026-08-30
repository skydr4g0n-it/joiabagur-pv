"""SHA-256 of a product-id set, matching C12 `IndexFeedAggregateHash.OfProductIds`."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from uuid import UUID


def of_product_ids(product_ids: Iterable[UUID]) -> str:
    """Canonical UUID `D` format, .NET `Guid` order, UTF-8 concat, 64 lowercase hex.

    **The ordering is plain byte order, and that is the whole subtlety.**

    This function delivered by C13 used to sort by a hand-rolled key that read
    the first three fields of the identifier as *signed* integers, modelling the
    `Guid.CompareTo` of the .NET **Framework**. On .NET Core and later — which
    is what the API runs — that comparison is *unsigned*, and an unsigned
    comparison of `Data1`, `Data2`, `Data3` and then the remaining bytes is
    exactly a comparison of the sixteen bytes in order.

    The difference is invisible until a set contains identifiers on both sides
    of the high bit, and then every hash disagrees. C17 hit it on the first real
    index: over the same 1200 identifiers, the .NET feed published
    `ba2d18de…` and this function computed `35e77e80…`, so `drift_count` could
    never reach zero no matter how many times the catalog was synchronised. The
    sets were identical; only the order was not.

    The test vector that guarded this used `aaaaaaaa-…` and `bbbbbbbb-…`, both
    in the upper half of the range, where signed and unsigned ordering agree —
    so it passed against either implementation. `test_set_hash_distinguishes_
    signed_from_unsigned_order` exists to make that impossible again.
    """
    ordered = sorted(product_ids, key=lambda value: value.bytes)
    payload = "".join(str(item) for item in ordered)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
