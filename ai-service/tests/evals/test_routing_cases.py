"""The routing manifest, the projection onto classes, and the veto. C31.

Offline throughout: the manifest resolves against the golden set and the corpus, both of which
are files in git, and no provider is reached. The measurement itself is a separate command.
"""

from __future__ import annotations

from collections import Counter

import pytest

from jbg_ai.assist.schema import RouteDecision
from jbg_ai.evals.routing import (
    C25_ABSTENTION_RATE,
    HARNESS_RETRY_CAUSES,
    ROUTING_CLASSES,
    VETO_CATEGORY,
    VETO_CLASS,
    ConfusionMatrix,
    RoutingCase,
    RoutingCasesError,
    build_matrix,
    false_positive_rate,
    load_routing_cases,
    predicted_class,
    report,
    veto_violations,
)

#: The composition the manifest declares, and the reason it is restated here rather than read
#: from the file: a test that took its expectation from the thing under test would pass on a
#: manifest that quietly halved itself.
DECLARED = {
    "catalog": 48,
    "not_in_catalogue": 20,
    "out_of_domain": 5,
    "knowledge": 32,
    "ambiguous": 4,
    "both": 10,
}


def test_the_manifest_loads_and_its_five_references_resolve() -> None:
    """Task 1.3 and 10.1. Five classes are referenced and not copied, so this is what says the
    references still point at something — the failure a copied fixture hides in silence."""
    cases = load_routing_cases()

    assert len(cases) == sum(DECLARED.values()) == 119
    assert cases.counts() == DECLARED
    assert cases.declared == DECLARED
    assert {case.source for case in cases} == {"golden", "corpus", "corpus_eval", "manifest"}


def test_every_case_carries_a_non_empty_text_and_a_unique_identifier() -> None:
    cases = load_routing_cases()

    assert all(case.text.strip() for case in cases)
    assert len({case.id for case in cases}) == len(cases)
    assert set(cases.counts()) <= set(ROUTING_CLASSES)


def test_the_veto_category_is_present_and_is_the_twelve_unanchored_queries() -> None:
    """The twelve that name **no piece type at all** — the ones the vector branch exists to
    serve, and the ones a classifier that learned the vocabulary instead of the trade silences."""
    catalog = load_routing_cases().of(VETO_CLASS)
    by_category = Counter(case.category for case in catalog)

    assert by_category[VETO_CATEGORY] == 12
    assert sum(by_category.values()) == 48
    assert len(by_category) == 8, "the eight judged categories of the golden set"


def test_a_declared_count_that_does_not_match_the_tree_refuses_the_load(tmp_path) -> None:
    """Task 10.1. **The load fails; it never warns.** A manifest that described 47 cases as 48
    would make a published rate unreproducible in a way nothing later could detect, which is
    the same defect the golden set's own composition check exists to prevent."""
    manifest = tmp_path / "cases.yaml"
    manifest.write_text(
        "version: 1\n"
        "sources:\n"
        "  ambiguous:\n"
        "    from: golden\n"
        "    categories: [ambigua]\n"
        "    expected_count: 99\n"
        "both: []\n",
        encoding="utf-8",
    )

    with pytest.raises(RoutingCasesError) as error:
        load_routing_cases(tmp_path)

    assert "ambiguous" in str(error.value)
    assert "99" in str(error.value)


def test_an_unknown_source_refuses_the_load(tmp_path) -> None:
    manifest = tmp_path / "cases.yaml"
    manifest.write_text(
        "version: 1\nsources:\n  catalog:\n    from: nowhere\n    expected_count: 0\nboth: []\n",
        encoding="utf-8",
    )

    with pytest.raises(RoutingCasesError):
        load_routing_cases(tmp_path)


# --- the projection from a decision onto a class ---------------------------------------------


@pytest.mark.parametrize(
    ("served", "index", "missing_axis", "expected"),
    [
        ("in_domain", "catalog", None, "catalog"),
        ("in_domain", "knowledge", None, "knowledge"),
        ("in_domain", "both", None, "both"),
        ("in_domain", "catalog", "piece_type", "ambiguous"),
        # Ambiguity is read BEFORE the index: a query the classifier admits but cannot search
        # with is answered by a question, whatever index it would otherwise have gone to.
        ("in_domain", "both", "price", "ambiguous"),
        # The two refusals come first of all: `index` is null on both, and reading it first
        # would make every refusal look like a missing route.
        ("out_of_domain", None, None, "out_of_domain"),
        ("not_in_catalogue", None, None, "not_in_catalogue"),
        ("out_of_domain", None, "piece_type", "out_of_domain"),
    ],
)
def test_a_decision_projects_onto_exactly_one_class(
    served, index, missing_axis, expected
) -> None:
    decision = RouteDecision(served=served, index=index, missing_axis=missing_axis)

    assert predicted_class(decision) == expected
    assert predicted_class(decision) in ROUTING_CLASSES


# --- the matrix, the two rates and the veto ---------------------------------------------------


def _case(identifier: str, expected: str, category: str | None = None) -> RoutingCase:
    return RoutingCase(
        id=identifier, text=identifier, expected=expected, source="test", category=category
    )


def test_the_matrix_counts_degradations_apart_from_predictions() -> None:
    matrix = ConfusionMatrix()
    matrix.record("catalog", "catalog")
    matrix.record("catalog", "out_of_domain")
    matrix.record("catalog", None)

    assert matrix.total("catalog") == 3
    assert matrix.correct("catalog") == 1
    assert matrix.degraded["catalog"] == 1
    assert matrix.rows["catalog"]["degraded"] == 1


def test_the_false_positive_on_the_answerable_class_counts_refusals_and_not_misroutes() -> None:
    """A `catalog` query sent to `knowledge` shows the operator an explanation instead of
    pieces, which is recoverable. One that is REFUSED shows nothing at all, which is the
    failure at the counter — so the two are not the same number and only one decides."""
    matrix = ConfusionMatrix()
    for predicted in ("catalog", "catalog", "knowledge", "out_of_domain"):
        matrix.record("catalog", predicted)

    assert matrix.accuracy("catalog") == 0.5
    assert false_positive_rate(matrix) == 0.25


def test_a_single_silenced_answerable_query_is_a_veto_violation() -> None:
    """D12, declared before measuring precisely so that it cannot be softened afterwards."""
    results = [
        (_case("q01", VETO_CLASS, VETO_CATEGORY), "catalog"),
        (_case("q02", VETO_CLASS, VETO_CATEGORY), "out_of_domain"),
        (_case("g01", "not_in_catalogue"), "not_in_catalogue"),
    ]

    violations = veto_violations(results)

    assert [case.id for case in violations] == ["q02"]


def test_a_misroute_within_the_answerable_class_is_not_a_veto_violation() -> None:
    results = [(_case("q01", VETO_CLASS, VETO_CATEGORY), "knowledge")]

    assert veto_violations(results) == ()


def test_a_run_that_degraded_cannot_pass_the_veto() -> None:
    """**Measured, and it is the defect this assertion exists for.** A `gpt-4o` arm whose 89 of
    119 cases died of rate limits reported zero violations and PASSED, because a degraded case
    is never a refusal. A criterion a broken run satisfies is not a criterion.
    """
    cases = [_case("q01", VETO_CLASS, VETO_CATEGORY), _case("q02", VETO_CLASS, VETO_CATEGORY)]
    results = [(cases[0], "catalog", None), (cases[1], None, "RateLimitError")]
    matrix, per_category = build_matrix(results)

    payload = report(
        matrix,
        violations=veto_violations([(case, predicted) for case, predicted, _ in results]),
        meta={"run_id": "r", "git_sha": "g", "prompt_version": "p", "model": "m", "taken_at": "t"},
        per_category=per_category,
        results_for_coverage=[(case, predicted) for case, predicted, _ in results],
    )

    assert payload["veto"]["violations"] == []
    assert payload["veto"]["veto_class_degraded"] == 1
    assert payload["veto"]["passed"] is False


def test_a_fully_measured_clean_run_passes_the_veto() -> None:
    cases = [_case("q01", VETO_CLASS, VETO_CATEGORY), _case("q02", VETO_CLASS, VETO_CATEGORY)]
    results = [(cases[0], "catalog", None), (cases[1], "catalog", None)]
    matrix, per_category = build_matrix(results)

    payload = report(
        matrix,
        violations=(),
        meta={"run_id": "r", "git_sha": "g", "prompt_version": "p", "model": "m", "taken_at": "t"},
        per_category=per_category,
        results_for_coverage=[(case, predicted) for case, predicted, _ in results],
    )

    assert payload["veto"]["passed"] is True
    assert payload["degraded_total"] == 0


def test_the_report_keeps_the_two_rates_apart_and_says_they_are_not_summable() -> None:
    """HU escenario 15. Two mechanisms, two rows, and the note that forbids adding them."""
    matrix = ConfusionMatrix()
    matrix.record("catalog", "catalog")
    matrix.record("not_in_catalogue", "not_in_catalogue")

    payload = report(
        matrix,
        violations=(),
        meta={"run_id": "r", "git_sha": "g", "prompt_version": "p", "model": "m", "taken_at": "t"},
    )
    rates = payload["rates"]

    assert rates["router_refusal_rate"] == 0.5
    assert rates["retriever_abstention_rate"] == C25_ABSTENTION_RATE
    assert rates["summable"] is False
    assert "NOT summable" in rates["note"]
    assert rates["retriever_abstention_source"]
    # The false positive over the answerable class is a THIRD figure and not either of them.
    assert "false_positive_on_answerable" in payload
    assert payload["false_positive_on_answerable"]["class"] == VETO_CLASS


def test_the_report_declares_the_three_limitations_before_anyone_reads_the_numbers() -> None:
    payload = report(
        ConfusionMatrix(),
        violations=(),
        meta={"run_id": "r", "git_sha": "g", "prompt_version": "p", "model": "m", "taken_at": "t"},
    )
    joined = " ".join(payload["limitations"])

    assert "CONSTRUCTED" in joined, "the ten `both` cases"
    assert "UPPER BOUND" in joined, "the twenty were chosen to be unsatisfiable"
    assert "vocabularies.yaml" in joined and "note" in joined, "D11's provenance"


def test_the_harness_retries_a_rate_limit_and_never_a_parse_failure() -> None:
    """The one place the harness departs from the serving path, and it is one-sided.

    A rate limit says this sweep asked too fast; a reply that does not parse is exactly the
    degradation being measured, and re-rolling it would publish the best of N attempts as the
    behaviour of one.
    """
    assert "RateLimitError" in HARNESS_RETRY_CAUSES
    assert "parse" not in HARNESS_RETRY_CAUSES
    assert "timeout" not in HARNESS_RETRY_CAUSES


def test_the_results_are_tied_to_a_run_id_a_sha_and_a_prompt_version() -> None:
    """Task 10.7. A result that cannot be tied to the tree that produced it is a number."""
    from jbg_ai.evals.routing import provenance

    meta = provenance(model="openai/gpt-4o-mini")

    assert set(meta) == {"run_id", "git_sha", "prompt_version", "model", "taken_at"}
    assert meta["prompt_version"].startswith("router/")
