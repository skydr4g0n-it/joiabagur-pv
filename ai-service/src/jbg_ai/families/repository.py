"""SQLAlchemy Core reads over `ai.product_document`. Delivered by C18a.

Read-only, and only the schema this service owns. Python does not touch `public`
by SQL: the catalogue's truth is .NET's, and this package sees it through the
index that C13 populates. Nothing here writes, and nothing here calls the
embedding provider — the vectors were computed at indexing time and are simply
read back.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.families.errors import FamilyDependencyError
from jbg_ai.families.grouping import CandidateProduct
from jbg_ai.families.veto import MemberSimilarity

__all__ = [
    "PersistedMember",
    "OrphanCandidate",
    "load_candidates",
    "load_member_similarities",
    "load_family_memberships",
    "load_orphan_candidates",
]

_CANDIDATES_SELECT = """
SELECT
  product_id,
  sku,
  name,
  piece_type,
  family_id
FROM ai.product_document
WHERE is_active IS TRUE
"""
# No `embedding` column on purpose. An earlier version selected it as
# `embedding::real[]` so the veto could run in Python, and then the veto turned out
# to be a comparison between groups that PostgreSQL answers far better with `<=>`
# (see `load_member_similarities`). Reading it here spent 1200 x 1536 floats per
# call on a value nothing went on to look at.

_ORDER_BY = "\nORDER BY sku"


def _compile_candidates_sql(piece_type: str | None) -> str:
    """Append the piece-type predicate only when there is one.

    A `(:p IS NULL OR piece_type = :p)` predicate reads better and does not work:
    PostgreSQL cannot infer the type of an untyped null parameter and rejects the
    statement. Building the clause conditionally is what `retrieval.search` already
    does for its optional filters.
    """
    if piece_type is None:
        return _CANDIDATES_SELECT + _ORDER_BY
    return _CANDIDATES_SELECT + "  AND piece_type = :piece_type" + _ORDER_BY


async def load_candidates(
    settings: Settings, piece_type: str | None = None
) -> list[CandidateProduct]:
    """Read every active indexed product, optionally narrowed to one piece type.

    Inactive rows are skipped: a product outside the indexable set has no place in
    a family proposal, and including it would offer the administrator a grouping
    that the feed would tombstone straight afterwards.

    Text columns only. The vectors are never loaded into Python: the veto needs
    similarities between products rather than the vectors themselves, and one
    `load_member_similarities` statement computes them all in the database.
    """
    sql = _compile_candidates_sql(piece_type)
    params = {} if piece_type is None else {"piece_type": piece_type}
    try:
        async with session_scope(settings) as session:
            result = await session.execute(text(sql), params)
            return [_to_candidate(dict(row)) for row in result.mappings()]
    except SQLAlchemyError as exc:
        raise FamilyDependencyError(f"database query failed: {exc}") from exc


def _to_candidate(row: dict[str, object]) -> CandidateProduct:
    return CandidateProduct(
        product_id=row["product_id"],  # type: ignore[arg-type]
        sku=str(row["sku"]),
        name=str(row["name"]),
        piece_type=str(row["piece_type"]) if row["piece_type"] is not None else None,
        family_id=row["family_id"],  # type: ignore[arg-type]
    )


_SIMILARITY_SQL = """
SELECT
  a.sku AS member_sku,
  b.sku AS other_sku,
  1 - (a.embedding <=> b.embedding) AS similarity
FROM ai.product_document a
JOIN ai.product_document b ON b.product_id <> a.product_id
WHERE a.sku = ANY(:skus)
  AND b.sku = ANY(:skus)
  AND a.embedding IS NOT NULL
  AND b.embedding IS NOT NULL
"""


async def load_member_similarities(
    settings: Settings, membership: dict[str, tuple[str, str]]
) -> dict[str, MemberSimilarity]:
    """Worst-sibling and best-stranger similarity for every proposed member.

    `membership` maps SKU to the identity of the family it was proposed for — its
    piece type and its root, which is what the grouper keys proposals by. The root
    alone would not do: two proposals of **different** piece types can carry the same
    root, since a root is the folded name and the piece type comes from enrichment
    rather than from the name, and keying on it alone would read those two families
    as one and quietly lose every veto between them.

    Restricting the query to proposed members is the decision, not an optimisation: a
    product competing for no membership is not an alternative membership and must not
    be able to veto one. Widening the universe to the whole catalogue flags 16% of
    members against products that were never candidates for anything.

    One statement rather than one per member: the connection pool is capped at five
    for the whole service.
    """
    skus = list(membership)
    if not skus:
        return {}

    try:
        async with session_scope(settings) as session:
            result = await session.execute(text(_SIMILARITY_SQL), {"skus": skus})
            rows = result.mappings().all()
    except SQLAlchemyError as exc:
        raise FamilyDependencyError(f"similarity query failed: {exc}") from exc

    worst: dict[str, float] = {}
    best: dict[str, float] = {}
    best_family: dict[str, str] = {}
    for row in rows:
        member, other = str(row["member_sku"]), str(row["other_sku"])
        similarity = float(row["similarity"])
        if membership[member] == membership[other]:
            if similarity < worst.get(member, 2.0):
                worst[member] = similarity
        elif similarity > best.get(member, -2.0):
            best[member] = similarity
            best_family[member] = membership[other][1]

    return {
        sku: MemberSimilarity(
            worst_sibling=worst.get(sku),
            best_stranger=best.get(sku),
            stranger_family=best_family.get(sku),
        )
        for sku in skus
    }


# --------------------------------------------------------------------------------------
# C18b — the audit reads the families that exist, which is the other side of the line
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PersistedMember:
    """One row of a family that already exists, as the audit needs it."""

    product_id: UUID
    sku: str
    name: str
    piece_type: str | None
    family_id: UUID
    family_name: str | None
    variant_label: str | None


@dataclass(frozen=True)
class OrphanCandidate:
    """A product belonging to no family, and the family it looks like it belongs to."""

    product_id: UUID
    sku: str
    name: str
    piece_type: str
    data_origin: str
    family_id: UUID
    family_name: str | None
    similarity: float
    worst_sibling: float
    #: How far it beats that family's worst sibling. The nomination criterion.
    margin: float
    #: Of its five nearest neighbours of the same piece type, how many belong to
    #: this family. Reported for ranking, never used to nominate — see the module
    #: docstring of the orchestrator and `JPV_FAMILY_ORPHAN_MARGIN`.
    purity: int


_MEMBERSHIP_SELECT = """
SELECT
  product_id,
  sku,
  name,
  piece_type,
  family_id,
  family_name,
  variant_label
FROM ai.product_document
WHERE is_active IS TRUE
  AND family_id IS NOT NULL
  AND embedding IS NOT NULL
ORDER BY family_id, sku
"""


async def load_family_memberships(settings: Settings) -> list[PersistedMember]:
    """Every indexed product that belongs to a family.

    This is what makes the flagged-member queue exist at all. Suggestion converges
    by excluding products that already belong somewhere, so once a batch is approved
    its flagged members are absent from every later suggestion — and the flags were
    never persisted, because C18a deliberately kept no proposal store. Recomputing
    over the rows that exist is the only route back to the signal.

    Rows without an embedding are skipped rather than reported: a missing vector is
    an indexing gap, and the veto already refuses to blame a member for one.
    """
    try:
        async with session_scope(settings) as session:
            result = await session.execute(text(_MEMBERSHIP_SELECT))
            return [_to_member(dict(row)) for row in result.mappings()]
    except SQLAlchemyError as exc:
        raise FamilyDependencyError(f"membership query failed: {exc}") from exc


def _to_member(row: dict[str, object]) -> PersistedMember:
    return PersistedMember(
        product_id=row["product_id"],  # type: ignore[arg-type]
        sku=str(row["sku"]),
        name=str(row["name"]),
        piece_type=str(row["piece_type"]) if row["piece_type"] is not None else None,
        family_id=row["family_id"],  # type: ignore[arg-type]
        family_name=str(row["family_name"]) if row["family_name"] is not None else None,
        variant_label=(
            str(row["variant_label"]) if row["variant_label"] is not None else None
        ),
    )


_ORPHAN_SQL = """
WITH member AS (
  SELECT product_id, family_id, family_name, piece_type, embedding
  FROM ai.product_document
  WHERE is_active IS TRUE AND family_id IS NOT NULL AND embedding IS NOT NULL
),
worst_sibling AS (
  SELECT a.family_id, min(1 - (a.embedding <=> b.embedding)) AS worst
  FROM member a
  JOIN member b ON b.family_id = a.family_id AND b.product_id <> a.product_id
  GROUP BY a.family_id
),
orphan AS (
  SELECT product_id, sku, name, piece_type, data_origin, embedding
  FROM ai.product_document
  WHERE is_active IS TRUE
    AND family_id IS NULL
    AND piece_type IS NOT NULL
    AND embedding IS NOT NULL
),
scored AS (
  SELECT
    o.product_id, o.sku, o.name, o.piece_type, o.data_origin,
    m.family_id, m.family_name,
    max(1 - (o.embedding <=> m.embedding)) AS similarity,
    w.worst
  FROM orphan o
  JOIN member m ON m.piece_type = o.piece_type
  JOIN worst_sibling w ON w.family_id = m.family_id
  GROUP BY o.product_id, o.sku, o.name, o.piece_type, o.data_origin,
           m.family_id, m.family_name, w.worst
),
best AS (
  SELECT *, row_number() OVER (
    PARTITION BY product_id ORDER BY (similarity - worst) DESC
  ) AS rank
  FROM scored
),
neighbour AS (
  SELECT o.product_id, n.family_id
  FROM orphan o
  CROSS JOIN LATERAL (
    SELECT d.family_id
    FROM ai.product_document d
    WHERE d.is_active IS TRUE
      AND d.embedding IS NOT NULL
      AND d.product_id <> o.product_id
      AND d.piece_type = o.piece_type
    ORDER BY o.embedding <=> d.embedding
    LIMIT 5
  ) n
),
purity AS (
  SELECT product_id, family_id, count(*) AS votes
  FROM neighbour
  WHERE family_id IS NOT NULL
  GROUP BY product_id, family_id
)
SELECT
  b.product_id, b.sku, b.name, b.piece_type, b.data_origin,
  b.family_id, b.family_name, b.similarity, b.worst,
  (b.similarity - b.worst) AS margin,
  COALESCE(p.votes, 0) AS purity
FROM best b
LEFT JOIN purity p ON p.product_id = b.product_id AND p.family_id = b.family_id
WHERE b.rank = 1
  AND (b.similarity - b.worst) > :margin
ORDER BY (b.similarity - b.worst) DESC, b.sku
"""


async def load_orphan_candidates(
    settings: Settings, *, margin: float
) -> list[OrphanCandidate]:
    """Products belonging to no family that beat some family's worst sibling.

    **The criterion is the relative margin, and the piece-type gate is inside the
    join, not a filter applied afterwards.** An orphan only competes against families
    whose members share its piece type, which is both the correct semantics and what
    keeps the comparison space from being 671 x 156.

    Neighbourhood purity is computed and returned, but never nominates. Measured over
    this corpus, purity fires on 55 synthetic orphans against 19 real ones, because
    C06b built deliberate `vN` near-duplicate families that purity reads as missing
    members; the margin fires on 21 real against 1 synthetic. Purity earns its place
    ranking a list the margin already chose.

    Each orphan yields **at most one** candidacy — the family it beats by the widest
    margin — rather than one per family it happens to beat. A reviewer answers "does
    this belong to that family", and offering the same product against four families
    turns one question into four.

    One statement, as everywhere in this package: the pool is capped at five
    connections for the whole service, and the vectors never leave PostgreSQL.
    """
    try:
        async with session_scope(settings) as session:
            result = await session.execute(text(_ORPHAN_SQL), {"margin": margin})
            return [_to_orphan(dict(row)) for row in result.mappings()]
    except SQLAlchemyError as exc:
        raise FamilyDependencyError(f"orphan query failed: {exc}") from exc


def _to_orphan(row: dict[str, object]) -> OrphanCandidate:
    return OrphanCandidate(
        product_id=row["product_id"],  # type: ignore[arg-type]
        sku=str(row["sku"]),
        name=str(row["name"]),
        piece_type=str(row["piece_type"]),
        data_origin=str(row["data_origin"]),
        family_id=row["family_id"],  # type: ignore[arg-type]
        family_name=str(row["family_name"]) if row["family_name"] is not None else None,
        similarity=float(row["similarity"]),  # type: ignore[arg-type]
        worst_sibling=float(row["worst"]),  # type: ignore[arg-type]
        margin=float(row["margin"]),  # type: ignore[arg-type]
        purity=int(row["purity"]),  # type: ignore[arg-type]
    )
