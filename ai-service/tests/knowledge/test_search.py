"""Knowledge search: citations, abstention and the two branches. Delivered by C23.

Offline throughout, over `InMemoryKnowledgeIndex` and `LocalEmbeddingClient`. What is under
test is the **real** search: the real query expansion, the real fusion module of C21, the
real threshold and the real abstention. What the stand-ins replace is the provider and the
socket, which is exactly what the change promised not to need in its tests.
"""

from __future__ import annotations

import asyncio

from jbg_ai.knowledge.chunking import chunk_corpus
from jbg_ai.knowledge.corpus import KnowledgeCorpus
from jbg_ai.knowledge.offline import InMemoryKnowledgeIndex, LocalEmbeddingClient
from jbg_ai.knowledge.search import search_knowledge
from support.paths import OPENAPI_SNAPSHOT

#: The offline stand-in's own scale, not the production default: this suite runs against
#: `LocalEmbeddingClient`, whose distances sit far higher than the real embedder's. Using
#: the shipped default here would make every one of these searches abstain.
OFFLINE_THRESHOLD = 0.81


def run(coro):
    return asyncio.run(coro)


def index_for(corpus: KnowledgeCorpus) -> InMemoryKnowledgeIndex:
    return InMemoryKnowledgeIndex(chunks=chunk_corpus(corpus))


def search(corpus: KnowledgeCorpus, question: str, **overrides):
    embed = overrides.pop("embed", None) or LocalEmbeddingClient()
    return run(
        search_knowledge(
            question,
            embed=embed,
            index=overrides.pop("index", None) or index_for(corpus),
            distance_threshold=overrides.pop("distance_threshold", OFFLINE_THRESHOLD),
            **overrides,
        )
    )


def test_knowledge_search_returns_chunk_with_citation_id(corpus: KnowledgeCorpus) -> None:
    results = search(corpus, "¿Qué le hace el cloro de la piscina a una pieza con baño de oro?")

    assert results
    first = results[0]
    assert first.citation_id == f"{first.document_slug}#{first.section_slug}"
    assert first.document_title
    assert first.section_title
    assert first.content.startswith(f"# {first.document_title}\n## {first.section_title}")
    assert 0.0 <= first.score <= 1.0


def test_claim_scope_travels_with_the_returned_chunk(corpus: KnowledgeCorpus) -> None:
    results = search(corpus, "¿Cuánto plazo hay para devolver o cambiar una pieza?")

    assert results
    for citation in results:
        assert citation.claim_scope in {"general", "establecimiento"}
    commitments = [item for item in results if item.claim_scope == "establecimiento"]
    assert commitments, "a question about the house's policy must return a commitment"


def test_out_of_domain_question_returns_no_citation(corpus: KnowledgeCorpus) -> None:
    """Explicit abstention, not an empty best-effort list."""
    for question in (
        "¿Cuál es la capital de Australia?",
        "¿A qué hora abre la tienda los domingos?",
        "¿Cómo se restaura un reloj de cuerda antiguo?",
    ):
        assert search(corpus, question) == (), question


def test_below_the_threshold_the_search_returns_nothing_at_all(
    corpus: KnowledgeCorpus,
) -> None:
    """A threshold nothing can meet abstains, however loud the lexical branch is."""
    question = "¿Por qué se pone negra la plata?"
    assert search(corpus, question, distance_threshold=0.05) == ()
    assert search(corpus, question, distance_threshold=0.99)


def test_hybrid_disabled_falls_back_to_vector_only(corpus: KnowledgeCorpus) -> None:
    question = "¿Se puede llevar una pulsera de cuero al mar?"
    index = index_for(corpus)

    hybrid = search(corpus, question, index=index, hybrid_enabled=True)
    vector = search(corpus, question, index=index, hybrid_enabled=False)

    assert hybrid and vector
    # Same admitted candidates either way: the lexical branch reorders, it never admits.
    assert {item.citation_id for item in vector} <= {
        item.citation_id
        for item in search(corpus, question, index=index, hybrid_enabled=True, top_k=50)
    }
    # And the flag really is the effective value of the call, not an environment read.
    assert vector == search(corpus, question, index=index, hybrid_enabled=False)


def test_knowledge_search_makes_no_provider_call_with_injected_fake(
    corpus: KnowledgeCorpus,
) -> None:
    embed = LocalEmbeddingClient()
    search(corpus, "¿Qué significa el punzón 925?", embed=embed)

    assert embed.calls == [["¿Qué significa el punzón 925?"]], (
        "exactly one embedding of the question, and it never left the process"
    )


def test_an_empty_question_asks_nothing_and_returns_nothing(
    corpus: KnowledgeCorpus,
) -> None:
    embed = LocalEmbeddingClient()
    assert search(corpus, "   ", embed=embed) == ()
    assert embed.calls == []


def test_the_caller_can_restrict_by_doc_type_and_only_if_it_asks(
    corpus: KnowledgeCorpus,
) -> None:
    question = "¿Qué cubre la garantía de una pieza?"
    index = index_for(corpus)

    unrestricted = search(corpus, question, index=index, top_k=10)
    restricted = search(corpus, question, index=index, doc_type="politica", top_k=10)

    assert restricted
    assert {item.doc_type for item in restricted} == {"politica"}
    assert len(restricted) <= len(unrestricted)


def test_fusion_consumes_ranks_and_not_raw_scores(corpus: KnowledgeCorpus) -> None:
    """The returned score is the normalised RRF score, never a cosine distance."""
    results = search(corpus, "¿Cómo se limpia una perla en casa?", top_k=5)

    assert results
    assert results[0].score == 1.0
    scores = [item.score for item in results]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= value <= 1.0 for value in scores)


def test_knowledge_search_opens_no_http_surface() -> None:
    snapshot = OPENAPI_SNAPSHOT.read_text(encoding="utf-8")
    assert "knowledge" not in snapshot.casefold()


def test_a_care_question_about_one_material_answers_from_that_sheet(
    corpus: KnowledgeCorpus,
) -> None:
    """D7's prediction, as a test: the branch that tells the near-identical sheets apart.

    The scenario asks for the sheet among the first three and not at position one, and
    that wording is deliberate. Against the offline stand-in — which scores lexical
    overlap and not meaning — the first hit for a care question is often a section of
    `joyas-playa-piscina-y-deporte` that legitimately answers it too, so pinning position
    one would pin the stand-in rather than the property.
    """
    index = index_for(corpus)
    question = "¿Cómo se cuida y se limpia una pieza de latón?"

    results = search(corpus, question, index=index, top_k=3)

    assert "material-laton" in {item.document_slug for item in results}
