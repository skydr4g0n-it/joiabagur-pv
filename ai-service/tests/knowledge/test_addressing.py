"""Fragments obtained by ADDRESS rather than by search. Delivered by C30a.

The third way into the knowledge index, and the only exact one. What it must prove is that
a consumer cannot tell which path produced a fragment — and that nothing was embedded.
"""

from __future__ import annotations

import asyncio

from jbg_ai.knowledge.chunking import chunk_corpus
from jbg_ai.knowledge.corpus import KnowledgeCorpus
from jbg_ai.knowledge.indexer import chunk_id
from jbg_ai.knowledge.offline import InMemoryKnowledgeIndex, LocalEmbeddingClient
from jbg_ai.knowledge.search import (
    ADDRESSED_SCORE,
    address_fragments,
    search_knowledge,
)

OFFLINE_THRESHOLD = 0.81


def run(coro):
    return asyncio.run(coro)


def index_for(corpus: KnowledgeCorpus) -> InMemoryKnowledgeIndex:
    return InMemoryKnowledgeIndex(chunks=chunk_corpus(corpus))


def test_an_addressed_fragment_comes_back_with_its_full_citation(
    corpus: KnowledgeCorpus,
) -> None:
    index = index_for(corpus)

    citations = run(
        address_fragments(
            (("material-plata", "cuidados-y-limpieza-en-casa"),), index=index
        )
    )

    assert len(citations) == 1
    citation = citations[0]
    assert citation.citation_id == "material-plata#cuidados-y-limpieza-en-casa"
    assert citation.document_slug == "material-plata"
    assert citation.section_slug == "cuidados-y-limpieza-en-casa"
    assert citation.document_title == "Plata"
    assert citation.section_title == "Cuidados y limpieza en casa"
    assert citation.doc_type == "material"
    assert citation.claim_scope == "general"
    assert citation.content


def test_an_addressed_fragment_is_indistinguishable_from_a_searched_one(
    corpus: KnowledgeCorpus,
) -> None:
    """Same fields, same values — only `score` differs, and it means something else."""
    index = index_for(corpus)
    addressed = run(
        address_fragments(
            (("material-plata", "cuidados-y-limpieza-en-casa"),), index=index
        )
    )[0]
    searched = [
        item
        for item in run(
            search_knowledge(
                "Cuidados y limpieza en casa de la plata",
                embed=LocalEmbeddingClient(),
                index=index,
                distance_threshold=OFFLINE_THRESHOLD,
                top_k=20,
            )
        )
        if item.citation_id == addressed.citation_id
    ]

    assert searched, "the same fragment must be reachable both ways"
    found = searched[0]
    for field in (
        "citation_id",
        "document_slug",
        "document_title",
        "section_slug",
        "section_title",
        "claim_scope",
        "doc_type",
        "content",
    ):
        assert getattr(addressed, field) == getattr(found, field), field


def test_an_addressed_fragment_scores_one_because_the_address_is_exact(
    corpus: KnowledgeCorpus,
) -> None:
    citations = run(
        address_fragments(
            (("material-plata", "piel-sensible-y-alergias"),), index=index_for(corpus)
        )
    )

    assert citations[0].score == ADDRESSED_SCORE == 1.0


def test_addressing_runs_no_search_and_makes_no_provider_call(
    corpus: KnowledgeCorpus,
) -> None:
    index = index_for(corpus)
    embed = LocalEmbeddingClient()

    citations = run(
        address_fragments(
            (
                ("material-plata", "cuidados-y-limpieza-en-casa"),
                ("material-oro", "piel-sensible-y-alergias"),
            ),
            index=index,
        )
    )

    assert len(citations) == 2
    assert embed.calls == []


def test_an_absent_section_yields_nothing_and_the_rest_resolve(
    corpus: KnowledgeCorpus,
) -> None:
    """`material-acero` carries four sections, `como-guardarlo` not among them."""
    assert corpus.document("material-acero").section("como-guardarlo") is None

    citations = run(
        address_fragments(
            (
                ("material-acero", "cuidados-y-limpieza-en-casa"),
                ("material-acero", "como-guardarlo"),
                ("material-acero", "piel-sensible-y-alergias"),
            ),
            index=index_for(corpus),
        )
    )

    assert [item.section_slug for item in citations] == [
        "cuidados-y-limpieza-en-casa",
        "piel-sensible-y-alergias",
    ]


def test_an_unknown_document_yields_nothing_at_all(corpus: KnowledgeCorpus) -> None:
    assert run(
        address_fragments((("material-titanio", "cuidados"),), index=index_for(corpus))
    ) == ()


def test_no_address_at_all_reads_nothing(corpus: KnowledgeCorpus) -> None:
    index = index_for(corpus)

    assert run(address_fragments((), index=index)) == ()


def test_the_addresses_keep_the_order_they_were_given(corpus: KnowledgeCorpus) -> None:
    """The caller's allow-list order is the citation order a consumer will render."""
    addresses = (
        ("material-oro", "piel-sensible-y-alergias"),
        ("material-plata", "cuidados-y-limpieza-en-casa"),
        ("material-oro", "cuidados-y-limpieza-en-casa"),
    )

    citations = run(address_fragments(addresses, index=index_for(corpus)))

    assert [item.citation_id for item in citations] == [
        f"{document}#{section}" for document, section in addresses
    ]


def test_the_address_resolves_to_the_identity_the_indexer_wrote(
    corpus: KnowledgeCorpus,
) -> None:
    """`chunk_id` and nothing else: the same `uuid5` the corpus was indexed under."""
    index = index_for(corpus)
    key = chunk_id("material-plata", "cuidados-y-limpieza-en-casa")

    hits = run(index.fetch_chunks([key]))

    assert [hit.chunk_id for hit in hits] == [key]
