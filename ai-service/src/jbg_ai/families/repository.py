"""SQLAlchemy Core reads over `ai.product_document`. Delivered by C18a.

Read-only, and only the schema this service owns. Python does not touch `public`
by SQL: the catalogue's truth is .NET's, and this package sees it through the
index that C13 populates. Nothing here writes, and nothing here calls the
embedding provider — the vectors were computed at indexing time and are simply
read back.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.families.errors import FamilyDependencyError
from jbg_ai.families.grouping import CandidateProduct
from jbg_ai.families.veto import MemberSimilarity

__all__ = ["load_candidates", "load_member_similarities"]

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
