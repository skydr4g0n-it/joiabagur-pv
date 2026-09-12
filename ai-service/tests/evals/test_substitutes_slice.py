"""The substitutes evaluation slice: anchored, separate, and unable to move the table. C26."""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

from jbg_ai.evals.errors import EvaluationUnavailable
from jbg_ai.evals.golden import SUBSTITUTE, load_golden_set
from jbg_ai.evals.substitutes_slice import (
    SWEEP_WEIGHTS,
    config_id,
    execute_substitutes,
    run_slice,
    substitute_queries,
)
from support.fake_product_search import FakeIndexedRow, FakeProductSearch
from support.settings import build_settings

SOURCE = UUID("00000000-0000-4000-8000-000000000013")


def test_every_substitutes_query_declares_a_source_product() -> None:
    """The anchor, asserted on the committed set and not only in the validator."""
    golden = load_golden_set()
    substitutes = [item for item in golden.queries if item.category == SUBSTITUTE]

    assert substitutes, "the set must keep carrying substitutes queries"
    for item in substitutes:
        assert item.source_product_id, f"{item.id} has no source product"
        UUID(item.source_product_id)


def test_the_slice_covers_a_source_product_without_a_family() -> None:
    """Four of the five reserved queries have a family; 58 % of the catalogue does not.

    Asserted through the judgements rather than by naming a SKU: the query anchored on
    `SKU102` is the orphan, and what matters is that some anchor has no family at all.
    """
    golden = load_golden_set()
    anchors = {item.source_product_id for item in substitute_queries(golden)}

    # `SKU102 Anillo caracola` — real, orphaned, and with no size either.
    assert "065314d3-4d91-4dda-8e6e-40ecdb545db6" in anchors


def test_substitutes_queries_are_excluded_from_the_product_retriever_scope() -> None:
    """**The guard that keeps the published ablation table reproducible.**

    The runner and the sweep measure `retrieval_queries`. Before C26 that was the same set
    as `judged_queries`, so the scope was right by accident; the five new judged queries are
    answered by a route that takes a product identifier, and letting them in would move the
    denominator of a table published twice — its figures would change with no configuration
    having changed.
    """
    golden = load_golden_set()

    assert len(golden.retrieval_queries) < len(golden.judged_queries)
    assert all(item.category != SUBSTITUTE for item in golden.retrieval_queries)
    assert {item.id for item in golden.judged_queries} - {
        item.id for item in golden.retrieval_queries
    } == {item.id for item in substitute_queries(golden)}


def test_the_published_ablation_denominator_is_the_one_c25_measured() -> None:
    """63 judged queries of the product retriever, exactly as before this change.

    A literal, on purpose. The point of the number is that it does NOT move, so deriving it
    from the file it is meant to protect would assert nothing at all.
    """
    assert len(load_golden_set().retrieval_queries) == 63


def test_the_sweep_grid_contains_the_rollback_and_a_value_that_is_too_strong() -> None:
    """A grid that only explores the half that works is not a sweep."""
    assert 0.0 in SWEEP_WEIGHTS
    assert max(SWEEP_WEIGHTS) > 0.08
    assert config_id(0.05) == "c26-substitutes-w0.05"


def test_the_slice_calls_the_pipeline_and_never_the_product_retriever() -> None:
    """In process, like `execute.py`, and through the substitutes path only."""
    golden = load_golden_set()
    query = substitute_queries(golden)[0]
    rows = [
        FakeIndexedRow(
            product_id=UUID(query.source_product_id),
            sku="SOURCE",
            distance=0.0,
            materials=["plata"],
            piece_type="anillo",
            size_label="M",
        ),
        FakeIndexedRow(
            product_id=SOURCE,
            sku="CANDIDATE",
            distance=0.1,
            materials=["plata"],
            piece_type="anillo",
            size_label="M",
        ),
    ]
    search = FakeProductSearch(rows)

    run = asyncio.run(
        execute_substitutes(
            query,
            settings=build_settings(stub_mode=False),
            search=search,
            weight_size=0.05,
        )
    )

    assert [hit.sku for hit in run.hits] == ["CANDIDATE"]
    assert run.sample.provider_ms == 0.0
    assert run.low_confidence is False
    assert search.search_calls == []
    assert search.lexical_calls == []
    # Unscoped, exactly as every configuration of the published table sets
    # `pos_prefilter: false`: the golden set carries no assortment.
    assert search.neighbour_calls[-1]["signal_pos_id"] is None


def test_an_unanchored_query_cannot_be_executed() -> None:
    golden = load_golden_set()
    query = substitute_queries(golden)[0]
    unanchored = type(query)(**{**query.__dict__, "source_product_id": None})

    with pytest.raises(EvaluationUnavailable):
        asyncio.run(
            execute_substitutes(
                unanchored,
                settings=build_settings(stub_mode=False),
                search=FakeProductSearch([]),
                weight_size=0.05,
            )
        )


def test_run_slice_produces_one_case_per_query_and_weight() -> None:
    golden = load_golden_set()
    queries = substitute_queries(golden)
    rows = [
        FakeIndexedRow(
            product_id=UUID(item.source_product_id),
            sku=f"SRC-{item.id}",
            distance=0.0,
            materials=["plata"],
            piece_type="anillo",
            size_label="M",
        )
        for item in queries
    ]
    rows.append(
        FakeIndexedRow(
            product_id=SOURCE,
            sku="CANDIDATE",
            distance=0.1,
            materials=["plata"],
            piece_type="anillo",
            size_label="M",
        )
    )

    cases = asyncio.run(
        run_slice(
            golden,
            settings=build_settings(stub_mode=False),
            search=FakeProductSearch(rows),
            weights=(0.0, 0.05),
        )
    )

    assert len(cases) == 2 * len(queries)
    assert {case.config_id for case in cases} == {
        config_id(0.0),
        config_id(0.05),
    }
