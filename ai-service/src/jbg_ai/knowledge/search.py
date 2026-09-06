"""Knowledge search with citations. Delivered by C23.

**A callable of the service, not an HTTP route.** The only consumer is C30, in this same
Python process; `ai-service-api-contracts` freezes the `/v1` surface in a MUST that
enumerates ten routes, and adding one would mean regenerating the committed `openapi.json`
and agreeing it with the .NET side **in order to connect two modules of the same process**.

**No router, either.** The caller states its intent: the design already assigned the
decision to the sales agent's `consultar_conocimiento` tool. Classifying the query to guess
where to search would add a provider call and latency to every question to serve a minority.

The shape of one search:

1. `expand_query` — C20's equivalence groups, imported and not restated.
2. The **vector branch** decides *whether there is an answer at all*: k-NN cosine with the
   knowledge threshold. Return nothing and the search abstains, whatever the lexical branch
   thinks. For a question the corpus does not cover the correct answer is **no citation**,
   and C30 depends on that to have nothing with which to invent an attribution.
3. The **lexical branch** decides *the order*. It exists for a reason specific to this
   corpus: nine material sheets are structurally identical — same skeleton, same register,
   same vocabulary — and the only thing that tells them apart is the material's name, a
   short lexical token drowned in shared prose. Cosine collapses by homogeneity.
4. `fuse` — C21's module, imported verbatim. Ranks and weights only: **no cosine distance
   and no `ts_rank` value takes part in the computation**, because the two live on
   incomparable scales whose distributions move per query.

The candidate set is the vector branch's, and only the order is fused. A chunk the
similarity threshold rejected must never become a citation on lexical evidence alone: a
citation that is well formed and wrong is worse than no citation, which is the whole risk
this change is built around.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.indexing.constants import EMBEDDING_DIM
from jbg_ai.indexing.embeddings import EmbeddingClient
from jbg_ai.knowledge.errors import KnowledgeSearchError
from jbg_ai.retrieval.fusion import FusedCandidate, RankedList, fuse, normalised_scores
from jbg_ai.retrieval.lexical import LexicalRequest, build_fragments, expanded_request
from jbg_ai.retrieval.synonyms import expand_query

logger = logging.getLogger(__name__)

VECTOR_LIST = "vector"
LEXICAL_LIST = "lexical"

#: Two lists, one vote each. Deliberately **not** the product weights: those are 0.33 for
#: the vector branch against 0.5 + 0.5 for two lexical lists, and they are that way because
#: over there the distance threshold passes essentially the whole corpus, so the vector
#: branch fills its list whether or not it understood the query. Here it does not: the
#: threshold gates admission, so a branch that returns few candidates has already earned
#: the right to be believed. Parity is the honest starting point, and D7 settles it with a
#: measurement — if the lexical branch does not move the number, it is removed outright,
#: which is a stronger answer than any weight.
KNOWLEDGE_WEIGHT_VECTOR = 0.5
KNOWLEDGE_WEIGHT_LEXICAL = 0.5

#: Smoothing constant and branch depth. The corpus is ~161 chunks, so a depth of 60 is
#: already most of it; both are of the order of the product defaults on purpose, because
#: `fusion.py` documents that depth and `k` are swept together or not at all.
KNOWLEDGE_RRF_K = 60
KNOWLEDGE_BRANCH_DEPTH = 60

DEFAULT_TOP_K = 5


@dataclass(frozen=True)
class KnowledgeHit:
    """One chunk as the index returns it, before anything is fused."""

    chunk_id: UUID
    content: str
    metadata: dict[str, Any]
    distance: float | None = None
    ts_rank: float | None = None
    coordination: int = 0


@dataclass(frozen=True)
class KnowledgeCitation:
    """What the caller receives. Everything needed to present the claim honestly.

    `claim_scope` travels with the fragment and is not optional: a commitment of the
    establishment read aloud as if it were a fact of the world is the failure mode the
    whole marking mechanism exists to prevent.
    """

    citation_id: str
    document_slug: str
    document_title: str
    section_slug: str
    section_title: str
    claim_scope: str
    doc_type: str
    content: str
    score: float
    source_ref: str | None = None


class KnowledgeSearchIndex(Protocol):
    """Injectable index port. An implementation may be SQL, or may be in memory."""

    async def vector_search(
        self,
        embedding: Sequence[float],
        *,
        threshold: float,
        depth: int,
        doc_type: str | None = None,
        model_version_key: str,
        model_id: str,
    ) -> list[KnowledgeHit]: ...

    async def lexical_search(
        self,
        request: LexicalRequest,
        *,
        depth: int,
        doc_type: str | None = None,
    ) -> list[KnowledgeHit]: ...


def _citation(hit: KnowledgeHit, score: float) -> KnowledgeCitation:
    metadata = hit.metadata or {}
    return KnowledgeCitation(
        citation_id=str(metadata.get("citation_id", "")),
        document_slug=str(metadata.get("document_slug", "")),
        document_title=str(metadata.get("document_title", "")),
        section_slug=str(metadata.get("section_slug", "")),
        section_title=str(metadata.get("section_title", "")),
        claim_scope=str(metadata.get("claim_scope", "")),
        doc_type=str(metadata.get("doc_type", "")),
        content=hit.content,
        score=score,
        source_ref=metadata.get("source_ref"),
    )


def _ordered(fused: Sequence[FusedCandidate], hits: dict[UUID, KnowledgeHit], top_k: int):
    scores = normalised_scores(fused)
    out: list[KnowledgeCitation] = []
    for candidate, score in zip(fused, scores, strict=True):
        hit = hits.get(candidate.key)  # type: ignore[arg-type]
        if hit is None:
            continue
        out.append(_citation(hit, score))
        if len(out) >= top_k:
            break
    return tuple(out)


async def search_knowledge(
    question: str,
    *,
    embed: EmbeddingClient,
    index: KnowledgeSearchIndex,
    top_k: int = DEFAULT_TOP_K,
    doc_type: str | None = None,
    distance_threshold: float,
    hybrid_enabled: bool = True,
    expansion_enabled: bool = True,
    rrf_k: int = KNOWLEDGE_RRF_K,
    branch_depth: int = KNOWLEDGE_BRANCH_DEPTH,
    trace_id: str | None = None,
) -> tuple[KnowledgeCitation, ...]:
    """Answer a knowledge question with citable fragments, or with nothing at all.

    Shaped as a tool so C30 can hand it to the sales agent as `consultar_conocimiento`:
    a natural-language question, an optional `top_k` and an optional `doc_type`, and back
    a list of fragments each carrying its citation identifier and its claim scope.

    `distance_threshold`, `hybrid_enabled` and `expansion_enabled` arrive **as parameters**
    and not read from the environment inside: `Settings` supplies only the default, so a
    sweep can compare configurations in one process without restarting anything.
    """
    started = time.perf_counter()
    cleaned = question.strip()
    if not cleaned:
        return ()

    embedded = await embed.embed([cleaned])
    if not embedded.vectors:
        raise KnowledgeSearchError("the embedding client returned no vector for the question")

    vector_hits = await index.vector_search(
        embedded.vectors[0],
        threshold=distance_threshold,
        depth=branch_depth,
        doc_type=doc_type,
        model_version_key=f"{embed.model_id}:{EMBEDDING_DIM}",
        model_id=embed.model_id,
    )

    if not vector_hits:
        logger.info(
            "stage=knowledge trace_id=%s latency_ms=%.1f abstained=1 threshold=%s "
            "hybrid=%s doc_type=%s citations=0",
            trace_id,
            (time.perf_counter() - started) * 1000,
            distance_threshold,
            hybrid_enabled,
            doc_type,
        )
        return ()

    hits: dict[UUID, KnowledgeHit] = {hit.chunk_id: hit for hit in vector_hits}
    admitted = set(hits)
    lists = [
        RankedList(
            name=VECTOR_LIST,
            weight=KNOWLEDGE_WEIGHT_VECTOR,
            keys=[hit.chunk_id for hit in vector_hits],
        )
    ]

    lexical_count = 0
    if hybrid_enabled:
        expanded = expand_query(cleaned, enabled=expansion_enabled)
        lexical_hits = await index.lexical_search(
            expanded_request(expanded), depth=branch_depth, doc_type=doc_type
        )
        # Filtered **before** fusing, not after: ranks stay dense over the admitted
        # candidates, so the branch votes at full strength among the fragments the
        # threshold already accepted instead of spending its top positions on chunks
        # that can never be cited.
        keys = [hit.chunk_id for hit in lexical_hits if hit.chunk_id in admitted]
        lexical_count = len(keys)
        if keys:
            lists.append(
                RankedList(name=LEXICAL_LIST, weight=KNOWLEDGE_WEIGHT_LEXICAL, keys=keys)
            )

    fused = fuse(lists, k=rrf_k, depth=branch_depth)
    citations = _ordered(fused, hits, top_k)

    logger.info(
        "stage=knowledge trace_id=%s latency_ms=%.1f abstained=0 threshold=%s hybrid=%s "
        "expansion=%s doc_type=%s vector=%s lexical=%s citations=%s distance_min=%s",
        trace_id,
        (time.perf_counter() - started) * 1000,
        distance_threshold,
        hybrid_enabled,
        expansion_enabled,
        doc_type,
        len(vector_hits),
        lexical_count,
        len(citations),
        f"{min(hit.distance for hit in vector_hits if hit.distance is not None):.4f}"
        if any(hit.distance is not None for hit in vector_hits)
        else None,
    )
    return citations


_VECTOR_SQL = """SELECT
  c.id,
  c.content,
  c.metadata,
  (c.embedding <=> CAST(:q AS vector)) AS distance
FROM ai.knowledge_chunk c
JOIN ai.knowledge_document d ON d.id = c.document_id
WHERE c.embedding IS NOT NULL
  AND (
    c.embedding_version LIKE :version_prefix
    OR c.embedding_model = :model_id
  )
  AND c.embedding <=> CAST(:q AS vector) <= :threshold
{doc_type_clause}
ORDER BY c.embedding <=> CAST(:q AS vector) ASC
LIMIT :depth
"""

_LEXICAL_SQL = """SELECT
  c.id,
  c.content,
  c.metadata,
  ts_rank(c.tsv, {match}) AS ts_rank,
  ({coordination}) AS coordination
FROM ai.knowledge_chunk c
JOIN ai.knowledge_document d ON d.id = c.document_id
WHERE c.tsv @@ {match}
{doc_type_clause}
ORDER BY coordination DESC, ts_rank DESC
LIMIT :depth
"""

_DOC_TYPE_CLAUSE = "  AND d.doc_type = :doc_type\n"


def compile_vector_sql(*, doc_type: str | None) -> str:
    """The k-NN statement. `<=>` and nothing else, to stay aligned with the HNSW class.

    The index is built with `vector_cosine_ops`; querying it with any other operator would
    make the planner ignore it **without an error** — the silent failure `ai-vector-schema`
    exists to prevent.
    """
    return _VECTOR_SQL.format(doc_type_clause=_DOC_TYPE_CLAUSE if doc_type else "")


def compile_lexical_sql(
    request: LexicalRequest, *, doc_type: str | None
) -> tuple[str, dict[str, object]]:
    """The full-text statement and its bound terms.

    SQL of this package's own. `retrieval/search.py` is tied to `ai.product_document` — its
    point-of-sale CTE, its `is_active`, its price and family columns — and is not touched.
    What **is** reused is `retrieval/lexical.py`, which composes the `tsquery` itself: one
    `plainto_tsquery` per surface form, alternatives OR-ed inside a group, every term a
    bound parameter and no query syntax ever concatenated into the statement.
    """
    fragments = build_fragments(request, placeholder=lambda name: f":{name}")
    sql = (
        _LEXICAL_SQL.replace("{match}", fragments.match)
        .replace("{coordination}", fragments.coordination)
        .format(doc_type_clause=_DOC_TYPE_CLAUSE if doc_type else "")
    )
    return sql, dict(fragments.params)


def _vector_literal(embedding: Sequence[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"


def _metadata(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


class SqlAlchemyKnowledgeIndex:
    """SQLAlchemy Core over the existing engine. No mapped class, no second engine."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def vector_search(
        self,
        embedding: Sequence[float],
        *,
        threshold: float,
        depth: int,
        doc_type: str | None = None,
        model_version_key: str,
        model_id: str,
    ) -> list[KnowledgeHit]:
        params: dict[str, object] = {
            "q": _vector_literal(embedding),
            "threshold": threshold,
            "depth": depth,
            "version_prefix": f"{model_version_key}%",
            "model_id": model_id,
        }
        if doc_type:
            params["doc_type"] = doc_type
        try:
            async with session_scope(self._settings) as session:
                rows = (
                    await session.execute(text(compile_vector_sql(doc_type=doc_type)), params)
                ).mappings().all()
        except SQLAlchemyError as exc:
            raise KnowledgeSearchError(f"database query failed: {exc}") from exc
        return [
            KnowledgeHit(
                chunk_id=UUID(str(row["id"])),
                content=str(row["content"]),
                metadata=_metadata(row["metadata"]),
                distance=float(row["distance"]),
            )
            for row in rows
        ]

    async def lexical_search(
        self,
        request: LexicalRequest,
        *,
        depth: int,
        doc_type: str | None = None,
    ) -> list[KnowledgeHit]:
        sql, terms = compile_lexical_sql(request, doc_type=doc_type)
        params: dict[str, object] = {"depth": depth, **terms}
        if doc_type:
            params["doc_type"] = doc_type
        try:
            async with session_scope(self._settings) as session:
                rows = (await session.execute(text(sql), params)).mappings().all()
        except SQLAlchemyError as exc:
            raise KnowledgeSearchError(f"database query failed: {exc}") from exc
        return [
            KnowledgeHit(
                chunk_id=UUID(str(row["id"])),
                content=str(row["content"]),
                metadata=_metadata(row["metadata"]),
                ts_rank=float(row["ts_rank"]),
                coordination=int(row["coordination"] or 0),
            )
            for row in rows
        ]
