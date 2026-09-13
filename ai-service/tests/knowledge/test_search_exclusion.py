"""The per-document exclusion C30a adds to knowledge search. Offline throughout.

Same stand-ins C23's own suite uses — `InMemoryKnowledgeIndex` over the real corpus and
`LocalEmbeddingClient` — so what is under test is the real search, the real fusion and the
real threshold, with the provider and the socket replaced and nothing else.
"""

from __future__ import annotations

import asyncio

import pytest

from jbg_ai.assist.knowledge_scope import canonical_material_sheets, piece_scoped_exclusions
from jbg_ai.knowledge.chunking import chunk_corpus
from jbg_ai.knowledge.corpus import KnowledgeCorpus, material_sheet_slug
from jbg_ai.knowledge.indexer import document_id
from jbg_ai.knowledge.offline import InMemoryKnowledgeIndex, LocalEmbeddingClient
from jbg_ai.knowledge.search import (
    compile_lexical_sql,
    compile_vector_sql,
    search_knowledge,
)
from jbg_ai.retrieval.lexical import typed_request

#: The offline stand-in's own scale, as in `test_search.py`: its distances sit far above the
#: production embedder's, and the shipped 0,51 would make every one of these searches abstain.
OFFLINE_THRESHOLD = 0.81

#: A question phrased the way the sheets are, chosen because it **demonstrates the problem
#: the filter exists for**: unfiltered it returns `material-plata` together with seven other
#: canonical sheets, which is the homogeneity collapse the corpus warns about — same
#: skeleton, same register, same vocabulary, and only the material's name to tell them apart.
SILVER_CARE = "Cuidados y limpieza en casa de la plata"


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


# --- 5.1 · the parameter is additive and its rollback is passing nothing -----------------


def test_an_absent_and_an_empty_exclusion_set_return_the_same_fragments_in_order(
    corpus: KnowledgeCorpus,
) -> None:
    question = SILVER_CARE
    index = index_for(corpus)

    absent = search(corpus, question, index=index, top_k=10)
    empty = search(corpus, question, index=index, exclude_documents=(), top_k=10)

    assert absent, "the question must be answerable for this comparison to mean anything"
    assert [item.citation_id for item in absent] == [item.citation_id for item in empty]
    assert [item.score for item in absent] == [item.score for item in empty]


# --- 5.2 · both branches honour it --------------------------------------------------------


def test_an_excluded_document_contributes_no_fragment(corpus: KnowledgeCorpus) -> None:
    question = SILVER_CARE
    index = index_for(corpus)

    before = search(corpus, question, index=index, top_k=20)
    assert any(item.document_slug == "material-plata" for item in before)

    after = search(
        corpus,
        question,
        index=index,
        exclude_documents=(document_id("material-plata"),),
        top_k=20,
    )

    assert all(item.document_slug != "material-plata" for item in after)


def test_the_exclusion_reaches_the_lexical_branch_too(corpus: KnowledgeCorpus) -> None:
    """A document the vector branch was told to drop must not walk back in lexically."""
    question = SILVER_CARE
    index = index_for(corpus)
    excluded = (document_id("material-plata"),)

    hybrid = search(corpus, question, index=index, exclude_documents=excluded, top_k=20)
    vector_only = search(
        corpus,
        question,
        index=index,
        exclude_documents=excluded,
        hybrid_enabled=False,
        top_k=20,
    )

    for citations in (hybrid, vector_only):
        assert all(item.document_slug != "material-plata" for item in citations)

    # And the lexical branch of the index really is asked to drop it, not merely outvoted.
    lexical = run(
        index.lexical_search(
            typed_request("plata limpieza"), depth=60, exclude_documents=excluded
        )
    )
    assert all(hit.metadata["document_slug"] != "material-plata" for hit in lexical)


def test_both_compiled_statements_carry_the_clause_only_when_asked() -> None:
    vector = compile_vector_sql(doc_type=None, exclude_documents=True)
    lexical, _ = compile_lexical_sql(
        typed_request("plata"), doc_type=None, exclude_documents=True
    )

    for sql in (vector, lexical):
        assert "d.id <> ALL(CAST(:exclude_documents AS uuid[]))" in sql
        # Before the cut, never after: the freed slots must be refilled by the statement.
        assert sql.index(":exclude_documents") < sql.index("LIMIT :depth")

    assert ":exclude_documents" not in compile_vector_sql(doc_type=None)
    assert ":exclude_documents" not in compile_lexical_sql(
        typed_request("plata"), doc_type=None
    )[0]


def test_the_exclusion_clause_composes_with_the_doc_type_clause() -> None:
    sql = compile_vector_sql(doc_type="material", exclude_documents=True)

    assert "d.doc_type = :doc_type" in sql
    assert ":exclude_documents" in sql


# --- 5.3 · the set is built from the nine canonical sheets --------------------------------


def test_there_are_exactly_nine_canonical_material_sheets() -> None:
    sheets = canonical_material_sheets()

    assert len(sheets) == 9
    assert len(set(sheets)) == 9
    assert all(slug.startswith("material-") for slug in sheets)


def test_a_piece_of_one_material_excludes_the_other_eight_and_nothing_else() -> None:
    excluded = piece_scoped_exclusions(["plata"])

    assert len(excluded) == 8
    assert document_id(material_sheet_slug("plata")) not in excluded
    assert set(excluded) == {
        document_id(slug)
        for slug in canonical_material_sheets()
        if slug != "material-plata"
    }


def test_a_piece_of_two_materials_excludes_seven() -> None:
    excluded = piece_scoped_exclusions(["plata", "baño de oro"])

    assert len(excluded) == 7
    assert document_id(material_sheet_slug("plata")) not in excluded
    assert document_id(material_sheet_slug("baño de oro")) not in excluded


def test_a_piece_declaring_no_material_excludes_nothing() -> None:
    assert piece_scoped_exclusions([]) == ()


def test_a_synonym_resolves_to_its_canonical_sheet() -> None:
    """`925` is silver; excluding `material-plata` for a silver piece would be the defect."""
    assert piece_scoped_exclusions(["925"]) == piece_scoped_exclusions(["plata"])
    assert document_id(material_sheet_slug("plata")) not in piece_scoped_exclusions(["925"])


def test_an_unknown_material_excludes_no_more_than_it_should() -> None:
    """Erring towards excluding less: an unresolvable term is ignored, never guessed."""
    assert piece_scoped_exclusions(["titanio"]) == piece_scoped_exclusions([])


# --- 5.4 · everything that is not a canonical sheet passes --------------------------------


@pytest.mark.parametrize(
    "slug",
    [
        "material-piezas-mixtas",
        "material-marcajes-y-punzones",
        "politica-garantia",
        "politica-devoluciones-y-cambios",
        "tallas-anillos",
        "piedras-cuarzos-y-gemas-facetadas",
        "piedras-materia-organica",
        "piedras-opacas-porosas-y-tratadas",
        "joyas-playa-piscina-y-deporte",
        "regalar-sin-saber-la-talla",
    ],
)
def test_the_piece_scoped_set_never_excludes_a_document_that_is_not_a_sheet(
    slug: str,
) -> None:
    assert document_id(slug) not in piece_scoped_exclusions(["acero"])


def test_the_two_prefixed_documents_that_are_not_sheets_stay_reachable(
    corpus: KnowledgeCorpus,
) -> None:
    """They carry `doc_type: material` and are not outputs of `material_sheet_slug`.

    «¿qué significa el 925?» is answerable about a steel piece, and mixed-piece guidance is
    answerable about any piece at all.
    """
    for slug in ("material-piezas-mixtas", "material-marcajes-y-punzones"):
        document = corpus.document(slug)
        assert document is not None
        assert document.doc_type == "material"
        assert slug not in canonical_material_sheets()


def test_the_rest_of_the_corpus_is_still_reachable_with_a_piece_scoped_set(
    corpus: KnowledgeCorpus,
) -> None:
    question = "¿Se puede llevar una pieza a la piscina?"
    index = index_for(corpus)
    excluded = piece_scoped_exclusions(["acero"])

    citations = search(corpus, question, index=index, exclude_documents=excluded, top_k=20)

    assert citations, "a counter question must survive the piece-scoped filter"
    sheets = set(canonical_material_sheets()) - {"material-acero"}
    assert all(item.document_slug not in sheets for item in citations)


def test_the_declared_material_sheet_stays_reachable(corpus: KnowledgeCorpus) -> None:
    question = SILVER_CARE
    index = index_for(corpus)

    citations = search(
        corpus,
        question,
        index=index,
        exclude_documents=piece_scoped_exclusions(["plata"]),
        top_k=20,
    )

    assert any(item.document_slug == "material-plata" for item in citations)


def test_no_sheet_of_an_undeclared_material_survives_the_piece_scoped_set(
    corpus: KnowledgeCorpus,
) -> None:
    index = index_for(corpus)
    foreign = set(canonical_material_sheets()) - {"material-acero"}

    for question in (
        "¿se puede mojar?",
        "¿se pone negro con el tiempo?",
        "¿cómo lo guardo?",
    ):
        citations = search(
            corpus,
            question,
            index=index,
            exclude_documents=piece_scoped_exclusions(["acero"]),
            top_k=20,
        )
        assert all(item.document_slug not in foreign for item in citations), question
