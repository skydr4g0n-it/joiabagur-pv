"""Measurement CLI: safe tsquery composition and a clean skip. Delivered by C20.

The composition is asserted here rather than in the library because the library
deliberately does not build queries — C21 does. This is the shape it inherits.
"""

from __future__ import annotations

import pytest

from jbg_ai.retrieval.lexical import build_fragments, expanded_request
from jbg_ai.retrieval.measure import (
    COMPARISON_ARMS,
    MeasurementUnavailable,
    _is_hit,
    _rubric,
    compose_tsquery,
    main,
)
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


def test_comparison_without_a_database_skips_instead_of_failing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The C21 arm comparison is a development aid too, never part of the unit suite."""

    def _unavailable(*_args: object, **_kwargs: object) -> None:
        raise MeasurementUnavailable("no index here")

    monkeypatch.setattr("jbg_ai.retrieval.measure.run_comparison", _unavailable)

    assert main(["compare"]) == 0
    assert "skipping measurement" in capsys.readouterr().out


def test_the_comparison_arms_are_the_two_endpoints_and_the_shipped_default() -> None:
    arms = {name: (typed, expanded, vector) for name, typed, expanded, vector in COMPARISON_ARMS}

    assert arms["vector-only"][2] > 0 and arms["vector-only"][:2] == (0.0, 0.0)
    assert arms["lexical-only"][2] == 0.0
    assert arms["fused-default"] == (0.5, 0.5, 0.33)


def test_the_rubric_is_read_off_the_query_itself() -> None:
    """A hit is a top-ten result with the right piece type and the right material (C20's rubric)."""
    piece, materials = _rubric(expand_query("sortija de plata", enabled=True))

    assert piece == "anillo"
    assert materials == ("plata",)
    assert _is_hit({"piece_type": "anillo", "materials": ["plata"]}, piece, materials)
    assert not _is_hit({"piece_type": "pulsera", "materials": ["plata"]}, piece, materials)
    assert not _is_hit({"piece_type": "anillo", "materials": ["oro"]}, piece, materials)


def test_the_comparison_lexical_sql_binds_every_term_by_name() -> None:
    """Named placeholders, so a fragment repeated in ORDER BY and WHERE binds once."""
    fragments = build_fragments(
        expanded_request(expand_query("sortija de plata", enabled=True)),
        placeholder=lambda name: f"%({name})s",
    )

    assert "%(lex_0)s" in fragments.match
    assert "sortija" not in fragments.match
    assert set(fragments.params.values()) >= {"sortija", "anillo", "plata"}
