"""The seven authoring rules, and the coverage invariant. Delivered by C23.

Every one of these asserts a property of the **committed corpus**, not of a hand-made
fixture, wherever the rule is about the corpus. A rule tested only against a synthetic
document proves the parser works and says nothing about the 32 files that will actually be
indexed — which is the pair the citation has to be true about.
"""

from __future__ import annotations

import pytest

from jbg_ai.enrichment.vocab import load_vocabularies
from jbg_ai.knowledge.constants import (
    ALLOWED_DOC_TYPES,
    CLAIM_SCOPES,
    FORBIDDEN_DOC_TYPE,
    MAX_SECTION_CHARS,
)
from jbg_ai.knowledge.corpus import (
    KnowledgeCorpus,
    forbidden_content_reason,
    material_sheet_slug,
    missing_material_sheets,
    parse_document,
)
from jbg_ai.knowledge.errors import KnowledgeCorpusError, KnowledgeCoverageError

VALID = """# Plata

<!-- doc_type: material -->
<!-- eval_question: ¿Por qué se pone negra la plata? -->

## Qué es y cómo se reconoce

<!-- claim_scope: general -->

La plata de ley es una aleación de 925 milésimas.

## Nuestra garantía

<!-- claim_scope: establecimiento -->

La casa responde del acabado durante un plazo.
"""


def document(text: str = VALID, *, slug: str = "material-plata"):
    return parse_document(text, slug=slug)


def test_a_well_formed_document_parses() -> None:
    parsed = document()
    assert parsed.doc_type == "material"
    assert parsed.eval_question.startswith("¿Por qué")
    assert [section.slug for section in parsed.sections] == [
        "que-es-y-como-se-reconoce",
        "nuestra-garantia",
    ]


def test_section_over_the_size_limit_fails_ingestion() -> None:
    oversized = VALID.replace(
        "La plata de ley es una aleación de 925 milésimas.",
        "palabra " * (MAX_SECTION_CHARS // 4),
    )
    with pytest.raises(KnowledgeCorpusError) as error:
        document(oversized)
    message = str(error.value)
    assert "material-plata" in message
    assert "que-es-y-como-se-reconoce" in message
    assert str(MAX_SECTION_CHARS) in message


def test_an_oversized_section_is_not_split_automatically() -> None:
    """The failure is the point: an automatic split makes a fragment with no heading."""
    oversized = VALID.replace(
        "La plata de ley es una aleación de 925 milésimas.",
        "palabra " * (MAX_SECTION_CHARS // 4),
    )
    with pytest.raises(KnowledgeCorpusError):
        document(oversized)


def test_document_with_text_before_first_section_is_rejected() -> None:
    with pytest.raises(KnowledgeCorpusError) as error:
        document(VALID.replace("<!-- doc_type: material -->", "Una introducción suelta."))
    assert "texto entre el título y la primera sección" in str(error.value)


def test_section_without_claim_scope_is_rejected() -> None:
    with pytest.raises(KnowledgeCorpusError) as error:
        document(VALID.replace("<!-- claim_scope: general -->\n\n", ""))
    assert "claim_scope" in str(error.value)
    assert "que-es-y-como-se-reconoce" in str(error.value)


def test_an_unknown_claim_scope_is_rejected() -> None:
    with pytest.raises(KnowledgeCorpusError):
        document(VALID.replace("claim_scope: general", "claim_scope: catalogo"))


def test_a_sales_script_document_is_rejected_by_name() -> None:
    with pytest.raises(KnowledgeCorpusError) as error:
        document(VALID.replace("doc_type: material", f"doc_type: {FORBIDDEN_DOC_TYPE}"))
    assert "indistinguible de una instrucción" in str(error.value)


def test_a_document_without_an_eval_question_is_rejected() -> None:
    with pytest.raises(KnowledgeCorpusError) as error:
        document(VALID.replace("<!-- eval_question: ¿Por qué se pone negra la plata? -->\n", ""))
    assert "eval_question" in str(error.value)


@pytest.mark.parametrize(
    "offending",
    [
        "La referencia SKU01 se limpia con un paño.",
        "Cuesta 48 euros y se limpia con un paño.",
        "Se vende por 48 € en el mostrador.",
        "El precio de 48 no incluye el estuche.",
        "La ref. 4432 lleva baño de oro.",
    ],
)
def test_a_section_naming_a_product_or_a_price_is_rejected(offending: str) -> None:
    with pytest.raises(KnowledgeCorpusError) as error:
        document(VALID.replace("La plata de ley es una aleación de 925 milésimas.", offending))
    assert "que-es-y-como-se-reconoce" in str(error.value)


@pytest.mark.parametrize(
    "offending",
    [
        "La plata suma 634 productos del surtido.",
        "Sobre los 1.168 productos del índice, la plata encabeza.",
        "Algo más de un doce por ciento de las piezas mezcla dos materiales.",
        "Los pendientes son el 24,4 % del surtido.",
        "De las veintiocho colecciones, muchas llevan topónimo.",
        "Sobre mil doscientos productos medidos, la plata domina.",
        "El surtido creció un 12 % este año.",
    ],
)
def test_a_section_counting_the_catalogue_is_rejected(offending: str) -> None:
    """The half of rule 5 that is easy to get wrong, because a figure reads like rigour.

    A count of the assortment stops being true the day a product is added or withdrawn, and
    the citation keeps resolving and keeps locating — so the corpus would carry a falsehood
    with a verified stamp, which is the exact failure this change is built around.
    """
    with pytest.raises(KnowledgeCorpusError) as error:
        document(VALID.replace("La plata de ley es una aleación de 925 milésimas.", offending))
    assert "que-es-y-como-se-reconoce" in str(error.value)
    assert "catálogo" in str(error.value)


@pytest.mark.parametrize(
    "innocent",
    [
        "El ópalo lleva agua en su estructura, entre un tres y un diez por ciento.",
        "La plata de ley es una aleación de 925 milésimas de plata y 75 de cobre.",
        "Un aro liso admite un ajuste de hasta 2 tallas arriba o abajo.",
        "La circunferencia interior va de 44 a 46 mm.",
        "Dos piezas de oro que comparten cajón se rayan mutuamente.",
        "Veinte años de mostrador enseñan a mirar el cierre primero.",
    ],
)
def test_a_figure_that_is_not_about_the_catalogue_is_allowed(innocent: str) -> None:
    """The rule reads the neighbourhood, not the symbol.

    Not every proportion in a jewellery corpus is a statistic about the shop: an opal
    carries three to ten per cent water by structure, and that sentence will read the same
    in twenty years. Banning percentages on sight would have deleted the mineralogy.
    """
    parsed = document(
        VALID.replace("La plata de ley es una aleación de 925 milésimas.", innocent)
    )
    assert parsed.sections[0].body == innocent


def test_a_deeper_heading_is_rejected() -> None:
    with pytest.raises(KnowledgeCorpusError):
        document(VALID + "\n### Un subapartado\n\nTexto.\n")


def test_a_marker_placed_after_the_body_is_rejected() -> None:
    with pytest.raises(KnowledgeCorpusError) as error:
        document(
            VALID.replace(
                "La plata de ley es una aleación de 925 milésimas.",
                "La plata de ley es una aleación.\n\n<!-- source_ref: tarde -->",
            )
        )
    assert "justo bajo el encabezado" in str(error.value)


# --- properties of the committed corpus ------------------------------------------------


def test_corpus_contains_no_sales_script_document(corpus: KnowledgeCorpus) -> None:
    assert FORBIDDEN_DOC_TYPE not in {document.doc_type for document in corpus}
    assert {document.doc_type for document in corpus} <= ALLOWED_DOC_TYPES


def test_corpus_contains_no_sku_product_or_price(corpus: KnowledgeCorpus) -> None:
    """Load already enforces it; asserting it again states it as a property of the corpus."""
    for item in corpus:
        for section in item.sections:
            assert "€" not in section.body
            assert "SKU" not in section.body.upper()


def test_corpus_does_not_depend_on_the_current_contents_of_the_catalogue(
    corpus: KnowledgeCorpus,
) -> None:
    """No section may go stale because one product was added or withdrawn.

    The measured evidence decides which documents exist and how deep each one goes; it
    lives in the block prompts and in the report. What the citable text carries is the
    durable shape of the fact.
    """
    for item in corpus:
        for section in item.sections:
            reason = forbidden_content_reason(f"{section.title}\n{section.body}")
            assert reason is None, f"{item.slug}#{section.slug}: {reason}"


def test_every_section_declares_a_claim_scope(corpus: KnowledgeCorpus) -> None:
    for item in corpus:
        for section in item.sections:
            assert section.claim_scope in CLAIM_SCOPES


def test_no_document_carries_a_single_scope_of_its_own(corpus: KnowledgeCorpus) -> None:
    """Scope is per section because a document carries claims of both kinds."""
    assert not hasattr(corpus.documents[0], "claim_scope")
    mixed = [
        item
        for item in corpus
        if len({section.claim_scope for section in item.sections}) > 1
    ]
    assert mixed, "at least one document must carry sections of both kinds"


def test_the_service_block_is_entirely_a_commitment_of_the_establishment(
    corpus: KnowledgeCorpus,
) -> None:
    """The block that demonstrates the marking mechanism from the first document."""
    scopes = {
        section.claim_scope
        for item in corpus
        if item.doc_type == "politica"
        for section in item.sections
    }
    assert scopes == {"establecimiento"}


def test_every_canonical_material_has_exactly_one_sheet(corpus: KnowledgeCorpus) -> None:
    vocabularies = load_vocabularies()
    assert missing_material_sheets(corpus, vocabularies) == ()
    for canonical in vocabularies.materials.canonical:
        slug = material_sheet_slug(canonical)
        matching = [item for item in corpus if item.slug == slug]
        assert len(matching) == 1, canonical
        assert matching[0].doc_type == "material"


def test_a_new_vocabulary_term_without_its_sheet_is_a_failure(corpus: KnowledgeCorpus) -> None:
    """Coverage is derived from the vocabulary, so extending one and not the other fails."""
    vocabularies = load_vocabularies()
    widened = vocabularies.materials.__class__(
        name="materials",
        canonical=(*vocabularies.materials.canonical, "titanio"),
        synonyms=dict(vocabularies.materials.synonyms),
    )
    extended = vocabularies.__class__(
        piece_type=vocabularies.piece_type,
        materials=widened,
        stone_type=vocabularies.stone_type,
        size_label=vocabularies.size_label,
        color_tags=vocabularies.color_tags,
        style_tags=vocabularies.style_tags,
        occasion_tags=vocabularies.occasion_tags,
    )
    assert missing_material_sheets(corpus, extended) == ("titanio",)

    from jbg_ai.knowledge.corpus import require_material_coverage

    with pytest.raises(KnowledgeCoverageError) as error:
        require_material_coverage(corpus, extended)
    assert "titanio" in str(error.value)


def test_material_sheet_is_not_product_scoped(corpus: KnowledgeCorpus) -> None:
    """A sheet describes a material, never a piece: no identifier, no price, no article."""
    for canonical in load_vocabularies().materials.canonical:
        sheet = corpus.document(material_sheet_slug(canonical))
        assert sheet is not None
        for section in sheet.sections:
            body = section.body
            assert "€" not in body
            assert "SKU" not in body.upper()
            assert "referencia " not in body.casefold()


def test_the_corpus_declares_the_composition_the_report_publishes(
    corpus: KnowledgeCorpus,
) -> None:
    assert len(corpus) == 32
    assert corpus.section_count == 161
    assert corpus.counts_by_doc_type() == {
        "faq": 10,
        "material": 14,
        "politica": 4,
        "talla": 4,
    }
    assert corpus.counts_by_claim_scope() == {"establecimiento": 25, "general": 136}
