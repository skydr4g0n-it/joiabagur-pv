"""Provenance, reproducibility, the default-changing rule and the artifact-first sink. C24."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from jbg_ai.config.settings import FUSION_DEFAULTS
from jbg_ai.evals.errors import EvaluationUnavailable
from jbg_ai.evals.latency import LatencySummary, Sample, StageCollector, summarise
from jbg_ai.evals.metrics import AVERAGED, Aggregate, CaseMetrics
from jbg_ai.evals.pricing import load_prices
from jbg_ai.evals.provenance import UNKNOWN_SHA, Provenance, index_set_hash
from jbg_ai.evals.report import write
from jbg_ai.evals.runner import ConfigReport, Report
from jbg_ai.evals.sweep import (
    CATEGORY_TOLERANCE,
    MATERIAL_DELTA,
    WEIGHT_VECTOR_GRID,
    SweepPoint,
    decide,
)
from jbg_ai.evals.vectors import FrozenEmbeddingClient, FrozenVector, load_vectors, write_vectors

A = UUID("aaaaaaaa-0000-0000-0000-000000000000")
B = UUID("bbbbbbbb-0000-0000-0000-000000000000")


def _provenance(**overrides: object) -> Provenance:
    values: dict = {
        "golden_set_version": "1:abc",
        "config_id": "v2-hibrido",
        "index_set_hash": "0" * 64,
        "embedding_model_version_key": "openai/text-embedding-3-small:1536",
        "git_sha": "a03b4ad",
    }
    values.update(overrides)
    return Provenance(**values)  # type: ignore[arg-type]


def test_two_runs_with_the_same_provenance_are_comparable() -> None:
    assert _provenance().comparable_with(_provenance())
    assert _provenance().differences(_provenance()) == ()


def test_a_moved_index_makes_two_runs_incomparable_and_names_what_moved() -> None:
    other = _provenance(index_set_hash="f" * 64)

    assert not _provenance().comparable_with(other)
    assert _provenance().differences(other) == ("index_set_hash",)


def test_a_different_configuration_is_the_point_of_an_ablation_table() -> None:
    """`config_id` is what the table varies, so it never makes two rows incomparable."""
    other = _provenance(config_id="v1-vectorial")

    assert _provenance().comparable_with(other)
    assert _provenance().differences(other) == ("config_id",)


def test_a_lexical_baseline_records_no_embedding_model_and_that_is_an_answer() -> None:
    """NULL means "does not depend on the embedder", so a model change cannot invalidate it."""
    lexical = _provenance(config_id="v0-fts", embedding_model_version_key=None)

    assert lexical.as_dict()["embedding_model_version_key"] is None
    assert lexical.comparable_with(
        _provenance(config_id="v0-nombre", embedding_model_version_key=None)
    )


def test_an_unavailable_revision_is_recorded_as_unknown_and_never_guessed() -> None:
    unknown = _provenance(git_sha=UNKNOWN_SHA)

    assert not unknown.comparable_with(_provenance())


def test_the_index_fingerprint_notices_a_swapped_document() -> None:
    """Not a count and not a maximum timestamp: those miss a set that lost one and gained one."""
    before = index_set_hash([A, B])
    after = index_set_hash([A, UUID("cccccccc-0000-0000-0000-000000000000")])

    assert before != after
    assert index_set_hash([A, B]) == index_set_hash([B, A]), "order of the input is irrelevant"


def test_frozen_vectors_round_trip_at_six_decimals(tmp_path: Path) -> None:
    write_vectors(
        [
            FrozenVector(
                query_id="q1",
                text="anillo de plata",
                model_version_key="m:1536",
                vector=(0.1234567, -0.7654321),
            )
        ],
        tmp_path,
    )

    stored = load_vectors(tmp_path)

    assert stored[0].vector == (0.123457, -0.765432)


def test_the_harness_refuses_to_embed_on_the_fly(tmp_path: Path) -> None:
    """A run that silently calls the provider is a run nobody can repeat."""
    write_vectors(
        [
            FrozenVector(
                query_id="q1", text="anillo", model_version_key="m:1536", vector=(0.5,)
            )
        ],
        tmp_path,
    )
    client = FrozenEmbeddingClient.from_file("m", tmp_path)

    with pytest.raises(EvaluationUnavailable, match="no frozen vector"):
        import asyncio

        asyncio.run(client.embed(["una consulta que nadie congeló"]))


def test_a_missing_vector_file_names_the_command_that_creates_it(tmp_path: Path) -> None:
    with pytest.raises(EvaluationUnavailable, match="freeze-vectors"):
        FrozenEmbeddingClient.from_file("m", tmp_path)


# ------------------------------------------------------------------------------- latency


def test_retrieval_latency_excludes_the_provider_round_trip() -> None:
    """The criterion is about this service, and the provider is 170-1707 ms of somebody else's."""
    sample = Sample(query_id="q1", e2e_ms=900.0, provider_ms=800.0, lexical_ms=12.0)

    assert sample.retrieval_ms == 100.0


def test_a_provider_faster_than_the_measurement_cannot_produce_a_negative() -> None:
    sample = Sample(query_id="q1", e2e_ms=10.0, provider_ms=12.0, lexical_ms=1.0)

    assert sample.retrieval_ms == 0.0


def test_the_cold_execution_is_excluded_from_the_percentiles_and_still_reported() -> None:
    warm = [Sample("q1", 100.0, 0.0, 5.0), Sample("q1", 110.0, 0.0, 5.0)]
    cold = [Sample("q1", 900.0, 0.0, 5.0)]

    summary = summarise(warm, cold=cold)

    assert summary.p95_e2e == 110.0
    assert summary.cold_e2e_ms == 900.0
    assert summary.samples == 2


def test_an_empty_sample_reports_nothing_rather_than_zero() -> None:
    summary = summarise([])

    assert summary.p50_retrieval is None
    assert summary.as_dict()["p95_e2e_ms"] is None


def test_the_collector_reads_the_stages_the_orchestrator_already_logs() -> None:
    import logging

    with StageCollector() as collector:
        logging.getLogger("jbg_ai.retrieval.orchestrator").info(
            "stage=embed trace_id=x latency_ms=170.5 model=m cache_hits=0"
        )
        logging.getLogger("jbg_ai.retrieval.orchestrator").info(
            "stage=fuse trace_id=x typed=1 expanded=2 vector=3"
        )

    assert collector.total("embed") == 170.5
    assert collector.total("fuse") == 0.0, "a stage without a latency contributes none"


# ---------------------------------------------------------------------------------- D13


#: Every averaged metric, so a fixture cannot pass by leaving one out of the report.
_ZEROED = {name: 0.0 for name in AVERAGED}


def _config_report(config_id: str, ndcg: dict[str, float], categories: dict[str, float]):
    return ConfigReport(
        config_id=config_id,
        label=config_id,
        provenance=_provenance(config_id=config_id),
        readings={
            name: Aggregate(queries=48, values={**_ZEROED, "ndcg_at_5": value})
            for name, value in ndcg.items()
        },
        by_origin={},
        by_category={
            name: Aggregate(queries=5, values={"ndcg_at_5": value})
            for name, value in categories.items()
        },
        abstention_rate=0.0,
        latency=summarise([]),
        cost_per_query_usd=0.0,
        documents_omitted=0,
        cases=(),
        ranked={},
    )


def _point(weight: float, ndcg: dict[str, float], categories: dict[str, float]) -> SweepPoint:
    return SweepPoint(
        weight_vector=weight,
        branch_depth=60,
        report=_config_report(f"w{weight}", ndcg, categories),
    )


def test_a_small_improvement_does_not_move_a_default() -> None:
    baseline = _point(0.33, {"global": 0.60, "tuning": 0.60, "new": 0.60}, {"piedra": 0.5})
    better = _point(1.0, {"global": 0.64, "tuning": 0.64, "new": 0.64}, {"piedra": 0.5})

    verdict = decide(baseline, [better])

    assert verdict.moved is False
    assert str(MATERIAL_DELTA) in verdict.reason


def test_a_result_that_only_holds_on_the_tuning_subset_is_not_a_confirmation() -> None:
    baseline = _point(0.33, {"global": 0.60, "tuning": 0.60, "new": 0.60}, {"piedra": 0.5})
    fitted = _point(1.0, {"global": 0.70, "tuning": 0.95, "new": 0.55}, {"piedra": 0.5})

    verdict = decide(baseline, [fitted])

    assert verdict.moved is False
    assert "'new'" in verdict.reason or "new" in verdict.reason


def test_a_category_paying_for_the_average_blocks_the_change() -> None:
    baseline = _point(0.33, {"global": 0.60, "tuning": 0.60, "new": 0.60}, {"piedra": 0.80})
    lopsided = _point(1.0, {"global": 0.70, "tuning": 0.70, "new": 0.70}, {"piedra": 0.60})

    verdict = decide(baseline, [lopsided])

    assert verdict.moved is False
    assert "piedra" in verdict.reason
    assert str(CATEGORY_TOLERANCE) in verdict.reason


def test_a_material_improvement_in_every_reading_moves_the_default() -> None:
    baseline = _point(0.33, {"global": 0.60, "tuning": 0.60, "new": 0.60}, {"piedra": 0.50})
    better = _point(1.0, {"global": 0.70, "tuning": 0.68, "new": 0.71}, {"piedra": 0.49})

    verdict = decide(baseline, [better])

    assert verdict.moved is True
    assert verdict.best.weight_vector == 1.0


def test_the_sweep_is_directional_and_never_looks_below_the_value_in_force() -> None:
    """The rubric that fixed the live weight is the lexical branch's own objective function."""
    assert min(WEIGHT_VECTOR_GRID) == FUSION_DEFAULTS["jpv_rrf_weight_vector"]


def test_the_sweep_grid_and_the_production_default_are_separate_constants() -> None:
    """The rule inherited from the previous change: one constant may not do both jobs.

    A constant that steers a measurement AND asserts a production default keeps a test green
    while the defect ships, because the two numbers live on different scales. Here the grid
    READS the default as its floor and never redefines it.
    """
    import inspect

    from jbg_ai.evals import sweep as module

    source = inspect.getsource(module)
    assert "FUSION_DEFAULTS" in source
    assert "jpv_rrf_weight_vector = " not in source


# --------------------------------------------------------------------------- artifact-first


def _report(tmp_path: Path) -> Report:
    case = CaseMetrics(
        query_id="q1",
        ndcg_at_5=0.5,
        ndcg_at_5_binary=0.6,
        recall_at_5=0.4,
        recall_at_5_capped=0.8,
        precision_at_3=0.33,
        mrr=1.0,
        unjudged_at_5=0.0,
        synthetic_displacement_at_5=False,
        rerank_headroom=False,
        abstained=False,
        relevant_total=3,
    )
    item = _config_report("v2-hibrido", {"global": 0.5, "tuning": 0.5, "new": 0.5}, {"x": 0.5})
    item = replace(item, cases=(case,), ranked={"q1": (str(A),)}, latency=summarise([]))
    return Report(
        run_id=str(uuid4()),
        generated_at=datetime(2026, 9, 7, tzinfo=UTC),
        golden_set_version="1:abc",
        index_set_hash="0" * 64,
        git_sha="a03b4ad",
        corpus_size=1168,
        configs=(item,),
        distance_distribution={},
        stale_judgements=0,
        price_list=load_prices(),
    )


def test_a_run_without_persistence_still_writes_its_report(tmp_path: Path) -> None:
    """The producer does not know the database exists, so its absence changes nothing."""
    report = _report(tmp_path)

    target = write(report, title="t", name="r.md", out_dir=tmp_path)

    assert target.is_file()
    detail = tmp_path / "runs" / f"{report.run_id}.jsonl"
    assert detail.is_file()
    row = json.loads(detail.read_text(encoding="utf-8").splitlines()[0])
    assert row["query_id"] == "q1"
    assert row["ranked"] == [str(A)]


def test_the_runner_does_not_import_the_persistence_module() -> None:
    """The direction of that dependency is the design decision, so it is asserted."""
    import inspect

    from jbg_ai.evals import runner

    source = inspect.getsource(runner)
    imports = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
    assert not [line for line in imports if "repository" in line]
    assert "from jbg_ai.evals.repository" not in source


def test_the_report_publishes_both_readings_and_the_three_splits(tmp_path: Path) -> None:
    body = write(_report(tmp_path), title="t", name="r.md", out_dir=tmp_path).read_text(
        encoding="utf-8"
    )

    assert "nDCG@5 bin" in body
    for reading in ("global", "tuning", "new"):
        assert f"| {reading} |" in body
    assert "no son comparables" in body


def test_the_report_marks_the_abstention_figures_provisional(tmp_path: Path) -> None:
    body = write(_report(tmp_path), title="t", name="r.md", out_dir=tmp_path).read_text(
        encoding="utf-8"
    )

    assert "**Provisional.**" in body
    assert "no** toca el umbral" in body


def test_a_latency_summary_carries_both_figures() -> None:
    summary: LatencySummary = summarise(
        [Sample("q1", 300.0, 200.0, 10.0), Sample("q1", 320.0, 210.0, 11.0)]
    )

    values = summary.as_dict()
    assert values["p95_retrieval_ms"] is not None
    assert values["p95_e2e_ms"] is not None
    assert values["p95_retrieval_ms"] < values["p95_e2e_ms"]


def _two_configs(tmp_path: Path, first: dict[str, float], second: dict[str, float]) -> Report:
    def _item(config_id: str, values: dict[str, float]) -> ConfigReport:
        item = _config_report(
            config_id, {"global": values["graded"], "tuning": 0.5, "new": 0.5}, {"x": 0.5}
        )
        readings = dict(item.readings)
        readings["global"] = Aggregate(
            queries=48,
            values={
                **_ZEROED,
                "ndcg_at_5": values["graded"],
                "ndcg_at_5_binary": values["binary"],
            },
        )
        return replace(item, readings=readings, latency=summarise([]))

    return replace(
        _report(tmp_path), configs=(_item("v1", first), _item("v2", second))
    )


def test_agreeing_readings_are_reported_as_a_robustness_result(tmp_path: Path) -> None:
    report = _two_configs(
        tmp_path, {"graded": 0.7, "binary": 0.8}, {"graded": 0.5, "binary": 0.6}
    )

    body = write(report, title="t", name="r.md", out_dir=tmp_path).read_text(encoding="utf-8")

    assert "ordenan las configuraciones **igual**" in body
    assert "no es robusta" not in body


def test_disagreeing_readings_are_surfaced_as_a_finding(tmp_path: Path) -> None:
    """Publishing both scales only answers the objection if a disagreement is stated."""
    report = _two_configs(
        tmp_path, {"graded": 0.7, "binary": 0.4}, {"graded": 0.5, "binary": 0.9}
    )

    body = write(report, title="t", name="r.md", out_dir=tmp_path).read_text(encoding="utf-8")

    assert "las dos lecturas no coinciden" in body
    assert "**no es robusta**" in body
    assert "`v1, v2`" in body and "`v2, v1`" in body


def _with_unjudged(tmp_path: Path, share: float) -> Report:
    item = _config_report("v3-futuro", {"global": 0.6, "tuning": 0.6, "new": 0.6}, {"x": 0.5})
    readings = dict(item.readings)
    readings["global"] = Aggregate(
        queries=48, values={**_ZEROED, "ndcg_at_5": 0.6, "unjudged_at_5": share}
    )
    return replace(_report(tmp_path), configs=(replace(item, readings=readings),))


def test_a_configuration_promoting_unjudged_documents_is_not_presented_as_final(
    tmp_path: Path,
) -> None:
    """Unjudged scores as irrelevant, so a row full of it is unmeasured rather than bad.

    Every configuration reports zero today because the pool was built from these same
    configurations. The mark exists for the ones that come next: a change that reorders results
    can promote documents nobody judged, and that is exactly when it has to fire.
    """
    from jbg_ai.evals.report import NOT_COMPARABLE_UNJUDGED

    body = write(
        _with_unjudged(tmp_path, NOT_COMPARABLE_UNJUDGED + 0.2),
        title="t",
        name="r.md",
        out_dir=tmp_path,
    ).read_text(encoding="utf-8")

    assert "⚠ **no comparable**" in body
    assert "**Filas no comparables:" in body
    assert "resultado desconocido" in body


def test_a_fully_judged_row_is_not_marked(tmp_path: Path) -> None:
    body = write(
        _with_unjudged(tmp_path, 0.0), title="t", name="r.md", out_dir=tmp_path
    ).read_text(encoding="utf-8")

    assert "⚠ **no comparable**" not in body
    assert "**Filas no comparables:" not in body


def test_unverifiable_prices_are_declared_rather_than_invented(tmp_path: Path) -> None:
    """A price taken from memory looks exactly like a measured one, which is the danger."""
    from jbg_ai.evals.pricing import UNKNOWN, PriceList

    report = replace(
        _report(tmp_path),
        price_list=PriceList(as_of=UNKNOWN, source=UNKNOWN, verified=False, models={}),
    )

    body = write(report, title="t", name="r.md", out_dir=tmp_path).read_text(encoding="utf-8")

    assert "**NO VERIFICADOS**" in body
    assert "unknown" in body


def test_a_file_claiming_to_be_verified_without_a_date_is_not_believed(tmp_path: Path) -> None:
    """`verified: true` next to an unknown date is the shape of a lie, so the loader refuses it."""
    from jbg_ai.evals.pricing import load_prices

    (tmp_path / "pricing.yaml").write_text(
        "\n".join(
            [
                "as_of: unknown",
                "source: https://example.invalid",
                "verified: true",
                "models: {}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert load_prices(tmp_path).verified is False
