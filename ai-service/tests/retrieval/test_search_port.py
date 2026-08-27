"""Fake search port covers count/search without RDS. Delivered by C14."""

from __future__ import annotations

import asyncio
from uuid import UUID

from jbg_ai.retrieval.ports import SearchFilters
from jbg_ai.retrieval.search import COUNT_COMPATIBLE_SQL, compile_search_sql
from support.fake_product_search import FakeIndexedRow, FakeProductSearch

A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
C = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
FAMILY = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
OTHER_FAMILY = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _run(coro):
    return asyncio.run(coro)


def test_fake_count_compatible_ignores_inactive_and_incompatible_rows() -> None:
    search = FakeProductSearch(
        [
            FakeIndexedRow(product_id=A, sku="S1", distance=0.1),
            FakeIndexedRow(product_id=B, sku="S2", distance=0.1, is_active=False),
            FakeIndexedRow(product_id=C, sku="S3", distance=0.1, compatible=False),
        ]
    )

    assert _run(search.count_compatible(model_version_key="m:1536", model_id="m")) == 1


def test_fake_search_applies_threshold_overfetch_and_body_filters() -> None:
    search = FakeProductSearch(
        [
            FakeIndexedRow(
                product_id=A,
                sku="S1",
                distance=0.2,
                materials=["plata"],
                family_id=FAMILY,
                piece_type="anillo",
            ),
            FakeIndexedRow(
                product_id=B,
                sku="S2",
                distance=0.3,
                materials=["oro"],
                family_id=FAMILY,
                piece_type="anillo",
            ),
            FakeIndexedRow(
                product_id=C,
                sku="S3",
                distance=0.9,
                materials=["plata"],
                family_id=FAMILY,
                piece_type="anillo",
            ),
        ]
    )
    hits = _run(
        search.search(
            [0.0],
            threshold=0.65,
            overfetch=10,
            filters=SearchFilters(
                materials=["plata"],
                category="anillo",
                family_id=FAMILY,
                exclude_product_ids=[],
            ),
            model_version_key="m:1536",
            model_id="m",
        )
    )

    assert [hit.product_id for hit in hits] == [A]
    assert hits[0].distance == 0.2


def test_search_sql_does_not_use_pos_id_as_a_predicate() -> None:
    sql = compile_search_sql(
        SearchFilters(
            materials=["plata"],
            category="anillo",
            family_id=FAMILY,
            exclude_product_ids=[B],
        )
    )

    assert "<=>" in sql
    assert "<->" not in sql
    assert "pos_id" not in sql
    assert "public." not in sql
    assert "price" not in sql
    assert "stock" not in sql
    assert "ai.product_document" in COUNT_COMPATIBLE_SQL
    assert "public." not in COUNT_COMPATIBLE_SQL
    assert "pos_id" not in COUNT_COMPATIBLE_SQL
