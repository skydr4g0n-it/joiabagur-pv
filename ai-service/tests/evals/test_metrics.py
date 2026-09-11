"""Ranking metrics, verified against values computed by hand. C24."""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from jbg_ai.evals.golden import load_golden_set
from jbg_ai.evals.metrics import (
    aggregate,
    binary_gain,
    grade_distribution,
    graded_gain,
    ndcg,
    score_case,
    stale_judgements,
)

A = "aaaaaaaa-0000-0000-0000-000000000000"
B = "bbbbbbbb-0000-0000-0000-000000000000"
C = "cccccccc-0000-0000-0000-000000000000"
D = "dddddddd-0000-0000-0000-000000000000"


def test_ndcg_matches_the_value_computed_by_hand() -> None:
    """Ranked 2, 0, 1 against an ideal of 2, 1, 1.

    DCG  = 3/log2(2) + 0/log2(3) + 1/log2(4) = 3 + 0 + 0.5              = 3.5
    IDCG = 3/log2(2) + 1/log2(3) + 1/log2(4) = 3 + 0.6309297 + 0.5      = 4.1309297
    nDCG = 3.5 / 4.1309297 = 0.8472669…

    Both forms are asserted on purpose: the closed expression catches a change of formula, and
    the decimal catches a change of formula that happens to be algebraically equivalent to a
    different metric.
    """
    value = ndcg([2, 0, 1], [2, 1, 1], gain=graded_gain)

    expected = (3 + 0 + 1 / 2) / (3 + 1 / math.log2(3) + 1 / 2)
    assert value == expected
    assert round(value, 7) == 0.8472669


def test_the_binary_reading_of_the_same_ranking_is_a_different_number() -> None:
    """Which is the point of publishing both: they can order configurations differently."""
    graded = ndcg([2, 0, 1], [2, 1, 1], gain=graded_gain)
    binary = ndcg([2, 0, 1], [2, 1, 1], gain=binary_gain)

    assert binary == (1 + 0 + 1 / 2) / (1 + 1 / math.log2(3) + 1 / 2)
    assert graded != binary


def test_a_query_nothing_can_answer_scores_zero_and_not_one() -> None:
    """Otherwise the out-of-domain category hands a free point to whoever returns most rubbish."""
    assert ndcg([0, 0, 0], [], gain=graded_gain) == 0.0


def _one_query_set(tmp_path: Path, judgements: list[dict]) -> Path:
    import json

    root = tmp_path / "g"
    root.mkdir()
    (root / "criterion.md").write_text("x", encoding="utf-8")
    (root / "queries.jsonl").write_text(
        json.dumps(
            {
                "id": "q1",
                "text": "anillo de plata",
                "category": "materiales",
                "in_tuning_set": False,
                "judged": True,
                "judged_depth": 20,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "judgements.jsonl").write_text(
        "\n".join(json.dumps(item) for item in judgements) + "\n", encoding="utf-8"
    )
    return root


def _judgement(product_id: str, grade: int, origin: str = "real") -> dict:
    return {
        "query_id": "q1",
        "product_id": product_id,
        "grade": grade,
        "pooled_in": ["v2-hibrido"],
        "judged_at": "2026-09-07",
        "source_hash": "0" * 64,
        "data_origin": origin,
        "lexically_reachable": True,
    }


def _load(tmp_path: Path, judgements: list[dict]):
    from jbg_ai.evals.golden import GoldenSet, Judgement, content_version

    root = _one_query_set(tmp_path, judgements)
    # Built directly rather than through `load_golden_set`, which would apply the composition
    # matrix to a one-query fixture that exists to exercise arithmetic and nothing else.
    parsed = [
        Judgement.from_json(item, where="fixture") for item in judgements
    ]
    from jbg_ai.evals.golden import GoldenQuery

    query = GoldenQuery(
        id="q1",
        text="anillo de plata",
        category="materiales",
        in_tuning_set=False,
        judged=True,
        judged_depth=20,
    )
    return GoldenSet(
        version=content_version(root),
        root=root,
        queries=(query,),
        judgements=tuple(parsed),
        by_query={"q1": tuple(parsed)},
    )


def test_unjudged_is_reported_separately_from_irrelevant(tmp_path: Path) -> None:
    """Scoring them alike is unavoidable; printing them alike is not."""
    golden = _load(tmp_path, [_judgement(A, 2), _judgement(B, 0)])

    case = score_case(golden, "q1", [UUID(A), UUID(B), UUID(C)], abstained=False)

    assert case.unjudged_at_5 == 1 / 3
    assert case.ndcg_at_5 == 1.0, "the unjudged tail cannot lower a perfect first position"


def test_the_origin_breakdown_counts_only_that_origin_and_never_shrinks_the_corpus(
    tmp_path: Path,
) -> None:
    golden = _load(
        tmp_path,
        [_judgement(A, 2, "synthetic"), _judgement(B, 2, "real"), _judgement(C, 0, "real")],
    )
    ranked = [UUID(A), UUID(C), UUID(B)]

    every = score_case(golden, "q1", ranked, abstained=False)
    real = score_case(golden, "q1", ranked, abstained=False, origin="real")

    assert every.relevant_total == 2
    assert real.relevant_total == 1, "only the real relevant documents are counted"
    assert real.recall_at_5 == 1.0
    assert every.recall_at_5 == 1.0
    # The RANKING is the same list in both readings: nothing restricted the corpus.
    assert real.unjudged_at_5 == every.unjudged_at_5


def test_no_configuration_can_restrict_the_corpus_by_data_origin() -> None:
    """`origin` filters the COUNTING and there is no knob that filters the retrieval."""
    from jbg_ai.evals.configs import EvalConfig, load_all

    fields = set(EvalConfig.__dataclass_fields__)
    assert not {name for name in fields if "origin" in name}
    for config in load_all():
        assert "origin" not in repr(config).lower()


def test_synthetic_displacement_is_measured_and_not_assumed(tmp_path: Path) -> None:
    golden = _load(tmp_path, [_judgement(A, 0, "synthetic"), _judgement(B, 2, "real")])

    displaced = score_case(golden, "q1", [UUID(A), UUID(B)], abstained=False)
    clean = score_case(golden, "q1", [UUID(B), UUID(A)], abstained=False)

    assert displaced.synthetic_displacement_at_5 is True
    assert clean.synthetic_displacement_at_5 is False


def test_displacement_does_not_apply_where_no_real_answer_exists(tmp_path: Path) -> None:
    golden = _load(tmp_path, [_judgement(A, 2, "synthetic")])

    case = score_case(golden, "q1", [UUID(A)], abstained=False)

    assert case.synthetic_displacement_at_5 is None
    assert aggregate([case]).values["synthetic_displacement_at_5"] == 0.0


def test_recall_is_published_capped_and_uncapped(tmp_path: Path) -> None:
    """With dozens of relevant documents the classic reading measures the catalogue, not the run."""
    golden = _load(tmp_path, [_judgement(f"{index:08d}-0000-0000-0000-000000000000", 2) for index in range(20)])
    ranked = [UUID(f"{index:08d}-0000-0000-0000-000000000000") for index in range(5)]

    case = score_case(golden, "q1", ranked, abstained=False)

    assert case.recall_at_5 == 5 / 20
    assert case.recall_at_5_capped == 1.0


def test_stale_judgements_are_counted_against_the_text_they_were_made_on(
    tmp_path: Path,
) -> None:
    """A re-enrichment landing after labelling must not invalidate a judgement in silence."""
    golden = _load(tmp_path, [_judgement(A, 2), _judgement(B, 1)])

    assert stale_judgements(golden, {A: "0" * 64, B: "0" * 64}) == 0
    assert stale_judgements(golden, {A: "f" * 64, B: "0" * 64}) == 1


def test_the_distance_distribution_reports_whether_one_value_separates_the_two() -> None:
    separable = grade_distribution([(2, 0.30), (2, 0.40), (0, 0.60), (0, 0.70)])
    overlapping = grade_distribution([(2, 0.30), (2, 0.80), (0, 0.35), (0, 0.70)])

    assert separable["separability"]["gap"] > 0
    assert overlapping["separability"]["gap"] < 0


def test_the_reranking_headroom_counts_what_a_reranker_could_fix(tmp_path: Path) -> None:
    """A maximum-grade document inside the reranking window but outside the reported five."""
    from jbg_ai.evals.metrics import RERANK_WINDOW

    ids = [f"{index:08d}-0000-0000-0000-000000000000" for index in range(RERANK_WINDOW)]
    golden = _load(tmp_path, [_judgement(ids[7], 2)])

    buried = score_case(golden, "q1", [UUID(value) for value in ids], abstained=False)
    surfaced = score_case(
        golden, "q1", [UUID(ids[7]), *[UUID(value) for value in ids[:7]]], abstained=False
    )

    assert buried.rerank_headroom is True
    assert surfaced.rerank_headroom is False


def test_a_document_beyond_the_reranking_window_is_not_headroom(tmp_path: Path) -> None:
    """A reranker only reorders what it is given; past the window there is nothing to fix."""
    from jbg_ai.evals.metrics import RERANK_WINDOW

    ids = [f"{index:08d}-0000-0000-0000-000000000000" for index in range(RERANK_WINDOW + 5)]
    golden = _load(tmp_path, [_judgement(ids[-1], 2)])

    case = score_case(golden, "q1", [UUID(value) for value in ids], abstained=False)

    assert case.rerank_headroom is False


def test_the_binarisation_rule_is_declared_once_and_not_per_configuration() -> None:
    from jbg_ai.evals.golden import RELEVANT_FROM

    assert RELEVANT_FROM == 1
    assert binary_gain(0) == 0.0
    assert binary_gain(1) == binary_gain(2) == 1.0
