"""Closed vocabularies and synonym normalisation. Delivered by C09."""

from __future__ import annotations

from jbg_ai.enrichment.vocab import load_vocabularies, normalize_value


def test_vocabularies_load_from_versioned_file() -> None:
    vocabs = load_vocabularies()

    assert "anillo" in vocabs.piece_type.as_set
    assert "hilo" in vocabs.materials.as_set
    assert "piedra" in vocabs.stone_type.as_set
    assert "S" in vocabs.size_label.as_set
    assert "mini" in vocabs.size_label.as_set
    assert vocabs.color_tags.canonical
    assert vocabs.style_tags.canonical
    assert vocabs.occasion_tags.canonical


def test_rejects_value_outside_closed_vocabulary() -> None:
    vocabs = load_vocabularies()

    assert normalize_value("mithril", vocabs.materials) is None
    assert "mithril" not in vocabs.materials.as_set
    assert normalize_value("diamante", vocabs.materials) is None


def test_material_synonym_normalized_to_canonical_term() -> None:
    vocabs = load_vocabularies()

    assert normalize_value("plata de ley", vocabs.materials) == "plata"
    assert normalize_value("925", vocabs.materials) == "plata"
    assert normalize_value("sterling", vocabs.materials) == "plata"
    assert normalize_value("18k", vocabs.materials) == "oro"
    assert normalize_value("18kl", vocabs.materials) == "oro"
    assert normalize_value("hilo encerado", vocabs.materials) == "hilo"
    assert normalize_value("ámbar", vocabs.stone_type) == "ambar"
    assert normalize_value("amber", vocabs.stone_type) == "ambar"


def test_piece_type_stores_hypernym_not_hyponym() -> None:
    vocabs = load_vocabularies()

    assert normalize_value("sortija", vocabs.piece_type) == "anillo"
    assert normalize_value("alianza", vocabs.piece_type) == "anillo"
    assert normalize_value("gargantilla", vocabs.piece_type) == "collar"
    assert normalize_value("brazalete", vocabs.piece_type) == "pulsera"
    assert normalize_value("esclava", vocabs.piece_type) == "pulsera"
    assert normalize_value("criollas", vocabs.piece_type) == "pendientes"
    assert normalize_value("aro", vocabs.piece_type) == "pendientes"
    assert normalize_value("colgante", vocabs.piece_type) == "colgante"
    assert "gargantilla" not in vocabs.piece_type.as_set
    assert "brazalete" not in vocabs.style_tags.as_set
    assert "gargantilla" not in vocabs.style_tags.as_set


def test_new_piece_types_are_canonical_and_normalised() -> None:
    """The four terms FIX1 added are canonicals, not synonyms of an older hypernym.

    `gemelos` is canonical in the plural, as `pendientes` is, because the piece is a
    pair. `cinturon` is canonical without its accent, as `pequeno` is: the value is
    compared by exact equality when it travels from the panel to the retriever, so the
    accent lives only in the human-readable label.
    """
    vocabs = load_vocabularies()

    for term in ("diadema", "gemelos", "cinturon", "llavero"):
        assert term in vocabs.piece_type.as_set
        assert normalize_value(term, vocabs.piece_type) == term

    assert normalize_value("Diadema", vocabs.piece_type) == "diadema"
    assert normalize_value("Cinturón", vocabs.piece_type) == "cinturon"
    assert normalize_value("cinturón", vocabs.piece_type) == "cinturon"
    assert normalize_value("LLAVERO", vocabs.piece_type) == "llavero"

    # No extraction synonym was added for them: the query-side variants belong to the
    # C20 overlay, which derives its classes from this same file.
    assert normalize_value("tiara", vocabs.piece_type) is None
    assert normalize_value("gemelo", vocabs.piece_type) is None
