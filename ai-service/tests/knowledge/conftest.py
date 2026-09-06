"""Fixtures of the knowledge suite. Delivered by C23.

Every test in this directory runs **offline**: no LLM, no embedding provider, no RDS. The
two that need PostgreSQL ask for the shared `migrated` fixture, which skips itself when no
Docker daemon is reachable.

The corpus is loaded once per session because it is 32 files that never change during a
run, and parsing it per test would dominate the suite's runtime for no isolation gained:
`KnowledgeCorpus` and everything it holds are frozen dataclasses.
"""

from __future__ import annotations

import pytest

from jbg_ai.knowledge.chunking import chunk_corpus
from jbg_ai.knowledge.corpus import KnowledgeCorpus, load_corpus


@pytest.fixture(scope="session")
def corpus() -> KnowledgeCorpus:
    return load_corpus()


@pytest.fixture(scope="session")
def chunks(corpus: KnowledgeCorpus):
    return chunk_corpus(corpus)
