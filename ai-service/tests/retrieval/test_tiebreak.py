"""Both retrieval statements truncate under a TOTAL order. Delivered by C24.

Neither `ORDER BY` had a final key, so `LIMIT` could cut inside a tie and PostgreSQL was free
to return either row. Two runs of one configuration against one index could therefore disagree,
which is fatal to an evaluation harness: a moved metric could no longer be attributed to a
change rather than to chance. This is the live-path deviation C24 declares.

Ties are not a corner case in the lexical branch. `coordination` takes a handful of values by
construction and `ts_rank` repeats across documents matching the same fields, so the boundary
lands inside a tie routinely rather than exceptionally.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from jbg_ai.retrieval.lexical import TYPED_LIST, LexicalRequest, typed_request
from jbg_ai.retrieval.ports import SearchFilters
from jbg_ai.retrieval.search import compile_lexical_sql, compile_search_sql
from support.fake_product_search import FakeIndexedRow, FakeProductSearch

#: Deliberately NOT in the order they are declared: the lower identifier is the second row of
#: every fixture below, so a test that passed by input order alone would fail here.
LOW = UUID("11111111-1111-1111-1111-111111111111")
HIGH = UUID("99999999-9999-9999-9999-999999999999")


def _run(coro):
    return asyncio.run(coro)


def _order_by(sql: str) -> str:
    return next(line.strip() for line in sql.splitlines() if line.strip().startswith("ORDER BY"))


def test_both_statements_end_their_ordering_with_the_deterministic_key() -> None:
    filters = SearchFilters()
    lexical_sql, _ = compile_lexical_sql(typed_request("anillo"), filters)

    assert _order_by(compile_search_sql(filters)).endswith("d.product_id ASC")
    assert _order_by(lexical_sql).endswith("d.product_id ASC")


def test_the_key_is_last_so_it_never_outranks_a_real_signal() -> None:
    """A tiebreak placed first would be a ranking signal. Order of the keys is the whole point."""
    lexical_sql, _ = compile_lexical_sql(typed_request("anillo"), SearchFilters())
    ordering = _order_by(lexical_sql)

    assert ordering.index("coordination") < ordering.index("ts_rank") < ordering.index(
        "d.product_id"
    )
    assert _order_by(compile_search_sql(SearchFilters())).index("<=>") < _order_by(
        compile_search_sql(SearchFilters())
    ).index("d.product_id")


def _tied_lexical_rows() -> list[FakeIndexedRow]:
    """Two documents the lexical ordering cannot separate: same groups matched, same tally."""
    return [
        FakeIndexedRow(
            product_id=HIGH,
            sku="tied-high",
            distance=0.9,
            doc_text="Tipo: anillo. Materiales: plata.",
            piece_type="anillo",
            materials=["plata"],
        ),
        FakeIndexedRow(
            product_id=LOW,
            sku="tied-low",
            distance=0.9,
            doc_text="Tipo: anillo. Materiales: plata.",
            piece_type="anillo",
            materials=["plata"],
        ),
    ]


def test_equal_coordination_and_rank_survive_truncation_the_same_way_every_run() -> None:
    rows = _tied_lexical_rows()
    request = typed_request("anillo")

    survivors = [
        [
            hit.product_id
            for hit in _run(
                FakeProductSearch(list(rows)).search_lexical(
                    request, depth=1, filters=SearchFilters()
                )
            )
        ]
        for _ in range(3)
    ]

    assert survivors == [[LOW]] * 3, "the cut fell inside a tie and moved between runs"


def test_a_tie_is_a_real_tie_before_the_key_decides() -> None:
    """Guards the fixture, not the code: if the two rows scored differently the test proves nothing."""
    hits = _run(
        FakeProductSearch(_tied_lexical_rows()).search_lexical(
            typed_request("anillo"), depth=60, filters=SearchFilters()
        )
    )

    assert len(hits) == 2
    assert hits[0].coordination == hits[1].coordination
    assert hits[0].ts_rank == hits[1].ts_rank


def test_the_tiebreak_does_not_reorder_candidates_that_differ_in_coordination() -> None:
    """The higher identifier matches both groups and must still come first."""
    rows = [
        FakeIndexedRow(
            product_id=HIGH,
            sku="two-groups",
            distance=0.9,
            doc_text="Tipo: anillo. Materiales: plata.",
            piece_type="anillo",
            materials=["plata"],
        ),
        FakeIndexedRow(
            product_id=LOW,
            sku="one-group",
            distance=0.9,
            doc_text="Tipo: anillo. Materiales: oro.",
            piece_type="anillo",
            materials=["oro"],
        ),
    ]
    request = LexicalRequest(
        name=TYPED_LIST,
        text="anillo plata",
        groups=(("anillo",), ("plata",)),
        counting=(True, True),
    )

    hits = _run(FakeProductSearch(rows).search_lexical(request, depth=60, filters=SearchFilters()))

    assert [hit.product_id for hit in hits] == [HIGH, LOW]
    assert hits[0].coordination == 2 and hits[1].coordination == 1


def test_the_tiebreak_does_not_reorder_candidates_whose_distances_differ() -> None:
    rows = [
        FakeIndexedRow(product_id=HIGH, sku="near", distance=0.10),
        FakeIndexedRow(product_id=LOW, sku="far", distance=0.40),
    ]

    hits = _run(
        FakeProductSearch(rows).search(
            [0.0],
            threshold=0.65,
            depth=60,
            filters=SearchFilters(),
            model_version_key="m:1536",
            model_id="m",
        )
    )

    assert [hit.product_id for hit in hits] == [HIGH, LOW], "the key outranked the distance"


def test_equal_distances_survive_truncation_the_same_way_every_run() -> None:
    rows = [
        FakeIndexedRow(product_id=HIGH, sku="tied-high", distance=0.25),
        FakeIndexedRow(product_id=LOW, sku="tied-low", distance=0.25),
    ]

    survivors = [
        [
            hit.product_id
            for hit in _run(
                FakeProductSearch(list(rows)).search(
                    [0.0],
                    threshold=0.65,
                    depth=1,
                    filters=SearchFilters(),
                    model_version_key="m:1536",
                    model_id="m",
                )
            )
        ]
        for _ in range(3)
    ]

    assert survivors == [[LOW]] * 3
