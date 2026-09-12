"""Loading the golden set FAILS when its composition cannot arbitrate what it exists for. C24.

One test per row of the traceability matrix, each with a golden set that breaks exactly that
row and nothing else. The matrix is the containment of the structural risk of this change: the
set is written by the person who built the retriever, in the vocabulary of the catalogue he
also wrote, so left alone it would fill up with `<tipo> de <material>` queries and confirm the
previous rubric by construction.

A documented intention would not survive the first hurried edit. A failing load does.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from jbg_ai.evals.errors import GoldenSetError
from jbg_ai.evals.golden import load_golden_set


def test_the_reference_set_loads(golden_factory: Callable[..., Path]) -> None:
    """The fixture sits exactly at the minimums, so every later test breaks one thing only."""
    golden = load_golden_set(golden_factory())

    assert len(golden.judged_queries) >= 45
    assert golden.version.startswith("1:")


def test_a_set_without_an_annotation_criterion_is_refused(
    golden_factory: Callable[..., Path],
) -> None:
    with pytest.raises(GoldenSetError, match="criterion"):
        load_golden_set(golden_factory(criterion=False))


def test_too_few_unanchored_queries_fails_the_load(
    golden_factory: Callable[..., Path],
) -> None:
    """The pleito this set exists for: queries only the vector branch can answer."""

    def reachable(judgements: list[dict]) -> list[dict]:
        for item in judgements:
            if item["query_id"] == "u00":
                item["lexically_reachable"] = True
        return judgements

    with pytest.raises(GoldenSetError) as exc:
        load_golden_set(golden_factory(mutate_judgements=reachable))

    assert exc.value.requirement == "P1 vector vs lexical"
    assert "11 of the 12" in str(exc.value)


def test_a_subjective_query_that_names_a_material_does_not_count(
    golden_factory: Callable[..., Path],
) -> None:
    """Naming a 89 %-coverage field means the sparse one is not what answered it."""

    def anchor(queries: list[dict]) -> list[dict]:
        for item in queries:
            if item["id"] == "s00":
                item["text"] = "un anillo de plata para una boda"
        return queries

    with pytest.raises(GoldenSetError) as exc:
        load_golden_set(golden_factory(mutate_queries=anchor))

    assert exc.value.requirement == "P3 subjective"


def test_four_queries_about_one_stone_do_not_satisfy_the_stone_requirement(
    golden_factory: Callable[..., Path],
) -> None:
    def one_stone(queries: list[dict]) -> list[dict]:
        for item in queries:
            if item.get("isolates_stone"):
                item["text"] = "anillo con onix"
                item["isolates_stone"] = "onix"
        return queries

    with pytest.raises(GoldenSetError) as exc:
        load_golden_set(golden_factory(mutate_queries=one_stone))

    assert exc.value.requirement == "P3 stone"
    assert "distinct stones" in str(exc.value)


def test_a_declared_synonym_kind_the_dictionary_does_not_corroborate_fails(
    golden_factory: Callable[..., Path],
) -> None:
    """A label is not a test. The class has to be one the query actually exercises."""

    def mislabel(queries: list[dict]) -> list[dict]:
        for item in queries:
            if item["id"] in {"y04", "y05"}:
                item["synonym_kind"] = "bridge"
                item["text"] = "dije de plata"  # a commercial synonym, not a bridge
        return queries

    with pytest.raises(GoldenSetError) as exc:
        load_golden_set(golden_factory(mutate_queries=mislabel))

    assert exc.value.requirement == "P4 synonyms/bridge"


def test_each_synonym_class_needs_its_own_queries(
    golden_factory: Callable[..., Path],
) -> None:
    def drop_stemmer(queries: list[dict]) -> list[dict]:
        for item in queries:
            if item["id"] == "y00":
                item["text"] = "dije de plata"
                item["synonym_kind"] = "commercial"
        return queries

    with pytest.raises(GoldenSetError) as exc:
        load_golden_set(golden_factory(mutate_queries=drop_stemmer))

    assert exc.value.requirement == "P4 synonyms/stemmer"


def test_nonsense_does_not_satisfy_the_out_of_domain_category(
    golden_factory: Callable[..., Path],
) -> None:
    """Every configuration abstains on nonsense, so the metric would discriminate nothing."""

    def gibberish(queries: list[dict]) -> list[dict]:
        for item in queries:
            if item["id"] == "o00":
                item["text"] = "xyzzy quimbombo alfanumerico"
        return queries

    with pytest.raises(GoldenSetError) as exc:
        load_golden_set(golden_factory(mutate_queries=gibberish))

    assert exc.value.requirement == "P5 abstention"
    assert "nonsense" in str(exc.value)


def test_an_answerable_out_of_domain_query_is_refused(
    golden_factory: Callable[..., Path],
) -> None:
    def answerable(judgements: list[dict]) -> list[dict]:
        for item in judgements:
            if item["query_id"] == "o01":
                item["grade"] = 2
        return judgements

    with pytest.raises(GoldenSetError) as exc:
        load_golden_set(golden_factory(mutate_judgements=answerable))

    assert exc.value.requirement == "P5 abstention"
    assert "measures ranking and not abstention" in str(exc.value)


def test_a_literal_query_must_actually_be_the_literal(
    golden_factory: Callable[..., Path],
) -> None:
    """Where the pre-existing substring searcher can win. Omitting it is not a fair comparison."""

    def paraphrase(queries: list[dict]) -> list[dict]:
        for item in queries:
            if item["id"] == "l00":
                item["text"] = "el anillo de pared seca"  # a description, not the name
        return queries

    with pytest.raises(GoldenSetError) as exc:
        load_golden_set(golden_factory(mutate_queries=paraphrase))

    assert exc.value.requirement == "P7 decision 12"


def test_a_wholly_synthetic_category_is_refused(
    golden_factory: Callable[..., Path],
) -> None:
    """The annotator wrote the synthetic corpus; a single-origin category is not comparable."""

    def synthetic(judgements: list[dict]) -> list[dict]:
        for item in judgements:
            if item["query_id"].startswith("p"):
                item["data_origin"] = "synthetic"
        return judgements

    with pytest.raises(GoldenSetError) as exc:
        load_golden_set(golden_factory(mutate_judgements=synthetic))

    assert exc.value.requirement == "real anchoring"
    assert "piedra" in str(exc.value)


def test_a_set_below_the_floor_is_refused(golden_factory: Callable[..., Path]) -> None:
    """45 judged queries is the floor the exploration fixed before any of them was written."""
    # Enough to cross the floor from whatever the reference set holds. It grew when C25 took
    # the out-of-domain category from five to twenty, so a fixed count of two stopped reaching.
    kept = {f"o{index:02d}" for index in range(20)} | {f"v{index:02d}" for index in range(2)}

    with pytest.raises(GoldenSetError) as exc:
        load_golden_set(
            golden_factory(
                mutate_queries=lambda queries: [
                    item for item in queries if item["id"] not in kept
                ],
                mutate_judgements=lambda judgements: [
                    item for item in judgements if item["query_id"] not in kept
                ],
            )
        )

    assert exc.value.requirement == "floor"


def test_one_pair_judged_twice_is_refused(golden_factory: Callable[..., Path]) -> None:
    """Judgements are keyed by the pair so a later change can append. Two rows make it undefined."""

    def duplicate(judgements: list[dict]) -> list[dict]:
        return [*judgements, dict(judgements[0])]

    with pytest.raises(GoldenSetError, match="judged twice"):
        load_golden_set(golden_factory(mutate_judgements=duplicate))


def test_a_query_declared_unjudged_may_not_carry_judgements(
    golden_factory: Callable[..., Path],
) -> None:
    """The two unmeasurable categories are written and left unlabelled on purpose."""

    def declare(queries: list[dict]) -> list[dict]:
        for item in queries:
            if item["id"] == "u00":
                item["judged"] = False
        return queries

    with pytest.raises(GoldenSetError, match="WITHOUT judgements"):
        load_golden_set(golden_factory(mutate_queries=declare))


def test_the_golden_set_needs_no_database(golden_factory: Callable[..., Path]) -> None:
    """Everything the composition check reads is frozen into the files themselves."""
    import socket

    root = golden_factory()
    original = socket.socket.connect

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("loading the golden set must not open a socket")

    socket.socket.connect = _fail  # type: ignore[method-assign]
    try:
        assert load_golden_set(root).judged_queries
    finally:
        socket.socket.connect = original  # type: ignore[method-assign]


def test_appending_a_judgement_moves_the_version(golden_factory: Callable[..., Path]) -> None:
    """The version is derived from the content, so nobody has to remember to bump it."""
    root = golden_factory()
    before = load_golden_set(root).version

    with (root / "judgements.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            '{"query_id": "u00", "product_id": "99999999-9999-9999-9999-999999999999", '
            '"grade": 1, "pooled_in": [], "judged_at": "2026-09-07", '
            f'"source_hash": "{"0" * 64}", "data_origin": "real", '
            '"lexically_reachable": true}\n'
        )

    after = load_golden_set(root)
    assert after.version != before
    assert after.grade("u00", "99999999-9999-9999-9999-999999999999") == 1
