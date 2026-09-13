"""Fixtures of the assistance suite. Delivered by C30a.

Every test here runs **offline**: no language model, no embedding provider, no database.
The fakes go in through the constructor seams that already exist — `FakeProductSearch` for
the index, `InMemoryKnowledgeIndex` over the real corpus for the knowledge side — so what is
under test is the real grouping, the real rules and the real addressing, with the provider
and the socket replaced and nothing else.
"""

from __future__ import annotations

import pytest

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.knowledge.chunking import chunk_corpus
from jbg_ai.knowledge.corpus import KnowledgeCorpus, load_corpus
from jbg_ai.knowledge.offline import InMemoryKnowledgeIndex
from support.assist_world import FAMILY, LONER, PIECE, SIBLING, indexed_row
from support.fake_product_search import FakeProductSearch
from support.settings import TOKEN_POS_ID, TOKEN_TRACE_ID


@pytest.fixture(scope="session")
def corpus() -> KnowledgeCorpus:
    return load_corpus()


@pytest.fixture(scope="session")
def knowledge(corpus: KnowledgeCorpus) -> InMemoryKnowledgeIndex:
    """The real 32-document corpus, chunked by the real chunker, held in memory."""
    return InMemoryKnowledgeIndex(chunks=chunk_corpus(corpus))


@pytest.fixture
def principal() -> ServicePrincipal:
    return ServicePrincipal(
        user_id="u-1", role="Operator", trace_id=TOKEN_TRACE_ID, pos_id=TOKEN_POS_ID
    )


@pytest.fixture
def search() -> FakeProductSearch:
    """A family of two plus one product that belongs to no family at all."""
    return FakeProductSearch(
        [
            indexed_row(),
            indexed_row(product_id=SIBLING, sku="JBG-0002", variant_label="20 mm"),
            indexed_row(
                product_id=LONER, sku="JBG-0009", family_id=None, family_name=None
            ),
        ]
    )
