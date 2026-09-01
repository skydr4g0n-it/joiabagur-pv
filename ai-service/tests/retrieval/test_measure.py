"""Measurement CLI: safe tsquery composition and a clean skip. Delivered by C20.

The composition is asserted here rather than in the library because the library
deliberately does not build queries — C21 does. This is the shape it inherits.
"""

from __future__ import annotations

import pytest

from jbg_ai.retrieval.measure import MeasurementUnavailable, compose_tsquery, main
from jbg_ai.retrieval.synonyms import expand_query


def test_compose_never_concatenates_terms_into_the_sql() -> None:
    expanded = expand_query("sortija de plata", enabled=True)
    fragment, params = compose_tsquery(expanded)

    assert "sortija" not in fragment, "terms travel as parameters, never as SQL text"
    assert "anillo" not in fragment
    assert fragment.count("%s") == len(params)
    assert "sortija" in params
    assert "anillo" in params


def test_compose_ors_inside_a_group_and_ands_between_groups() -> None:
    expanded = expand_query("sortija de plata", enabled=True)
    fragment, _ = compose_tsquery(expanded)

    assert "||" in fragment, "surface forms of one class are alternatives"
    assert "&&" in fragment, "different query terms are conjuncts"
    assert fragment.startswith("(")


def test_compose_handles_a_query_with_no_tokens() -> None:
    expanded = expand_query("   ", enabled=True)
    fragment, params = compose_tsquery(expanded)

    assert fragment.count("%s") == len(params) == 1


def test_measurement_without_a_database_skips_instead_of_failing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A development aid must not become a gate that fails on a laptop with no Docker."""

    def _unavailable(*_args: object, **_kwargs: object) -> None:
        raise MeasurementUnavailable("no index here")

    monkeypatch.setattr("jbg_ai.retrieval.measure.run_measurement", _unavailable)

    assert main(["measure"]) == 0
    assert "skipping measurement" in capsys.readouterr().out
