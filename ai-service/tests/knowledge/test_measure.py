"""The mini-measurement, and what it is allowed to touch. Delivered by C23."""

from __future__ import annotations

import ast
import json

import pytest

from jbg_ai.knowledge.constants import SIDECAR_PATH
from jbg_ai.knowledge.corpus import KnowledgeCorpus
from jbg_ai.knowledge.measure import (
    build_fixture,
    calibrated_threshold,
    load_out_of_domain,
    measure,
    sweep,
)
from support.paths import AI_SERVICE_ROOT

CALIBRATED = 0.81


def test_the_fixture_holds_one_question_per_document_plus_the_out_of_domain_group(
    corpus: KnowledgeCorpus,
) -> None:
    cases = build_fixture(corpus)
    in_domain = [case for case in cases if not case.out_of_domain]
    out_of_domain = [case for case in cases if case.out_of_domain]

    assert len(in_domain) == len(corpus) == 32
    assert {case.expected_document for case in in_domain} == {
        document.slug for document in corpus
    }
    assert 4 <= len(out_of_domain) <= 6
    assert all(case.question for case in cases)


def test_out_of_domain_questions_are_versioned_beside_the_corpus() -> None:
    questions = load_out_of_domain()
    assert questions
    assert all(case.expected_document is None for case in questions)


def test_the_sidecar_records_how_the_corpus_was_produced(corpus: KnowledgeCorpus) -> None:
    """Authorship does not vary between documents, so it is recorded once and not per row.

    And the counts it publishes are the ones the README declares, so a corpus that grew
    without the sidecar being rewritten is a detectable defect rather than a stale sentence
    somewhere in the documentation.
    """
    payload = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))

    for field in ("generator_version", "model", "prompt_version", "generated_at", "authorship"):
        assert payload.get(field), field

    assert payload["document_count"] == len(corpus)
    assert payload["section_count"] == corpus.section_count
    assert payload["counts_by_doc_type"] == corpus.counts_by_doc_type()
    assert payload["counts_by_claim_scope"] == corpus.counts_by_claim_scope()
    # The figure the README publishes as the share of illustrative commitments.
    assert payload["ratios_by_claim_scope"]["establecimiento"] == 15.5


def test_the_measurement_runs_offline_and_is_reproducible(corpus: KnowledgeCorpus) -> None:
    first = measure(threshold=CALIBRATED, hybrid_enabled=True, corpus=corpus)
    second = measure(threshold=CALIBRATED, hybrid_enabled=True, corpus=corpus)

    assert first.recall_at_3 == second.recall_at_3
    assert first.mrr == second.mrr
    assert first.abstention_rate == second.abstention_rate
    assert 0.0 <= first.recall_at_3 <= 1.0
    assert 0.0 <= first.mrr <= 1.0


def test_out_of_domain_questions_are_scored_as_abstentions(
    corpus: KnowledgeCorpus,
) -> None:
    report = measure(threshold=CALIBRATED, hybrid_enabled=True, corpus=corpus)

    assert report.out_of_domain
    assert report.abstention_rate == 1.0
    assert report.false_citations == [], (
        "a returned citation for an out-of-domain question counts as a failure"
    )


def test_the_calibrated_default_is_the_one_the_settings_carry(
    corpus: KnowledgeCorpus,
) -> None:
    """The default in `Settings` is the measured value, not a number chosen by eye."""
    from jbg_ai.config.settings import Settings

    assert Settings.model_fields["jpv_knowledge_distance_threshold"].default == CALIBRATED

    report = measure(threshold=CALIBRATED, hybrid_enabled=True, corpus=corpus)
    assert not report.false_citations


def test_the_fused_configuration_beats_vector_only(corpus: KnowledgeCorpus) -> None:
    """D7's question, answered with the number rather than with the intuition."""
    hybrid = measure(threshold=CALIBRATED, hybrid_enabled=True, corpus=corpus)
    vector = measure(threshold=CALIBRATED, hybrid_enabled=False, corpus=corpus)

    assert hybrid.recall_at_3 > vector.recall_at_3
    assert hybrid.mrr > vector.mrr


def test_the_measurement_reads_and_writes_no_evaluation_table() -> None:
    """`ai.eval_run`, `ai.eval_case` and `ai.eval_result` belong to C24.

    Scanned over the **code** rather than the file: docstrings in this package name those
    tables on purpose, to record why they are not used, and a check that could not tell
    prose from a statement would punish the explanation.
    """
    tables = ("eval_run", "eval_case", "eval_result")

    for path in (AI_SERVICE_ROOT / "src/jbg_ai/knowledge").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            ast.get_docstring(node, clean=False)
            for node in ast.walk(tree)
            if isinstance(
                node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
            )
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value not in docstrings
            ):
                for table in tables:
                    assert table not in node.value, f"{path.name} names {table} in a literal"
            if isinstance(node, ast.Name):
                assert node.id not in tables, f"{path.name} names {node.id}"
            if isinstance(node, ast.Attribute):
                assert node.attr not in tables, f"{path.name} names {node.attr}"


@pytest.mark.slow
def test_the_calibration_rule_picks_the_strictest_safe_threshold(
    corpus: KnowledgeCorpus,
) -> None:
    reports = sweep([0.75, 0.78, 0.81, 0.83, 0.85, 0.90], corpus=corpus)
    best = calibrated_threshold(reports)

    assert best is not None
    assert best.threshold == CALIBRATED
    assert not best.false_citations

    by_threshold = {report.threshold: report for report in reports}
    # Loosening past the calibrated value buys no recall at all — 0.81 and 0.83 answer the
    # same questions — and past 0.84 it starts citing out-of-domain ones. So the rule's own
    # word does the work: of the thresholds that tie on recall, the **strictest** wins.
    assert by_threshold[0.83].recall_at_3 == by_threshold[CALIBRATED].recall_at_3
    assert not by_threshold[0.83].false_citations
    assert by_threshold[0.85].false_citations
    assert by_threshold[0.78].recall_at_3 < by_threshold[CALIBRATED].recall_at_3
