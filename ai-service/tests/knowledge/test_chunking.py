"""Chunking, traceability and the stability of a citation. Delivered by C23."""

from __future__ import annotations

import re

from jbg_ai.knowledge.chunking import chunk_corpus, chunk_document, citation_id
from jbg_ai.knowledge.constants import CORPUS_DIR
from jbg_ai.knowledge.corpus import KnowledgeCorpus, parse_document
from jbg_ai.knowledge.indexer import chunk_id, document_id

THREE_SECTIONS = """# Tallas de anillo

<!-- doc_type: talla -->
<!-- eval_question: ¿Cómo mido mi talla de anillo? -->

## Cómo medir tu talla en casa

<!-- claim_scope: general -->

Con un hilo alrededor del dedo y una regla.

## De la talla española a los milímetros

<!-- claim_scope: general -->

La circunferencia es la talla más cuarenta.

## Qué aro se puede ajustar

<!-- claim_scope: general -->

Un aro liso admite dos tallas arriba o abajo.
"""

INSERTED = THREE_SECTIONS.replace(
    "## De la talla española a los milímetros",
    "## Medir a partir de un anillo que ya tienes\n\n"
    "<!-- claim_scope: general -->\n\n"
    "Se mide el diámetro interior con una regla.\n\n"
    "## De la talla española a los milímetros",
)


def test_chunker_preserves_section_titles_in_metadata(corpus: KnowledgeCorpus) -> None:
    for document in corpus:
        for chunk in chunk_document(document):
            metadata = chunk.metadata()
            assert metadata["document_title"] == document.title
            assert metadata["section_title"]
            assert chunk.content.startswith(
                f"# {document.title}\n## {metadata['section_title']}\n\n"
            )


def test_the_indexed_content_carries_both_titles(chunks) -> None:
    """`tsv` is generated over `content`, so a title inside it reaches both indexes."""
    for chunk in chunks:
        lines = chunk.content.splitlines()
        assert lines[0].startswith("# ")
        assert lines[1].startswith("## ")


def test_metadata_markers_do_not_reach_the_index(chunks) -> None:
    for chunk in chunks:
        assert "claim_scope" not in chunk.content
        assert "<!--" not in chunk.content
        assert "eval_question" not in chunk.content


def test_chunks_do_not_overlap(corpus: KnowledgeCorpus) -> None:
    """One section, one chunk: the bodies partition the document, they do not share text."""
    for document in corpus:
        produced = chunk_document(document)
        assert len(produced) == len(document.sections)
        for chunk, section in zip(produced, document.sections, strict=True):
            assert chunk.content.endswith(section.body)
        for index, chunk in enumerate(produced):
            for other in produced[index + 1 :]:
                assert chunk.section_slug != other.section_slug


def test_every_chunk_has_traceable_document_id(chunks) -> None:
    for chunk in chunks:
        metadata = chunk.metadata()
        assert metadata["document_slug"] == chunk.document_slug
        assert metadata["citation_id"] == citation_id(
            chunk.document_slug, chunk.section_slug
        )
        assert document_id(chunk.document_slug) == document_id(metadata["document_slug"])


def test_citation_id_resolves_to_a_file_and_a_heading_in_the_corpus(chunks) -> None:
    """The strongest form of verifiability available: the citation opens the source."""
    for chunk in chunks:
        document_slug, section_title = chunk.citation_id.split("#", 1)
        path = CORPUS_DIR / f"{document_slug}.md"
        assert path.is_file(), chunk.citation_id
        text = path.read_text(encoding="utf-8")
        heading = re.escape(f"## {chunk.section_title}")
        assert re.search(rf"^{heading}\s*$", text, flags=re.MULTILINE), chunk.citation_id
        assert section_title == chunk.section_slug


def test_a_citation_naming_a_heading_that_no_longer_exists_is_detected(
    corpus: KnowledgeCorpus,
) -> None:
    document = corpus.documents[0]
    stale = citation_id(document.slug, "una-seccion-que-no-existe")
    slug, section = stale.split("#", 1)
    text = (CORPUS_DIR / f"{slug}.md").read_text(encoding="utf-8")
    assert section not in {item.slug for item in document.sections}
    assert f"## {section}" not in text


def test_chunk_identity_is_stable_across_reindexing(corpus: KnowledgeCorpus) -> None:
    first = {chunk.citation_id: chunk_id(chunk.document_slug, chunk.section_slug)
             for chunk in chunk_corpus(corpus)}
    second = {chunk.citation_id: chunk_id(chunk.document_slug, chunk.section_slug)
              for chunk in chunk_corpus(corpus)}
    assert first == second
    # Pinned by value, not only by self-consistency: `uuid5` over a fixed namespace must
    # give the same identifier on any machine and in any process, for ever.
    assert str(chunk_id("material-plata", "cuidados-y-limpieza-en-casa")) == (
        "dfd0d813-aeb5-5097-afdd-f1cb5294b340"
    )
    assert str(document_id("material-plata")) == "b758ad22-9b99-52cd-bef7-a4bd049edada"


def test_inserting_a_section_does_not_repoint_existing_citations() -> None:
    """The reason identity is not `(document_id, chunk_index)`."""
    before = chunk_document(parse_document(THREE_SECTIONS, slug="tallas-anillos"))
    after = chunk_document(parse_document(INSERTED, slug="tallas-anillos"))

    identity_before = {
        chunk.citation_id: chunk_id(chunk.document_slug, chunk.section_slug)
        for chunk in before
    }
    identity_after = {
        chunk.citation_id: chunk_id(chunk.document_slug, chunk.section_slug)
        for chunk in after
    }
    for citation, identifier in identity_before.items():
        assert identity_after[citation] == identifier

    # And the position, which the trap would have used, really did move underneath them.
    index_before = {chunk.citation_id: chunk.chunk_index for chunk in before}
    index_after = {chunk.citation_id: chunk.chunk_index for chunk in after}
    moved = [key for key in index_before if index_before[key] != index_after[key]]
    assert moved, "the inserted section must have shifted the later positions"


def test_content_hash_changes_with_the_content_and_not_with_the_position() -> None:
    before = {chunk.citation_id: chunk.content_hash
              for chunk in chunk_document(parse_document(THREE_SECTIONS, slug="tallas-anillos"))}
    after = {chunk.citation_id: chunk.content_hash
             for chunk in chunk_document(parse_document(INSERTED, slug="tallas-anillos"))}
    for citation, digest in before.items():
        assert after[citation] == digest


def test_claim_scope_travels_with_the_chunk(corpus: KnowledgeCorpus) -> None:
    for document in corpus:
        for chunk, section in zip(chunk_document(document), document.sections, strict=True):
            assert chunk.claim_scope == section.claim_scope
            assert chunk.metadata()["claim_scope"] == section.claim_scope


def test_the_source_ref_is_optional_and_survives_when_present(corpus: KnowledgeCorpus) -> None:
    with_ref = [
        chunk for chunk in chunk_corpus(corpus) if "source_ref" in chunk.metadata()
    ]
    assert with_ref, "the corpus declares at least one section with a source reference"
    for chunk in with_ref:
        assert chunk.metadata()["source_ref"]
