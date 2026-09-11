"""Adaptive pooling, appendable judgements, and the context-only baseline. C24."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from jbg_ai.evals.cag import (
    LINE,
    SCALE_POINTS,
    answered_skus,
    breaking_point,
    build_context,
    build_prompt,
    compact_line,
    scale_projection,
)
from jbg_ai.evals.golden import Judgement
from jbg_ai.evals.pooling import (
    BASE_DEPTH,
    MAX_DEPTH,
    adaptive_depth,
    append_judgements,
    depth_schedule,
    pool_at_depth,
)


def _ids(count: int, prefix: str = "0") -> list[tuple[UUID, str]]:
    return [
        (UUID(f"{prefix}{index:07d}-0000-0000-0000-000000000000"), f"SKU{index}")
        for index in range(count)
    ]


def test_the_pool_is_the_union_without_repetition_ordered_by_best_rank() -> None:
    shared = _ids(3)
    lists = {
        "v1": shared,
        "v2": [shared[2], shared[1], shared[0]],
    }

    pool = pool_at_depth(lists, 3)

    # Best rank first, then the identifier. SKU2 leads `v2`, so its best rank ties with SKU0's
    # and the identifier decides between them; SKU1 is second in both lists and comes after.
    assert [item.sku for item in pool] == ["SKU0", "SKU2", "SKU1"]
    assert [item.best_rank for item in pool] == [1, 1, 2]
    assert set(pool[0].pooled_in) == {"v1", "v2"}
    assert len(pool) == 3, "the union does not repeat a document"


def test_pooling_stops_when_the_last_block_contributed_nothing() -> None:
    """Otherwise a query with a rich first twenty walks to the cap through forty obvious noughts."""
    lists = {"v1": _ids(60)}
    relevant_ids = {item[0] for item in _ids(BASE_DEPTH)}

    depth, pool = adaptive_depth(lists, lambda pid: pid in relevant_ids)

    assert depth == BASE_DEPTH + 10, "one block was bought, the next found nothing"
    assert len(pool) == BASE_DEPTH + 10


def test_pooling_deepens_while_each_block_keeps_paying() -> None:
    lists = {"v1": _ids(60)}

    depth, _ = adaptive_depth(lists, lambda _pid: True)

    assert depth == MAX_DEPTH


def test_pooling_never_goes_past_what_the_retriever_can_show() -> None:
    assert depth_schedule()[0] == BASE_DEPTH
    assert depth_schedule()[-1] == MAX_DEPTH
    assert all(value <= MAX_DEPTH for value in depth_schedule())


def test_an_unlabelled_pool_does_not_deepen() -> None:
    """A block whose verdicts are not in cannot say whether it contributed."""
    lists = {"v1": _ids(60)}

    depth, _ = adaptive_depth(lists, lambda _pid: None)

    assert depth == BASE_DEPTH


def _judgement(query_id: str, product_id: str, grade: int) -> Judgement:
    return Judgement(
        query_id=query_id,
        product_id=product_id,
        grade=grade,
        pooled_in=("v2-hibrido",),
        judged_at="2026-09-07",
        source_hash="0" * 64,
        data_origin="real",
        lexically_reachable=True,
    )


def test_a_new_judgement_does_not_alter_the_ones_already_recorded(tmp_path: Path) -> None:
    """What lets a later change deepen the pool without re-opening every earlier decision."""
    append_judgements([_judgement("q1", "p1", 2)], tmp_path)
    first = (tmp_path / "judgements.jsonl").read_text(encoding="utf-8")

    append_judgements([_judgement("q1", "p2", 0), _judgement("q1", "p1", 0)], tmp_path)
    after = (tmp_path / "judgements.jsonl").read_text(encoding="utf-8")

    assert after.startswith(first), "the existing line is untouched, and stays first"
    assert '"product_id": "p2"' in after
    assert after.count('"product_id": "p1"') == 1, "the pair already judged is not re-recorded"


# ------------------------------------------------------------------ context-only baseline


def _rows(count: int) -> list[dict]:
    return [
        {
            "product_id": f"{index:08d}-0000-0000-0000-000000000000",
            "sku": f"SKU{index}",
            "name": f"Anillo {index}",
            "piece_type": "anillo",
            "materials": ["plata"],
            "price": 123.45,
        }
        for index in range(count)
    ]


def test_a_catalogue_larger_than_the_budget_is_truncated_the_same_way_every_run() -> None:
    """NOT "it fits": that assertion stops being true the day the shop grows, and a test that
    starts passing for the wrong reason is worse than no test at all."""
    rows = _rows(50)
    budget = 60

    first = build_context(rows, budget_tokens=budget, count_tokens=lambda _text: 10)
    second = build_context(list(reversed(rows)), budget_tokens=budget, count_tokens=lambda _t: 10)

    assert first.documents_omitted == 44
    assert [line.sku for line in first.lines] == [line.sku for line in second.lines]
    assert [line.sku for line in first.lines] == ["SKU0", "SKU1", "SKU2", "SKU3", "SKU4", "SKU5"]


def test_the_number_of_omitted_documents_is_recorded_next_to_the_recall() -> None:
    context = build_context(_rows(10), budget_tokens=25, count_tokens=lambda _text: 10)

    assert context.documents_total == 10
    assert context.documents_omitted == 8
    assert len(context.lines) == 2


def test_no_price_reaches_the_context() -> None:
    """The authority over price is the .NET side, and `RetrievalResult` does not emit one."""
    rows = _rows(3)
    context = build_context(rows, budget_tokens=10_000, count_tokens=lambda text: len(text))
    prompt = build_prompt("anillo de plata", context)

    assert "123.45" not in prompt
    assert "123,45" not in prompt
    assert "price" not in LINE
    for row in rows:
        assert str(row["price"]) not in compact_line(row)


def test_the_scale_projection_says_where_the_catalogue_stops_fitting() -> None:
    context = build_context(_rows(100), budget_tokens=10_000, count_tokens=lambda _text: 10)

    projected = scale_projection(context, budget_tokens=15_000)

    assert [point["documents"] for point in projected] == list(SCALE_POINTS)
    assert projected[0]["tokens"] < projected[-1]["tokens"]
    assert projected[-1]["fits"] is False, "5.000 products at 10 tokens each exceed the budget"


def test_the_wall_is_named_even_when_every_sampled_size_still_fits() -> None:
    """The real catalogue's curve is three «sí» and no wall, which is how C24 shipped without it.

    `SCALE_POINTS` are samples: a budget nothing in them exceeds hides the ceiling rather than
    proving there is none. The requirement asks for the size at which the catalogue no longer
    fits, so it is computed and not sampled.
    """
    context = build_context(_rows(100), budget_tokens=10_000, count_tokens=lambda _text: 10)

    assert all(point["fits"] for point in scale_projection(context, budget_tokens=100_000))
    assert breaking_point(context, budget_tokens=100_000) == 10_001


def test_the_wall_agrees_with_the_curve_about_the_last_size_that_fits() -> None:
    """The two must never disagree: the curve rounds, so the wall rounds the same way."""
    context = build_context(_rows(100), budget_tokens=10_000, count_tokens=lambda _text: 10)
    budget = 25_004

    wall = breaking_point(context, budget_tokens=budget)

    assert round(context.tokens / len(context.lines) * wall) > budget
    assert round(context.tokens / len(context.lines) * (wall - 1)) <= budget


def test_the_answer_is_read_back_as_the_codes_it_cited() -> None:
    assert answered_skus("SKU12, SKU7 y SKU12") == ["SKU12", "SKU7"]
    assert answered_skus("NINGUNO") == []
    assert answered_skus("") == []
