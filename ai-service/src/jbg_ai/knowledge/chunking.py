"""Section chunking of the knowledge corpus. Delivered by C23.

A **pure function**: no session, no provider, no socket. Given a parsed document it
returns the chunks that document produces, and nothing else.

Three decisions live here and each one earns its place.

**One `##` section is one chunk, and chunks do not overlap.** Sections are self-contained
by authoring rule, and overlapping 130-word fragments would duplicate half the corpus for
no recall it does not already have.

**The indexed content begins with both titles.** `tsv` is a column *generated over
`content`* by the schema, so putting the document title and the section title inside the
content puts them into the lexical index and into the embedding at the same time. It is the
only thing that tells nine material sheets apart — same skeleton, same register, same
vocabulary, and the material's name the one token that differs — and it costs nothing.

**The `claim_scope` marker is stripped before the content is assembled.** It is authored
metadata about the claim, not part of it; leaving it in would put the literal word
`claim_scope` into every vector and every `tsvector` in the corpus.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from jbg_ai.indexing.source_text import hash_source_text
from jbg_ai.knowledge.corpus import KnowledgeCorpus, KnowledgeDocument


def citation_id(document_slug: str, section_slug: str) -> str:
    """The human-readable locator: `<documento>#<sección>`.

    Deliberately not the row identifier and deliberately not `(document, chunk_index)`.
    With the corpus in git this string **is** the locator — it opens
    `data/knowledge/<documento>.md` and finds `## <sección>` — which is the strongest form
    of verifiability available, and here it comes for free.
    """
    return f"{document_slug}#{section_slug}"


def compose_content(document_title: str, section_title: str, body: str) -> str:
    """`# documento` + `## sección` + texto. What is embedded and what `tsv` is built from."""
    return f"# {document_title}\n## {section_title}\n\n{body}"


@dataclass(frozen=True)
class KnowledgeChunk:
    """One indexable fragment, with everything a citation needs to travel."""

    document_slug: str
    document_title: str
    doc_type: str
    section_slug: str
    section_title: str
    claim_scope: str
    chunk_index: int
    content: str
    content_hash: str
    source_ref: str | None = None

    @property
    def citation_id(self) -> str:
        return citation_id(self.document_slug, self.section_slug)

    def metadata(self) -> dict[str, Any]:
        """What is written to `ai.knowledge_chunk.metadata`.

        `content_hash` lives here and **not in a column of its own**: the table does not
        have one and this change declares zero migrations. The `jsonb` already carries a
        GIN index, so it is a place to put a field and not a place to hide one.
        """
        payload: dict[str, Any] = {
            "citation_id": self.citation_id,
            "document_slug": self.document_slug,
            "document_title": self.document_title,
            "doc_type": self.doc_type,
            "section_slug": self.section_slug,
            "section_title": self.section_title,
            "claim_scope": self.claim_scope,
            "content_hash": self.content_hash,
        }
        if self.source_ref:
            payload["source_ref"] = self.source_ref
        return payload


def chunk_document(document: KnowledgeDocument) -> tuple[KnowledgeChunk, ...]:
    """One chunk per section, in document order, without overlap."""
    chunks: list[KnowledgeChunk] = []
    for section in document.sections:
        content = compose_content(document.title, section.title, section.body)
        chunks.append(
            KnowledgeChunk(
                document_slug=document.slug,
                document_title=document.title,
                doc_type=document.doc_type,
                section_slug=section.slug,
                section_title=section.title,
                claim_scope=section.claim_scope,
                # Written because the unique constraint requires it and because it orders
                # the fragments inside a document. **Never the identity of a citation**:
                # inserting a section in the middle shifts every later index and would
                # silently repoint every later citation, with no error and no visible
                # change. See `design.md` D3.
                chunk_index=section.order,
                content=content,
                content_hash=hash_source_text(content),
                source_ref=section.source_ref or document.source_ref,
            )
        )
    return tuple(chunks)


def chunk_corpus(corpus: KnowledgeCorpus | Iterable[KnowledgeDocument]) -> tuple[KnowledgeChunk, ...]:
    """Every chunk of every document, in corpus order."""
    documents = corpus.documents if isinstance(corpus, KnowledgeCorpus) else tuple(corpus)
    return tuple(chunk for document in documents for chunk in chunk_document(document))
