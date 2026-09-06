"""Offline stand-ins for the provider and the database. Delivered by C23.

The specification of the mini-measurement is explicit: it **must run offline, without
calling an embedding or a language model provider**, and its result must not depend on the
day it is run. That rules out measuring against OpenAI vectors, so this module supplies a
**deterministic local embedder** and an **in-memory index**, and the measurement runs
entirely inside the process.

What that buys and what it costs, stated plainly because it matters when the numbers are
read:

- **Buys** reproducibility. The same corpus and the same fixture give the same Recall@3,
  the same MRR and the same abstention rate on any machine, for ever, with no key and no
  container. A regression in chunking, in the fusion or in the threshold shows up as a
  moved number rather than as provider noise.
- **Costs** absolute realism. `LocalEmbeddingClient` scores lexical overlap, not meaning:
  it will not know that «¿se puede mojar?» and «agua salada» are the same question. Its
  distance distribution is therefore **not** the distribution of
  `openai/text-embedding-3-small`, and a threshold calibrated here is a calibrated *rule*
  and a provisional *number*. Re-running the calibration against the production embedder,
  once a real index exists, is written down as a follow-up rather than assumed away.

It is a stand-in with the same interface, never a fallback: nothing in the service path
constructs it, and `indexing/embeddings.py` — frozen by C11 — is untouched.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from jbg_ai.enrichment.vocab import fold
from jbg_ai.indexing.constants import EMBEDDING_DIM
from jbg_ai.indexing.embeddings import EmbedResult
from jbg_ai.knowledge.chunking import KnowledgeChunk
from jbg_ai.knowledge.constants import KNOWLEDGE_PREPROCESSING_VERSION
from jbg_ai.knowledge.search import KnowledgeHit
from jbg_ai.retrieval.lexical import LexicalRequest

LOCAL_MODEL_ID = "offline/knowledge-lexical-v1"

#: Spanish function words. They appear in every section of the corpus, so leaving them in
#: would make every pair of fragments look similar and flatten the distance distribution
#: the abstention threshold is calibrated on.
_STOPWORDS = frozenset(
    """
    a al algo alguna algunas alguno algunos ante antes aunque cada como con contra cual
    cuales cuando cuanto de del desde donde dos e el ella ellas ello ellos en entre era
    eran es esa esas ese eso esos esta estan estas este esto estos ha hace hacen hasta hay
    la las le les lo los mas me mi mientras muy no ni nos o os otra otras otro otros para
    pero poco por porque que quien se segun ser si sin sobre solo son su sus tan tanto te
    tiene tienen todo todos tras un una uno unos y ya
    """.split()
)

_WORD = re.compile(r"[0-9a-z]+")

#: Character n-gram width. Cheap morphology: `limpieza` and `limpiar` share `limpi`, which
#: is what the Spanish stemmer would give the lexical branch and what a bag of whole words
#: would miss.
_NGRAM = 5
_NGRAM_WEIGHT = 0.35


def tokenise(text: str) -> list[str]:
    """Fold, split on non-alphanumerics, drop function words and single letters."""
    return [
        token
        for token in _WORD.findall(fold(text))
        if len(token) > 1 and token not in _STOPWORDS
    ]


def _bucket(token: str) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % EMBEDDING_DIM


def local_vector(text: str, *, dimension: int = EMBEDDING_DIM) -> list[float]:
    """A deterministic, L2-normalised bag-of-features vector.

    Sublinear term frequency (`1 + log tf`) so a word repeated four times in a 140-word
    section does not outweigh four different words, which is the same reason `ts_rank`
    saturates.
    """
    counts: dict[int, float] = {}
    tokens = tokenise(text)
    for token in tokens:
        counts[_bucket(token)] = counts.get(_bucket(token), 0.0) + 1.0
        if len(token) > _NGRAM:
            for start in range(len(token) - _NGRAM + 1):
                gram = token[start : start + _NGRAM]
                key = _bucket(f"#{gram}")
                counts[key] = counts.get(key, 0.0) + _NGRAM_WEIGHT

    vector = [0.0] * dimension
    for key, count in counts.items():
        vector[key % dimension] = 1.0 + math.log(count) if count > 1 else count

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def cosine_distance(left: Sequence[float], right: Sequence[float]) -> float:
    """`1 - cos`, the same domain `<=>` returns for a pgvector cosine index: `[0, 2]`."""
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 1.0
    return 1.0 - (dot / (left_norm * right_norm))


@dataclass
class LocalEmbeddingClient:
    """`EmbeddingClient` shaped, deterministic, and it never opens a socket.

    Counts its calls, so a test can assert that a search made no provider call at all.
    """

    dimension: int = EMBEDDING_DIM
    model_id: str = LOCAL_MODEL_ID
    calls: list[list[str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.document_version_key = f"{self.model_id}:{self.dimension}:{KNOWLEDGE_PREPROCESSING_VERSION}"
        self.model_version_key = f"{self.model_id}:{self.dimension}"

    async def embed(self, texts: list[str]) -> EmbedResult:
        self.calls.append(list(texts))
        return EmbedResult(
            vectors=[local_vector(text, dimension=self.dimension) for text in texts],
            embedding_model=self.model_id,
            embedding_version=self.document_version_key,
            cache_hits=0,
        )


def _group_matches(group: Sequence[str], tokens: set[str]) -> bool:
    """One group matches when any of its surface forms does, all of whose words are present.

    Approximates `plainto_tsquery` per surface form, OR-ed inside the group: that
    constructor ANDs the words of one phrase and never applies positional adjacency.
    """
    for form in group:
        words = tokenise(form)
        if words and all(word in tokens for word in words):
            return True
    return False


@dataclass
class InMemoryKnowledgeIndex:
    """The two branches over chunks held in memory. No session, no socket.

    Its lexical branch **approximates** PostgreSQL: same shape — groups OR-ed, coordination
    counted, ordered by coordination then rank — but folded whole-word matching instead of
    the Spanish stemmer and its stopword dictionary. It exists so the measurement and the
    unit tests can exercise the real fusion, the real threshold and the real abstention
    without a container; `SqlAlchemyKnowledgeIndex` is what the service runs.
    """

    chunks: tuple[KnowledgeChunk, ...]
    vectors: dict[str, list[float]] = field(default_factory=dict)
    tokens: dict[str, set[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for chunk in self.chunks:
            self.vectors.setdefault(chunk.citation_id, local_vector(chunk.content))
            self.tokens.setdefault(chunk.citation_id, set(tokenise(chunk.content)))

    def _key(self, chunk: KnowledgeChunk):
        from jbg_ai.knowledge.indexer import chunk_id

        return chunk_id(chunk.document_slug, chunk.section_slug)

    def _hit(self, chunk: KnowledgeChunk, **extra) -> KnowledgeHit:
        return KnowledgeHit(
            chunk_id=self._key(chunk),
            content=chunk.content,
            metadata=chunk.metadata(),
            **extra,
        )

    async def vector_search(
        self,
        embedding: Sequence[float],
        *,
        threshold: float,
        depth: int,
        doc_type: str | None = None,
        model_version_key: str = "",
        model_id: str = "",
    ) -> list[KnowledgeHit]:
        scored = [
            (cosine_distance(embedding, self.vectors[chunk.citation_id]), chunk)
            for chunk in self.chunks
            if doc_type is None or chunk.doc_type == doc_type
        ]
        within = sorted(
            ((distance, chunk) for distance, chunk in scored if distance <= threshold),
            key=lambda item: (item[0], item[1].citation_id),
        )
        return [self._hit(chunk, distance=distance) for distance, chunk in within[:depth]]

    async def lexical_search(
        self,
        request: LexicalRequest,
        *,
        depth: int,
        doc_type: str | None = None,
    ) -> list[KnowledgeHit]:
        groups = request.groups or tuple((token,) for token in tokenise(request.text))
        counting = request.counting or tuple(True for _ in groups)
        results: list[tuple[int, float, KnowledgeChunk]] = []
        for chunk in self.chunks:
            if doc_type is not None and chunk.doc_type != doc_type:
                continue
            tokens = self.tokens[chunk.citation_id]
            matched = [_group_matches(group, tokens) for group in groups]
            if not any(matched):
                continue
            coordination = sum(
                1
                for hit, counts in zip(matched, counting, strict=False)
                if hit and counts
            )
            rank = sum(1 for hit in matched if hit) / max(len(tokens), 1)
            results.append((coordination, rank, chunk))

        results.sort(key=lambda item: (-item[0], -item[1], item[2].citation_id))
        return [
            self._hit(chunk, ts_rank=rank, coordination=coordination)
            for coordination, rank, chunk in results[:depth]
        ]
