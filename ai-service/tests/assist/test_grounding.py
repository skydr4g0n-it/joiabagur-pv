"""M2's deterministic addressing, over the real corpus. No provider call anywhere.

The invariant under test is the one the design calls a step rather than a slope: only
`claim_scope: general` enters an argument nobody asked for, and `material-bano-de-oro` is
the piece of evidence that makes it concrete.
"""

from __future__ import annotations

from jbg_ai.assist.constants import (
    DEFAULT_MATERIAL_CAP,
    DEFAULT_PITCH_SECTIONS,
    MIXED_PIECE_DOCUMENT,
    MIXED_PIECE_SECTION,
)
from jbg_ai.assist.grounding import ground_piece, pitch_addresses
from jbg_ai.assist.knowledge_scope import canonical_material_sheets
from jbg_ai.knowledge.constants import CLAIM_SCOPE_ESTABLISHMENT, CLAIM_SCOPE_GENERAL
from jbg_ai.knowledge.corpus import KnowledgeCorpus
from jbg_ai.knowledge.offline import InMemoryKnowledgeIndex, LocalEmbeddingClient
from support.assist_world import run


# --- the allow-list is an authored fact, and it is checked against the corpus -------------


def test_the_allow_listed_sections_exist_and_are_general_in_all_nine_sheets(
    corpus: KnowledgeCorpus,
) -> None:
    """The measurement the whole mode rests on, asserted rather than quoted."""
    for slug in canonical_material_sheets():
        document = corpus.document(slug)
        assert document is not None, slug
        for section_slug in DEFAULT_PITCH_SECTIONS:
            section = document.section(section_slug)
            assert section is not None, f"{slug}#{section_slug}"
            assert section.claim_scope == CLAIM_SCOPE_GENERAL, f"{slug}#{section_slug}"


def test_the_gold_plating_sheet_really_does_carry_an_establishment_section(
    corpus: KnowledgeCorpus,
) -> None:
    """Without this row the `general`-only invariant would be a rule guarding nothing."""
    document = corpus.document("material-bano-de-oro")

    assert document is not None
    commitments = [
        section
        for section in document.sections
        if section.claim_scope == CLAIM_SCOPE_ESTABLISHMENT
    ]
    assert commitments, "the sheet must carry the commitment this invariant excludes"
    assert all(section.slug not in DEFAULT_PITCH_SECTIONS for section in commitments)


def test_the_mixed_piece_section_exists_and_is_general(corpus: KnowledgeCorpus) -> None:
    document = corpus.document(MIXED_PIECE_DOCUMENT)

    assert document is not None
    section = document.section(MIXED_PIECE_SECTION)
    assert section is not None
    assert section.claim_scope == CLAIM_SCOPE_GENERAL


# --- addressing ---------------------------------------------------------------------------


def test_one_material_addresses_only_its_own_sheet() -> None:
    addresses = pitch_addresses(["plata"])

    assert addresses == (
        ("material-plata", "cuidados-y-limpieza-en-casa"),
        ("material-plata", "piel-sensible-y-alergias"),
    )


def test_two_materials_add_the_mixed_piece_section() -> None:
    addresses = pitch_addresses(["plata", "baño de oro"])

    assert (MIXED_PIECE_DOCUMENT, MIXED_PIECE_SECTION) in addresses
    assert ("material-plata", "cuidados-y-limpieza-en-casa") in addresses
    assert ("material-bano-de-oro", "cuidados-y-limpieza-en-casa") in addresses


def test_a_single_material_never_gets_the_mixed_piece_section() -> None:
    assert all(
        document != MIXED_PIECE_DOCUMENT for document, _ in pitch_addresses(["plata"])
    )


def test_the_material_cap_is_honoured_and_travels_by_parameter() -> None:
    three = ["plata", "baño de oro", "perla"]

    capped = pitch_addresses(three)
    widened = pitch_addresses(three, material_cap=3)

    assert DEFAULT_MATERIAL_CAP == 2
    assert not any(document == "material-perla" for document, _ in capped)
    assert any(document == "material-perla" for document, _ in widened)


def test_a_piece_over_the_cap_still_gets_the_mixed_piece_guidance() -> None:
    """The cap limits sheets, not the warning that one part governs the other."""
    addresses = pitch_addresses(["plata", "baño de oro", "perla"])

    assert (MIXED_PIECE_DOCUMENT, MIXED_PIECE_SECTION) in addresses


def test_the_section_list_travels_by_parameter() -> None:
    addresses = pitch_addresses(["plata"], sections=("cuidados-y-limpieza-en-casa",))

    assert addresses == (("material-plata", "cuidados-y-limpieza-en-casa"),)


def test_a_material_the_vocabulary_cannot_resolve_addresses_nothing() -> None:
    assert pitch_addresses(["titanio"]) == ()


def test_a_synonym_addresses_the_canonical_sheet() -> None:
    assert pitch_addresses(["925"]) == pitch_addresses(["plata"])


def test_a_repeated_material_is_addressed_once() -> None:
    assert pitch_addresses(["plata", "plata"]) == pitch_addresses(["plata"])


# --- the fragments that come back ----------------------------------------------------------


def test_the_citations_come_from_the_declared_material_sheet(
    knowledge: InMemoryKnowledgeIndex,
) -> None:
    citations = run(ground_piece(["plata"], index=knowledge))

    assert citations
    assert {item.document_slug for item in citations} == {"material-plata"}
    assert {item.section_slug for item in citations} == set(DEFAULT_PITCH_SECTIONS)


def test_no_sheet_of_an_undeclared_material_is_cited(
    knowledge: InMemoryKnowledgeIndex,
) -> None:
    citations = run(ground_piece(["plata"], index=knowledge))
    foreign = set(canonical_material_sheets()) - {"material-plata"}

    assert all(item.document_slug not in foreign for item in citations)


def test_no_commitment_of_the_establishment_enters_an_unrequested_argument(
    knowledge: InMemoryKnowledgeIndex,
) -> None:
    """Gold plating is the piece that would carry one, so it is the piece that is asked."""
    citations = run(ground_piece(["baño de oro"], index=knowledge))

    assert citations
    assert all(item.claim_scope == CLAIM_SCOPE_GENERAL for item in citations)


def test_the_scope_filter_holds_even_if_the_allow_list_were_widened(
    knowledge: InMemoryKnowledgeIndex,
) -> None:
    """The invariant must not depend on the allow-list staying correct.

    Handed the commitment section by name, the layer still refuses it — which is what makes
    "only general" a property of the code rather than of a tuple somebody could edit.
    """
    citations = run(
        ground_piece(
            ["baño de oro"],
            index=knowledge,
            sections=("nuestra-garantia-sobre-el-bano",),
        )
    )

    assert citations == ()


def test_a_citation_carries_every_field_a_searched_one_carries(
    knowledge: InMemoryKnowledgeIndex,
) -> None:
    """A consumer must not be able to tell which path produced a fragment."""
    citation = run(ground_piece(["plata"], index=knowledge))[0]

    assert citation.citation_id == f"{citation.document_slug}#{citation.section_slug}"
    assert citation.document_title
    assert citation.section_title
    assert citation.doc_type == "material"
    assert citation.claim_scope == CLAIM_SCOPE_GENERAL
    assert 0.0 <= citation.score <= 1.0
    assert citation.content


def test_an_absent_section_yields_nothing_and_does_not_fail_the_call(
    knowledge: InMemoryKnowledgeIndex,
) -> None:
    """`material-acero` has four sections; the other sheets have six or seven."""
    citations = run(
        ground_piece(
            ["acero"],
            index=knowledge,
            sections=("cuidados-y-limpieza-en-casa", "como-guardarlo"),
        )
    )

    assert [item.section_slug for item in citations] == ["cuidados-y-limpieza-en-casa"]


def test_grounding_makes_no_provider_call_at_all(
    knowledge: InMemoryKnowledgeIndex,
) -> None:
    """The mode that cites without being asked must not touch a vector."""
    embed = LocalEmbeddingClient()

    citations = run(ground_piece(["plata", "baño de oro"], index=knowledge))

    assert citations
    assert embed.calls == []


def test_a_piece_with_no_material_is_grounded_by_nothing(
    knowledge: InMemoryKnowledgeIndex,
) -> None:
    assert run(ground_piece([], index=knowledge)) == ()
