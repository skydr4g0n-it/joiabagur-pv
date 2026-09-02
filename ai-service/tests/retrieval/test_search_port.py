"""Fake search port covers count/search without RDS. Delivered by C14, extended by C21."""

from __future__ import annotations

import asyncio
from uuid import UUID

from jbg_ai.retrieval.lexical import expanded_request, typed_request
from jbg_ai.retrieval.ports import SearchFilters
from jbg_ai.retrieval.search import (
    COUNT_COMPATIBLE_SQL,
    compile_lexical_sql,
    compile_search_sql,
)
from jbg_ai.retrieval.synonyms import ExpandedQuery, TermMatch
from support.fake_product_search import FakeIndexedRow, FakeProductSearch

A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
C = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
FAMILY = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
OTHER_FAMILY = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")

ALL_FILTERS = SearchFilters(
    materials=["plata"],
    category="anillo",
    family_id=FAMILY,
    exclude_product_ids=[B],
)


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


def test_fake_search_applies_threshold_depth_and_body_filters() -> None:
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
            depth=10,
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


def test_search_sql_does_not_use_pos_id_or_price_as_a_predicate() -> None:
    sql = compile_search_sql(ALL_FILTERS)

    assert "<=>" in sql
    assert "<->" not in sql
    assert "pos_id" not in sql
    assert "public." not in sql
    assert "stock" not in sql
    assert "ai.product_document" in COUNT_COMPATIBLE_SQL
    assert "public." not in COUNT_COMPATIBLE_SQL
    assert "pos_id" not in COUNT_COMPATIBLE_SQL


def _price_predicates(sql: str) -> list[str]:
    """Lines that constrain by price, as opposed to the one that selects it for ordering."""
    return [
        line
        for line in sql.splitlines()
        if "price" in line and line.strip().startswith(("AND", "WHERE", "OR"))
    ]


def test_neither_branch_excludes_by_price_or_stock() -> None:
    """C21 selects `price` to demote with it. Demoting is not excluding."""
    lexical_sql, _ = compile_lexical_sql(typed_request("anillo barato"), ALL_FILTERS)

    for sql in (compile_search_sql(ALL_FILTERS), lexical_sql):
        assert _price_predicates(sql) == []
        assert "stock" not in sql


def test_lexical_sql_uses_the_gin_predicate_and_applies_every_body_filter() -> None:
    sql, terms = compile_lexical_sql(
        expanded_request(
            ExpandedQuery(
                original="anillo de plata",
                groups=(("anillo", "sortija"), ("plata",)),
                matched=(
                    TermMatch(term="anillo", field="piece_type", canonical="anillo"),
                    TermMatch(term="plata", field="materials", canonical="plata"),
                ),
            )
        ),
        ALL_FILTERS,
    )

    assert "tsv @@ " in sql
    assert "ts_rank(tsv," in sql
    assert "ORDER BY coordination DESC, ts_rank DESC" in sql
    assert "ai.product_document" in sql
    assert "public." not in sql
    assert "pos_id" not in sql
    assert "materials && CAST(:materials AS text[])" in sql
    assert "piece_type = :category" in sql
    assert "family_id = :family_id" in sql
    assert "product_id <> ALL(CAST(:exclude_ids AS uuid[]))" in sql
    assert sorted(terms.values()) == ["anillo", "plata", "sortija"]
    for term in terms.values():
        assert term not in sql


def _lexical_rows() -> list[FakeIndexedRow]:
    return [
        FakeIndexedRow(
            product_id=A,
            sku="both",
            distance=0.9,
            doc_text="Tipo: anillo. Materiales: plata.",
            materials=["plata"],
            piece_type="anillo",
        ),
        FakeIndexedRow(
            product_id=B,
            sku="type-only",
            distance=0.9,
            doc_text="Tipo: anillo. Materiales: oro.",
            materials=["oro"],
            piece_type="anillo",
        ),
        FakeIndexedRow(
            product_id=C,
            sku="material-only",
            distance=0.9,
            doc_text="Tipo: pulsera. Materiales: plata.",
            materials=["plata"],
            piece_type="pulsera",
        ),
    ]


def test_lexical_branch_ors_groups_and_ranks_by_coordination() -> None:
    """The conjunction's result is the head of the OR list, never a set traded away."""
    search = FakeProductSearch(_lexical_rows())
    request = expanded_request(
        ExpandedQuery(
            original="anillo de plata",
            groups=(("anillo",), ("plata",)),
            matched=(
                TermMatch(term="anillo", field="piece_type", canonical="anillo"),
                TermMatch(term="plata", field="materials", canonical="plata"),
            ),
        )
    )
    hits = _run(search.search_lexical(request, depth=60, filters=SearchFilters()))

    assert hits[0].sku == "both"
    assert hits[0].coordination == 2
    assert {hit.sku for hit in hits[1:]} == {"type-only", "material-only"}
    assert all(hit.coordination == 1 for hit in hits[1:])


def test_group_matching_nothing_does_not_change_order() -> None:
    """It adds 0 to every document, so no zero-drop step is needed to detect it."""
    search = FakeProductSearch(_lexical_rows())
    base = ExpandedQuery(
        original="anillo de plata",
        groups=(("anillo",), ("plata",)),
        matched=(
            TermMatch(term="anillo", field="piece_type", canonical="anillo"),
            TermMatch(term="plata", field="materials", canonical="plata"),
        ),
    )
    widened = ExpandedQuery(
        original="anillo de plata para regalar",
        groups=(("anillo",), ("plata",), ("regalar",)),
        matched=base.matched,
    )

    without = _run(search.search_lexical(expanded_request(base), depth=60, filters=SearchFilters()))
    with_dead_group = _run(
        search.search_lexical(expanded_request(widened), depth=60, filters=SearchFilters())
    )

    assert [hit.sku for hit in without] == [hit.sku for hit in with_dead_group]


def test_sparse_group_cannot_jump_the_queue() -> None:
    rows = [
        FakeIndexedRow(
            product_id=A,
            sku="ring-untagged",
            distance=0.9,
            doc_text="Tipo: anillo. Materiales: plata.",
            piece_type="anillo",
        ),
        FakeIndexedRow(
            product_id=B,
            sku="bracelet-for-weddings",
            distance=0.9,
            doc_text="Tipo: pulsera. Ocasiones: boda.",
            piece_type="pulsera",
        ),
    ]
    request = expanded_request(
        ExpandedQuery(
            original="anillo de boda",
            groups=(("anillo",), ("boda",)),
            matched=(
                TermMatch(term="anillo", field="piece_type", canonical="anillo"),
                TermMatch(term="boda", field="occasion_tags", canonical="boda"),
            ),
        )
    )
    hits = _run(FakeProductSearch(rows).search_lexical(request, depth=60, filters=SearchFilters()))

    assert [hit.sku for hit in hits] == ["ring-untagged", "bracelet-for-weddings"]
    assert hits[0].coordination == 1
    assert hits[1].coordination == 0, "the occasion tag scores but does not tally"


def test_lexical_branch_applies_body_filters_and_the_branch_depth() -> None:
    rows = _lexical_rows()
    search = FakeProductSearch(rows)
    request = typed_request("plata")

    filtered = _run(
        search.search_lexical(
            request,
            depth=60,
            filters=SearchFilters(materials=["plata"], category="anillo"),
        )
    )
    assert [hit.sku for hit in filtered] == ["both"]

    truncated = _run(search.search_lexical(request, depth=1, filters=SearchFilters()))
    assert len(truncated) == 1
