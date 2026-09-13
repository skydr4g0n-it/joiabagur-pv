"""Identifiers and builders the assistance suite shares. Delivered by C30a.

Lives here rather than in `conftest.py` for the reason `support/settings.py` already
records: `conftest.py` is pytest's fixture mechanism, not an importable module, so anything
a test module needs at import time has to live in `support/`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar
from uuid import UUID

from support.fake_product_search import FakeIndexedRow

T = TypeVar("T")

#: Real UUIDs because the layer parses them: a placeholder like `P-0001` is accepted only
#: for as long as nothing reads it, and here something does.
PIECE = UUID("aaaaaaaa-aaaa-4aaa-8aaa-000000000001")
SIBLING = UUID("aaaaaaaa-aaaa-4aaa-8aaa-000000000002")
THIRD = UUID("aaaaaaaa-aaaa-4aaa-8aaa-000000000003")
FOURTH = UUID("aaaaaaaa-aaaa-4aaa-8aaa-000000000004")
LONER = UUID("aaaaaaaa-aaaa-4aaa-8aaa-000000000009")
FAMILY = UUID("11111111-1111-4111-8111-111111111111")
OTHER_FAMILY = UUID("22222222-2222-4222-8222-222222222222")


def run(scenario: Coroutine[Any, Any, T] | Callable[[], Coroutine[Any, Any, T]]) -> T:
    """`asyncio.run` for a suite that installs no asyncio plugin."""
    if callable(scenario):
        return asyncio.run(scenario())
    return asyncio.run(scenario)


def indexed_row(**overrides: Any) -> FakeIndexedRow:
    """One indexed document; a test states only the attribute it is about."""
    values: dict[str, Any] = {
        "product_id": PIECE,
        "sku": "JBG-0001",
        "distance": 0.2,
        "materials": ["plata"],
        "family_id": FAMILY,
        "family_name": "Aro Menorca",
        "variant_label": "18 mm",
        "size_label": "M",
        "piece_type": "anillo",
        "doc_text": "Tipo: anillo. Materiales: plata. Aro Menorca.",
    }
    values.update(overrides)
    return FakeIndexedRow(**values)
