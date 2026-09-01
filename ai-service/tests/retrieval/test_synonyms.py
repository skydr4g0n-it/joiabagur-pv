"""Query-side synonym dictionary and expansion. Delivered by C20.

Every assertion here is offline: the expansion is a pure function and the dictionary
reads only its own packaged YAML.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jbg_ai.enrichment.vocab import load_vocabularies
from jbg_ai.retrieval.synonyms import (
    OVERLAY_RESOURCE,
    SynonymDictionaryError,
    build_dictionary,
    expand_query,
    load_overlay_from_path,
    load_query_dictionary,
    singular_candidates,
)

OVERLAY_PATH = Path(__file__).resolve().parents[2] / "src" / "jbg_ai" / "retrieval" / OVERLAY_RESOURCE


def _forms(query: str, position: int = 0) -> list[str]:
    return list(expand_query(query, enabled=True).groups[position])


def _folded(values: list[str]) -> set[str]:
    from jbg_ai.enrichment.vocab import fold

    return {fold(value) for value in values}


# --------------------------------------------------------------------- layering


def test_base_class_is_reachable_without_the_overlay_restating_it() -> None:
    """`gargantilla` -> `collar` lives in the enrichment vocabulary; the overlay is silent."""
    overlay = load_overlay_from_path(OVERLAY_PATH)
    restated = {
        str(form).casefold()
        for entry in overlay.get("classes") or ()
        for form in entry.get("forms") or ()
    }
    assert "gargantilla" not in restated

    forms = _forms("gargantilla")
    assert "gargantilla" in forms
    assert "collar" in forms


def test_overlay_never_overrides_a_base_canonical() -> None:
    """The overlay may add surface forms; reassigning a base term must fail loudly."""
    overlay = {
        "classes": [
            {"field": "piece_type", "canonical": "collar", "forms": ["sortija"]},
        ]
    }
    with pytest.raises(SynonymDictionaryError) as exc_info:
        build_dictionary(load_vocabularies(), overlay)

    message = str(exc_info.value)
    assert "sortija" in message
    assert "anillo" in message


def test_overlay_anchor_absent_from_the_base_is_a_vocabulary_gap() -> None:
    """A piece type the base does not know is not a synonym and must not enter here."""
    overlay = {
        "classes": [
            {"field": "piece_type", "canonical": "diadema", "forms": ["tiara"]},
        ]
    }
    with pytest.raises(SynonymDictionaryError) as exc_info:
        build_dictionary(load_vocabularies(), overlay)

    message = str(exc_info.value)
    assert "diadema" in message
    assert "fix-enrichment-vocabulary-gaps" in message


def test_shipped_overlay_anchors_all_exist_in_the_base_vocabulary() -> None:
    """Fixation: if C09 ever drops a canonical the overlay anchors, this fails first."""
    load_query_dictionary.cache_clear()
    dictionary = load_query_dictionary()
    overlay = load_overlay_from_path(OVERLAY_PATH)

    anchors = [(e["field"], e["canonical"]) for e in overlay.get("classes") or ()]
    anchors += [
        (a["field"], a["canonical"])
        for bridge in overlay.get("bridges") or ()
        for side in ("widens", "with")
        for a in bridge.get(side) or ()
    ]
    assert anchors, "the shipped overlay declares no anchors"
    for anchor in anchors:
        assert dictionary.forms_for(anchor), f"{anchor} is not a class of the base vocabulary"


def test_base_vocabulary_terms_are_pinned() -> None:
    """Mirror of `frontend/src/lib/materials-vocabulary.test.ts`.

    This change must not move the extraction vocabulary. When
    `fix-enrichment-vocabulary-gaps` adds `diadema`, `gemelos`, `cinturon` and
    `llavero`, that change updates this list deliberately — which is the point.
    """
    vocabs = load_vocabularies()
    assert vocabs.piece_type.canonical == (
        "anillo",
        "pendientes",
        "collar",
        "pulsera",
        "colgante",
        "tobillera",
        "broche",
        "cadena",
    )
    assert vocabs.materials.canonical == (
        "plata",
        "oro",
        "baño de oro",
        "hilo",
        "latón",
        "acero",
        "resina",
        "cuero",
        "perla",
    )


# ------------------------------------------------------------------- expansion


def test_query_with_synonym_matches_canonical_term() -> None:
    result = expand_query("sortija de plata", enabled=True)

    assert result.original == "sortija de plata"
    assert "sortija" in result.groups[0]
    assert "anillo" in result.groups[0]
    assert result.groups[0][0] == "sortija", "the operator's own form leads the group"

    resolved = {(m.term, m.field, m.canonical) for m in result.matched}
    assert ("sortija", "piece_type", "anillo") in resolved


def test_expansion_returns_groups_not_a_rewritten_string() -> None:
    result = expand_query("gargantilla dorada", enabled=True)

    assert isinstance(result.groups, tuple)
    assert all(isinstance(group, tuple) for group in result.groups)
    for group in result.groups:
        for form in group:
            assert not set(form) & set("|&!():*"), "no tsquery syntax leaves this module"


def test_longest_phrase_wins_over_shorter_token() -> None:
    """`aro` is earrings and `aro de dedo` is a ring; only phrase length separates them."""
    ring = _forms("aro de dedo de plata")
    assert "anillo" in ring
    assert "pendientes" not in ring

    earrings = _forms("aro de plata")
    assert "pendientes" in earrings
    assert "anillo" not in earrings


def test_unknown_term_passes_through_unchanged() -> None:
    result = expand_query("anillo Ses Salines", enabled=True)

    assert result.groups[1] == ("Ses",)
    assert result.groups[2] == ("Salines",)
    assert "anillo" in result.groups[0]
    assert all(m.term != "Ses" for m in result.matched)


def test_disabled_flag_returns_original_query() -> None:
    result = expand_query("sortija de plata", enabled=False)

    assert result.original == "sortija de plata"
    assert result.groups == (("sortija",), ("de",), ("plata",))
    assert result.matched == ()


def test_expansion_makes_no_database_or_provider_call(forbid_network: None) -> None:
    """The whole capability is arithmetic over dictionaries; a socket here is a bug."""
    result = expand_query("collares de plata dorada", enabled=True)
    assert result.groups


# --------------------------------------------------- stemmer artefacts, plurals


def test_plural_is_resolved_without_a_dedicated_entry() -> None:
    """Singularisation on both sides removes ten one-per-inflection overlay entries."""
    overlay = load_overlay_from_path(OVERLAY_PATH)
    declared = _folded(
        [str(form) for entry in overlay.get("classes") or () for form in entry.get("forms") or ()]
    )

    for typed, canonical in (
        ("sortijas", "anillo"),
        ("alianzas", "anillo"),
        ("gargantillas", "collar"),
        ("brazaletes", "pulsera"),
        ("esclavas", "pulsera"),
    ):
        assert typed not in declared, f"{typed} should not need its own overlay entry"
        assert canonical in _forms(typed), f"{typed} did not reach {canonical}"


def test_singularisation_never_invents_a_canonical() -> None:
    """A reduction is only used when the reduced form is already in the dictionary."""
    assert singular_candidates("collares") == ("collar", "collare")
    result = expand_query("mesas", enabled=True)
    assert result.groups == (("mesas",),)
    assert result.matched == ()


def test_stemmer_split_terms_are_expanded() -> None:
    """`collar` and `collares` stem to different lexemes: 140 documents against 1."""
    group = _forms("collares de plata")
    assert "collares" in group
    assert "collar" in group


def test_unaccented_query_reaches_accented_surface_form() -> None:
    """The stemmer folds acute accents but not the enye: 'ban' never meets 'bañ'."""
    group = _forms("bano de oro")
    assert "baño de oro" in group, "the accented surface form must survive deduplication"


def test_both_size_forms_are_emitted() -> None:
    """134 documents use `pequeño` in prose and 71 use `pequeno` in the size line."""
    for typed in ("pequeno", "pequeño"):
        group = _forms(typed)
        assert "pequeno" in group
        assert "pequeño" in group


def test_feminine_form_reaches_the_gold_bridge() -> None:
    """`dorada` is half of `gargantilla dorada`, the query that reaches zero unexpanded."""
    group = _forms("gargantilla dorada", position=1)
    assert "dorada" in group
    assert "baño de oro" in group
    assert "oro" in group


# ------------------------------------------------------------------- exclusions


def test_excluded_false_friend_is_absent() -> None:
    """All 7 documents matching `piel` say "sobre la piel"; `cuero` has one product."""
    dictionary = load_query_dictionary()
    leather = dictionary.forms_for(("materials", "cuero"))
    assert "piel" not in {form.casefold() for form in leather}

    result = expand_query("piel", enabled=True)
    assert result.groups == (("piel",),)
    assert result.matched == ()


def test_vocabulary_gaps_are_recorded_as_exclusions_not_smuggled_in() -> None:
    overlay = load_overlay_from_path(OVERLAY_PATH)
    excluded = {str(item["term"]).casefold() for item in overlay.get("exclusions") or ()}
    assert {"piel", "llavero", "diadema", "gemelos", "cinturon", "filigrana"} <= excluded
    for item in overlay.get("exclusions") or ():
        assert str(item.get("why") or "").strip(), f"exclusion {item['term']} has no reason"


def test_every_overlay_entry_carries_its_reason() -> None:
    overlay = load_overlay_from_path(OVERLAY_PATH)
    for entry in overlay.get("classes") or ():
        assert str(entry.get("why") or "").strip(), f"{entry['canonical']} has no reason"
    for bridge in overlay.get("bridges") or ():
        assert str(bridge.get("why") or "").strip(), "a bridge has no reason"


def test_gold_bridge_is_directional() -> None:
    """The colour reaches solid gold; the plating must not.

    A symmetric union was measured and rejected: it made a query for `baño de oro` —
    the plating, 420 EUR on average — also match the 282 solid-gold pieces averaging
    587 EUR, the opposite of what an operator asking for the cheaper finish wants.
    """
    colour = _forms("dorado")
    assert "baño de oro" in colour
    assert "oro" in colour, "a gold-coloured piece is gold-coloured either way"

    plating = _forms("baño de oro")
    assert "dorado" in plating, "the corpus writes the colour word far more often"
    assert "oro" not in plating, "the plating must not drag solid gold in"

    assert _forms("oro") == ["oro"], "the material is not widened by anything"


def test_bridge_direction_does_not_leak_transitively() -> None:
    """Donations come from a snapshot: `baño de oro -> dorado` must not inherit `oro`."""
    assert "oro" not in _forms("banado en oro")
    assert "oro" not in _forms("bano de oro")
