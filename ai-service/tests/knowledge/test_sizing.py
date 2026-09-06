"""The ring size convention of D16, checked against arithmetic. Delivered by C23.

The table is a **commitment of the establishment** and the section that carries it is
marked as one. That does not make its numbers unfalsifiable: the assignment of letters to
ranges is the house's decision, but `circunferencia = talla + 40` and the diameter derived
from it are ordinary Spanish arithmetic, and a typo in either is a defect whatever the
scope says.
"""

from __future__ import annotations

from jbg_ai.enrichment.vocab import fold, load_vocabularies
from jbg_ai.knowledge.constants import (
    MOTIF_SCALE_WORDS,
    NON_RESIZABLE_MATERIALS,
    NON_RESIZABLE_PHRASE,
    RESIZABLE_MATERIALS,
    TO_ORDER_SIZE_LETTERS,
)
from jbg_ai.knowledge.corpus import KnowledgeCorpus, material_sheet_slug
from jbg_ai.knowledge.sizing import (
    TO_ORDER,
    circumference_for,
    diameter_for,
    resizing_section_text,
    ring_size_table,
    size_letters,
)

RESIZING_POLICY = "politica-reparaciones-y-ajustes"


def test_ring_size_table_is_arithmetically_consistent(corpus: KnowledgeCorpus) -> None:
    rows = ring_size_table(corpus)
    assert len(rows) == 7

    for row in rows:
        assert row.size_max - row.size_min == 2, f"{row.letter}: three whole sizes per letter"
        assert row.circumference_min == circumference_for(row.size_min), row.letter
        assert row.circumference_max == circumference_for(row.size_max), row.letter
        assert abs(row.diameter_min - diameter_for(row.circumference_min)) <= 0.05, row.letter
        assert abs(row.diameter_max - diameter_for(row.circumference_max)) <= 0.05, row.letter

    for previous, following in zip(rows, rows[1:], strict=False):
        assert following.size_min == previous.size_max + 1, (
            f"{previous.letter} -> {following.letter}: contiguous and without overlap"
        )


def test_ring_size_table_covers_the_size_vocabulary(corpus: KnowledgeCorpus) -> None:
    rows = ring_size_table(corpus)
    letters = [row.letter for row in rows]
    assert letters == list(size_letters())

    to_order = {row.letter for row in rows if row.to_order}
    assert to_order == set(TO_ORDER_SIZE_LETTERS)
    for row in rows:
        if row.letter in TO_ORDER_SIZE_LETTERS:
            assert row.availability == TO_ORDER, row.letter


def test_the_table_lives_in_exactly_one_document(corpus: KnowledgeCorpus) -> None:
    """Two copies of one table is an incoherence waiting for someone to fix only one."""
    carrying = [
        document.slug
        for document in corpus
        for section in document.sections
        if "| Letra |" in section.body
    ]
    assert carrying == ["tallas-anillos"]


def test_the_arithmetic_and_the_assignment_carry_different_scopes(
    corpus: KnowledgeCorpus,
) -> None:
    document = corpus.document("tallas-anillos")
    assert document is not None
    arithmetic = document.section("de-la-talla-espanola-a-los-milimetros")
    assignment = document.section("nuestra-escala-de-letras-que-talla-es-cada-una")
    assert arithmetic is not None and assignment is not None
    assert arithmetic.claim_scope == "general"
    assert assignment.claim_scope == "establecimiento"


def test_motif_scale_words_are_never_a_ring_fit_label(corpus: KnowledgeCorpus) -> None:
    """`mini`, `pequeño`, `mediano`, `grande` describe the motif, never a fit."""
    rows = ring_size_table(corpus)
    motif = {fold(word) for word in MOTIF_SCALE_WORDS}
    assert not motif & {fold(row.letter) for row in rows}

    vocabulary_letters = {fold(letter) for letter in size_letters()}
    assert not motif & vocabulary_letters

    # And every one of them is still a term of the size vocabulary, so the exclusion is a
    # decision about meaning rather than a term the vocabulary happens not to have.
    catalogue = {fold(term) for term in load_vocabularies().size_label.canonical}
    assert motif <= catalogue


def test_resizing_limits_agree_across_documents(corpus: KnowledgeCorpus) -> None:
    """The table, the three material sheets and the policy must say the same thing."""
    table = resizing_section_text(corpus).casefold()
    policy_document = corpus.document(RESIZING_POLICY)
    assert policy_document is not None
    policy = policy_document.sections[0].body.casefold()

    for text, where in ((table, "tallas-anillos"), (policy, RESIZING_POLICY)):
        assert NON_RESIZABLE_PHRASE in text, where
        for material in NON_RESIZABLE_MATERIALS:
            assert material.casefold() in text, f"{where} omits {material}"
        for material in RESIZABLE_MATERIALS:
            assert material.casefold() in text, f"{where} omits {material}"
        assert "2 tallas" in text, where

    for material in NON_RESIZABLE_MATERIALS:
        sheet = corpus.document(material_sheet_slug(material))
        assert sheet is not None, material
        body = "\n".join(section.body for section in sheet.sections).casefold()
        assert NON_RESIZABLE_PHRASE in body, (
            f"the sheet of {material} does not state that it cannot be resized"
        )


def test_the_letter_is_documented_as_a_piece_scale_and_not_a_finger_size(
    corpus: KnowledgeCorpus,
) -> None:
    document = corpus.document("tallas-como-se-miden-en-nuestro-catalogo")
    assert document is not None
    first = document.sections[0]
    assert "tamaño de la pieza" in first.title.casefold()
    assert first.claim_scope == "general"
    assert first.source_ref
    # It names the ring document rather than repeating its table.
    joined = "\n".join(section.body for section in document.sections)
    assert "| Letra |" not in joined
