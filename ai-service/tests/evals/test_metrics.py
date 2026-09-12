"""Ranking metrics, verified against values computed by hand. C24."""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest

from jbg_ai.evals.configs import ABLATION_ORDER, load_config
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


# --------------------------------------------------------------------------------------
# C25 - the operational reading, declared before the measurement and never applied to the file.
# --------------------------------------------------------------------------------------


def test_operational_gain_is_a_declared_function_of_grade_and_availability() -> None:
    """The function of D3, pre-registered on 2026-09-11 before any metric was computed.

        g_efectivo = grade               if bucket != '0'
                     max(grade - 1, 0)   if bucket == '0'

    It reuses the rubric's own scale instead of inventing a constant: grade 1 is already
    "a plausible substitute the operator would offer second", and a piece that cannot be put
    on the cloth is exactly that.
    """
    from jbg_ai.evals.metrics import effective_grade, graded_gain, operational_gain

    # In stock: the grade is untouched, whichever non-zero bucket it is.
    for bucket in ("1-2", "3+"):
        for grade in (0, 1, 2):
            assert effective_grade(grade, bucket) == grade
            assert operational_gain(grade, bucket) == graded_gain(grade)

    # Exhausted: one rung down, with a floor at zero.
    assert effective_grade(2, "0") == 1
    assert effective_grade(1, "0") == 0
    assert effective_grade(0, "0") == 0, "grade 0 cannot fall further"

    # Absent is NOT exhausted: no reading scope, or this point of sale does not carry it.
    for grade in (0, 1, 2):
        assert effective_grade(grade, None) == grade, "absence is not evidence of zero stock"

    # The two non-zero buckets are indistinguishable under this function, which is why no
    # objective function can order them and why the distinction stays binary.
    assert operational_gain(2, "1-2") == operational_gain(2, "3+")


def test_operational_metric_does_not_modify_the_judgements(tmp_path) -> None:
    """A third READING of the same annotation. The file on disk is never touched."""
    import hashlib

    from jbg_ai.data.paths import AI_SERVICE_ROOT

    path = AI_SERVICE_ROOT / "evals" / "golden" / "judgements.jsonl"
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    golden = load_golden_set()
    query = golden.judged_queries[0]
    judged = golden.judgements_for(query.id)
    ranked = [UUID(item.product_id) for item in judged[:10]]
    # Every judged document reported as exhausted: the most aggressive reading there is.
    buckets = {item.product_id: "0" for item in judged}

    with_signal = score_case(golden, query.id, ranked, abstained=False, buckets=buckets)
    without = score_case(golden, query.id, ranked, abstained=False)

    assert hashlib.sha256(path.read_bytes()).hexdigest() == before, "the file changed"
    # The recorded grade is still the recorded grade.
    assert [item.grade for item in golden.judgements_for(query.id)] == [
        item.grade for item in judged
    ]
    # And the graded reading is unaffected by the availability signal.
    assert with_signal.ndcg_at_5 == without.ndcg_at_5
    assert without.ndcg_at_5_operational is None, "no signal read, no operational reading"
    assert with_signal.ndcg_at_5_operational is not None


def test_the_operational_reading_is_absent_rather_than_zero_when_no_signal_is_read() -> None:
    """Printing a zero would rank a configuration last on a metric it never competed in."""
    from jbg_ai.evals.metrics import aggregate

    golden = load_golden_set()
    query = golden.judged_queries[0]
    ranked = [UUID(item.product_id) for item in golden.judgements_for(query.id)[:5]]

    case = score_case(golden, query.id, ranked, abstained=False)
    assert case.ndcg_at_5_operational is None
    assert "ndcg_at_5_operational" not in aggregate([case]).values

    with_signal = score_case(
        golden,
        query.id,
        ranked,
        abstained=False,
        buckets={item.product_id: "3+" for item in golden.judgements_for(query.id)},
    )
    assert "ndcg_at_5_operational" in aggregate([with_signal]).values


def test_an_exhausted_top_hit_costs_the_operational_reading_and_not_the_graded_one() -> None:
    """The metric has to be able to move, or calibrating against it is theatre."""
    golden = load_golden_set()
    query = next(
        item
        for item in golden.judged_queries
        if sum(1 for j in golden.judgements_for(item.id) if j.grade == 2) >= 2
    )
    judged = golden.judgements_for(query.id)
    best = [item for item in judged if item.grade == 2][:2]
    ranked = [UUID(item.product_id) for item in best]

    stocked = score_case(
        golden, query.id, ranked, abstained=False,
        buckets={item.product_id: "3+" for item in judged},
    )
    exhausted = score_case(
        golden, query.id, ranked, abstained=False,
        buckets={item.product_id: "0" for item in judged},
    )

    assert stocked.ndcg_at_5 == exhausted.ndcg_at_5, "pure relevance must not notice"
    # Both readings normalise against an ideal built with the same gain, so a run where
    # EVERYTHING is exhausted is not penalised as a whole - what moves the metric is showing
    # exhausted pieces ahead of available ones, which is the next assertion.
    mixed = score_case(
        golden, query.id, ranked, abstained=False,
        buckets={
            best[0].product_id: "0",
            **{item.product_id: "3+" for item in judged if item.product_id != best[0].product_id},
        },
    )
    assert mixed.ndcg_at_5_operational < stocked.ndcg_at_5_operational, (
        "leading with an exhausted grade-2 must cost the operational reading"
    )
    assert mixed.ndcg_at_5 == stocked.ndcg_at_5, "and must not cost the graded one"


def test_the_baseline_row_is_archived_rather_than_selectable() -> None:
    """C25bis replaced reproducibility with conservation, and declared the trade.

    `v2-hibrido` was measured under the single-stage composition. That composition was retired
    for having been measured as defective, so the row can no longer be re-run — and the harness
    does NOT restate the retired pipeline to keep it runnable, because a harness that restates
    a pipeline measures the restatement.

    What is guaranteed instead is that the row stays CITABLE: its figures and provenance in the
    published report, its per-query detail in the run JSONL, and the configuration it was
    measured under in `evals/configs/retired/`. `test_the_retired_baseline_config_no_longer_
    loads` pins the last of the three.

    The row that isolates the fusion keeps every knob it shared with the baseline, so the
    comparison the published table records stays legible.
    """
    fusion_row = load_config("v2b-fusion")

    assert "v2-hibrido" not in ABLATION_ORDER, "archived rows are cited, not run"
    assert fusion_row.rrf_k == 60 and fusion_row.branch_depth == 60
    assert fusion_row.pos_prefilter is False
    assert fusion_row.signal_pos_id is None, "v2b isolates the fusion, with no signals"


def test_the_signals_row_declares_its_reading_scope_and_its_weight() -> None:
    """Declared in the file, not inferred: a row nobody can read is a row nobody can check."""
    signals = load_config("v3-senales")

    assert signals.signal_pos_id, "the reading scope must be declared"
    assert signals.pos_prefilter is False, (
        "reading must not restrict: otherwise the row measures the reordering and the recall "
        "cost of the prefilter as one number"
    )
    assert signals.business_weight_availability is not None
    # One business weight, and it is the only one: the rotation term was withdrawn, refuted
    # by measurement rather than by argument.
    assert not hasattr(signals, "business_weight_rotation")
    # It is built on v2b, so the fusion must be the same one.
    fusion_row = load_config("v2b-fusion")
    # `fusion` is gone as a key: one composition exists, so the two rows cannot differ in it.
    assert signals.branch_weight_lexical == fusion_row.branch_weight_lexical
    assert signals.branch_weight_vector == fusion_row.branch_weight_vector
    assert signals.coverage_rule == fusion_row.coverage_rule


def test_an_unknown_knob_is_still_refused() -> None:
    """The validation C24 built, unchanged: a misspelt knob would measure something else."""
    from jbg_ai.evals.configs import EvalConfig
    from jbg_ai.evals.errors import ConfigurationError

    with pytest.raises(ConfigurationError, match="unknown keys"):
        EvalConfig.from_mapping(
            {
                "id": "x",
                "kind": "pipeline",
                "label": "x",
                "rationale": "x",
                "uses_provider": False,
                "signal_pos_ids": "typo",
            },
            where="test",
        )
