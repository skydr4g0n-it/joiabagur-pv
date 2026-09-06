"""Deterministic identity and idempotent indexing. Delivered by C23.

The offline half runs against `FakeKnowledgeRepo`. The `db` half runs the real statements
against an ephemeral PostgreSQL with pgvector, because the two properties that matter most
here are properties of **statements** — that a chunk the run no longer produces is gone,
and that reordering sections does not trip the unique constraint on
`(document_id, chunk_index)` — and a fake that never executed one would prove neither.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import replace

import pytest
import sqlalchemy as sa

from jbg_ai.indexing.embeddings import document_version_key
from jbg_ai.knowledge.constants import CORPUS_DIR, KNOWLEDGE_PREPROCESSING_VERSION
from jbg_ai.knowledge.corpus import KnowledgeCorpus, parse_document
from jbg_ai.knowledge.indexer import (
    SqlAlchemyKnowledgeRepo,
    chunk_id,
    document_id,
    knowledge_version_key,
    sync_knowledge,
)
from support.async_db import run_db
from support.fake_embedding_client import FakeEmbeddingClient
from support.fake_knowledge_repo import FakeKnowledgeRepo
from support.settings import build_settings

THREE = """# Tallas de anillo

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

TWO = THREE.replace(
    """## De la talla española a los milímetros

<!-- claim_scope: general -->

La circunferencia es la talla más cuarenta.

""",
    "",
)

REORDERED = """# Tallas de anillo

<!-- doc_type: talla -->
<!-- eval_question: ¿Cómo mido mi talla de anillo? -->

## Qué aro se puede ajustar

<!-- claim_scope: general -->

Un aro liso admite dos tallas arriba o abajo.

## De la talla española a los milímetros

<!-- claim_scope: general -->

La circunferencia es la talla más cuarenta.

## Cómo medir tu talla en casa

<!-- claim_scope: general -->

Con un hilo alrededor del dedo y una regla.
"""


def corpus_of(text: str) -> KnowledgeCorpus:
    return KnowledgeCorpus(
        documents=(parse_document(text, slug="tallas-anillos"),),
        root=CORPUS_DIR,
    )


def run(coro):
    """The suite installs no asyncio plugin, by convention."""
    return asyncio.run(coro)


# --- version namespace -----------------------------------------------------------------


def test_knowledge_chunks_carry_their_own_preprocessing_version() -> None:
    model = "openai/text-embedding-3-small"
    knowledge = knowledge_version_key(model)
    product = document_version_key(model)

    assert knowledge.endswith(KNOWLEDGE_PREPROCESSING_VERSION)
    assert knowledge != product, (
        "sharing the product key would mean a change to the chunking rules invalidates "
        "nothing, leaving vectors that declare themselves current over text that is gone"
    )
    assert "source-text" not in knowledge
    # Same model and same dimension: the two corpora share the cache and the operator.
    assert knowledge.startswith(f"{model}:1536:")
    assert product.startswith(f"{model}:1536:")


# --- idempotence, offline --------------------------------------------------------------


def test_indexing_writes_every_chunk_with_a_deterministic_identity() -> None:
    repo, embed = FakeKnowledgeRepo(), FakeEmbeddingClient()
    result = run(sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))

    assert result.documents == 1
    assert result.chunks == 3
    assert result.embedded == 3
    assert repo.citation_ids() == {
        "tallas-anillos#como-medir-tu-talla-en-casa",
        "tallas-anillos#de-la-talla-espanola-a-los-milimetros",
        "tallas-anillos#que-aro-se-puede-ajustar",
    }
    for write in repo.all_chunks():
        assert write.id == chunk_id("tallas-anillos", write.metadata["section_slug"])
        assert write.document_id == document_id("tallas-anillos")
        assert write.embedding_version == knowledge_version_key(embed.model_id)


def test_unchanged_section_is_not_re_embedded() -> None:
    repo, embed = FakeKnowledgeRepo(), FakeEmbeddingClient()
    run(sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))
    calls_after_first = embed.call_count

    second = run(sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))

    assert second.embedded == 0
    assert second.skipped == 3
    assert embed.call_count == calls_after_first, "no provider batch on the second run"


def test_running_twice_over_an_unchanged_corpus_leaves_the_same_rows() -> None:
    repo, embed = FakeKnowledgeRepo(), FakeEmbeddingClient()
    run(sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))
    before = {write.id: (write.chunk_index, write.content) for write in repo.all_chunks()}

    run(sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))
    after = {write.id: (write.chunk_index, write.content) for write in repo.all_chunks()}

    assert before == after


def test_reindexing_removes_chunks_no_longer_produced() -> None:
    repo, embed = FakeKnowledgeRepo(), FakeEmbeddingClient()
    run(sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))

    result = run(sync_knowledge(corpus_of(TWO), embed=embed, repo=repo))

    assert result.deleted_chunks == 1
    assert repo.citation_ids() == {
        "tallas-anillos#como-medir-tu-talla-en-casa",
        "tallas-anillos#que-aro-se-puede-ajustar",
    }
    assert chunk_id("tallas-anillos", "de-la-talla-espanola-a-los-milimetros") in repo.deleted


def test_changing_the_preprocessing_version_recomputes_only_knowledge() -> None:
    """The reason `knowledge/v1` is not `source-text/v1`.

    A stored chunk whose recorded version is not the current one is stale **whatever its
    content hash says**, so it is recomputed. And the blast radius stops there: this
    repository only ever addresses `ai.knowledge_*`, so no product document can be marked
    stale by a change to the chunking rules — nor the other way round.
    """
    repo, embed = FakeKnowledgeRepo(), FakeEmbeddingClient()
    run(sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))

    stored = repo.chunks[document_id("tallas-anillos")]
    for key, write in stored.items():
        stored[key] = replace(write, embedding_version="openai/x:1536:knowledge/v0")

    result = run(sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))

    assert result.embedded == 3, "a stale preprocessing version recomputes every chunk"
    assert result.skipped == 0
    assert {write.embedding_version for write in repo.all_chunks()} == {
        knowledge_version_key(embed.model_id)
    }
    # And nothing outside the knowledge tables was ever addressed.
    assert set(repo.documents) == {document_id("tallas-anillos")}


def test_an_indexed_chunk_carries_no_product_identifier(corpus: KnowledgeCorpus) -> None:
    """Knowledge is general: the decision the whole corpus rests on, asserted on the rows."""
    repo, embed = FakeKnowledgeRepo(), FakeEmbeddingClient()
    run(sync_knowledge(corpus, embed=embed, repo=repo))

    allowed = {
        "citation_id",
        "document_slug",
        "document_title",
        "doc_type",
        "section_slug",
        "section_title",
        "claim_scope",
        "content_hash",
        "source_ref",
    }
    uuid_like = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

    for write in repo.all_chunks():
        assert set(write.metadata) <= allowed, write.metadata.keys()
        assert not any("product" in key for key in write.metadata)
        assert not uuid_like.search(str(write.metadata))
        assert not uuid_like.search(write.content)


def test_a_full_run_re_embeds_everything() -> None:
    repo, embed = FakeKnowledgeRepo(), FakeEmbeddingClient()
    run(sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))

    result = run(sync_knowledge(corpus_of(THREE), embed=embed, repo=repo, full=True))

    assert result.embedded == 3
    assert result.skipped == 0


def test_editing_one_section_re_embeds_only_that_one() -> None:
    repo, embed = FakeKnowledgeRepo(), FakeEmbeddingClient()
    run(sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))

    edited = THREE.replace(
        "La circunferencia es la talla más cuarenta.",
        "La circunferencia en milímetros es la talla española más cuarenta.",
    )
    result = run(sync_knowledge(corpus_of(edited), embed=embed, repo=repo))

    assert result.embedded == 1
    assert result.skipped == 2


def test_the_whole_corpus_indexes_offline(corpus: KnowledgeCorpus) -> None:
    repo, embed = FakeKnowledgeRepo(), FakeEmbeddingClient()
    result = run(sync_knowledge(corpus, embed=embed, repo=repo))

    assert result.documents == len(corpus)
    assert result.chunks == corpus.section_count
    assert result.embedded == corpus.section_count
    assert len(repo.citation_ids()) == corpus.section_count


# --- the real statements ---------------------------------------------------------------


@pytest.mark.db
def test_indexing_and_reindexing_against_postgres(migrated: sa.Engine, database_url: str) -> None:
    settings = build_settings(database_url=database_url)
    repo = SqlAlchemyKnowledgeRepo(settings)
    embed = FakeEmbeddingClient()

    def counts() -> tuple[int, int]:
        with migrated.connect() as connection:
            documents = connection.execute(
                sa.text("SELECT count(*) FROM ai.knowledge_document")
            ).scalar_one()
            chunks = connection.execute(
                sa.text("SELECT count(*) FROM ai.knowledge_chunk")
            ).scalar_one()
        return int(documents), int(chunks)

    first = run_db(lambda: sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))
    assert first.chunks == 3
    assert counts() == (1, 3)

    second = run_db(lambda: sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))
    assert second.embedded == 0
    assert second.skipped == 3
    assert counts() == (1, 3)

    third = run_db(lambda: sync_knowledge(corpus_of(TWO), embed=embed, repo=repo))
    assert third.deleted_chunks == 1
    assert counts() == (1, 2)

    with migrated.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT metadata ->> 'citation_id' AS citation, chunk_index, "
                "embedding_version, embedding IS NOT NULL AS embedded "
                "FROM ai.knowledge_chunk ORDER BY chunk_index"
            )
        ).mappings().all()
    assert [row["chunk_index"] for row in rows] == [0, 1]
    assert all(row["embedded"] for row in rows)
    assert {row["embedding_version"] for row in rows} == {
        knowledge_version_key(embed.model_id)
    }
    assert [row["citation"] for row in rows] == [
        "tallas-anillos#como-medir-tu-talla-en-casa",
        "tallas-anillos#que-aro-se-puede-ajustar",
    ]


@pytest.mark.db
def test_reordering_sections_does_not_trip_the_unique_constraint(
    migrated: sa.Engine, database_url: str
) -> None:
    """`chunk_index` is still unique per document, so the survivors are parked first."""
    settings = build_settings(database_url=database_url)
    repo = SqlAlchemyKnowledgeRepo(settings)
    embed = FakeEmbeddingClient()

    run_db(lambda: sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))
    result = run_db(lambda: sync_knowledge(corpus_of(REORDERED), embed=embed, repo=repo))

    assert result.deleted_chunks == 0
    assert result.embedded == 0, "reordering changes no content, so nothing is re-embedded"

    with migrated.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT metadata ->> 'citation_id' AS citation, chunk_index "
                "FROM ai.knowledge_chunk ORDER BY chunk_index"
            )
        ).mappings().all()
    assert [row["citation"] for row in rows] == [
        "tallas-anillos#que-aro-se-puede-ajustar",
        "tallas-anillos#de-la-talla-espanola-a-los-milimetros",
        "tallas-anillos#como-medir-tu-talla-en-casa",
    ]


@pytest.mark.db
def test_deleting_a_document_takes_its_chunks_by_cascade(
    migrated: sa.Engine, database_url: str
) -> None:
    settings = build_settings(database_url=database_url)
    repo = SqlAlchemyKnowledgeRepo(settings)
    embed = FakeEmbeddingClient()

    run_db(lambda: sync_knowledge(corpus_of(THREE), embed=embed, repo=repo))

    empty = KnowledgeCorpus(
        documents=(parse_document(THREE.replace("tallas-anillos", "otro"), slug="otro"),),
        root=CORPUS_DIR,
    )
    result = run_db(lambda: sync_knowledge(empty, embed=embed, repo=repo))

    assert result.deleted_documents == 1
    with migrated.connect() as connection:
        remaining = connection.execute(
            sa.text(
                "SELECT count(*) FROM ai.knowledge_chunk c "
                "JOIN ai.knowledge_document d ON d.id = c.document_id "
                "WHERE d.title = 'Tallas de anillo' AND d.id = :gone"
            ),
            {"gone": document_id("tallas-anillos")},
        ).scalar_one()
    assert int(remaining) == 0
