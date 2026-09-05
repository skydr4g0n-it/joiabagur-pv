"""SQLAlchemy Core k-NN and full text over `ai.product_document`. No mapped class, no second engine.

The point-of-sale scope is applied here, in SQL, and it is the only predicate in this module
that removes a candidate on availability grounds. Two properties of its shape are decisions,
not accidents.

**A materialised CTE, not a plain join.** An approximate index scan does not understand
`WHERE`: it returns its neighbours and the filter discards them afterwards, silently and with
no error. Forced on this corpus that behaviour is real and reproducible — the index returns
40 of the 60 rows asked for. It is not on the live path, because at this size the planner
chooses an exact sequential scan anyway, but "the planner currently chooses well" is one
statistics refresh away from being false. `MATERIALIZED` makes the scoped subset exist before
the distance is ranked, so the branch depth is honoured by construction rather than by luck.

**Assignment, not row existence.** The hydration on the .NET side drops everything the point
of sale does not actively carry, so a candidate kept here only to be dropped there has spent
a slot in the window for nothing.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.retrieval.errors import RetrievalDependencyError
from jbg_ai.retrieval.lexical import LexicalRequest, build_fragments
from jbg_ai.retrieval.ports import LexicalHit, SearchFilters, SearchHit

#: `feed` value of the POS drain. Duplicated from the indexing package rather than imported,
#: so the retrieval path does not depend on the indexer to answer a query.
POS_FEED = "pos-availability"

COUNT_COMPATIBLE_SQL = """
SELECT count(*)
FROM ai.product_document
WHERE embedding IS NOT NULL
  AND is_active IS TRUE
  AND (
    embedding_version LIKE :version_prefix
    OR embedding_model = :model_id
  )
"""

COUNT_SCOPE_SQL = """
SELECT count(*)
FROM ai.pos_projection
WHERE pos_id = :pos_id
  AND is_assigned_hint IS TRUE
"""

# Freshness is *when we last looked*, and the checkpoint is the only column that records it.
# `max(refreshed_at)` measures when an assignment last changed, and the feed is incremental —
# a pair that never changes is never re-emitted — so it would report months of staleness on a
# projection synchronised thirty seconds ago.
PROJECTION_SYNCED_AT_SQL = """
SELECT last_incremental_sync_at
FROM ai.sync_checkpoint
WHERE feed = :feed
"""

_SCOPE_CTE = """
WITH scope AS MATERIALIZED (
  SELECT product_id, qty_bucket
  FROM ai.pos_projection
  WHERE pos_id = :pos_id
    AND is_assigned_hint IS TRUE
)
"""

_SCOPE_JOIN = "JOIN scope s ON s.product_id = d.product_id"

_SEARCH_SELECT = """SELECT
  d.product_id,
  d.sku,
  (d.embedding <=> CAST(:q AS vector)) AS distance,
  d.materials,
  d.family_id,
  d.variant_label,
  d.price,
  d.size_label,
  {qty_bucket}
FROM ai.product_document d
{scope_join}
WHERE d.embedding IS NOT NULL
  AND d.is_active IS TRUE
  AND (
    d.embedding_version LIKE :version_prefix
    OR d.embedding_model = :model_id
  )
  AND d.embedding <=> CAST(:q AS vector) <= :threshold
"""

_SEARCH_ORDER_LIMIT = """
ORDER BY d.embedding <=> CAST(:q AS vector) ASC
LIMIT :depth
"""

# `tsv @@ (...)` is the GIN-indexed predicate; `coordination DESC, ts_rank DESC` is the
# ordering D2 measured. Coordination first is what puts the conjunction's own result at the
# head of the OR list, so precision is not traded away — only a tail is added.
_LEXICAL_SELECT = """SELECT
  d.product_id,
  d.sku,
  ts_rank(d.tsv, {match}) AS ts_rank,
  ({coordination}) AS coordination,
  d.materials,
  d.family_id,
  d.variant_label,
  d.price,
  d.size_label,
  {qty_bucket}
FROM ai.product_document d
{scope_join}
WHERE d.is_active IS TRUE
  AND d.tsv @@ {match}
"""

_LEXICAL_ORDER_LIMIT = """
ORDER BY coordination DESC, ts_rank DESC
LIMIT :depth
"""


def _body_filter_clauses(filters: SearchFilters) -> list[str]:
    """The four predicates a person selected in the panel. They exclude; rules never do."""
    extra: list[str] = []
    if filters.materials:
        extra.append("AND d.materials && CAST(:materials AS text[])")
    if filters.category is not None:
        extra.append("AND d.piece_type = :category")
    if filters.family_id is not None:
        extra.append("AND d.family_id = :family_id")
    if filters.exclude_product_ids:
        extra.append("AND d.product_id <> ALL(CAST(:exclude_ids AS uuid[]))")
    return extra


def _body_filter_params(filters: SearchFilters) -> dict[str, object]:
    params: dict[str, object] = {}
    if filters.materials:
        params["materials"] = list(filters.materials)
    if filters.category is not None:
        params["category"] = filters.category
    if filters.family_id is not None:
        params["family_id"] = filters.family_id
    if filters.exclude_product_ids:
        params["exclude_ids"] = [str(item) for item in filters.exclude_product_ids]
    return params


def _scoped(head: str, *, scoped: bool) -> str:
    """Fill the two holes the scope opens: what selects the bucket, and what joins it."""
    return head.format(
        qty_bucket="s.qty_bucket" if scoped else "NULL AS qty_bucket",
        scope_join=_SCOPE_JOIN if scoped else "",
    )


def _with_filters(head: str, filters: SearchFilters, tail: str, *, scoped: bool) -> str:
    extra = _body_filter_clauses(filters)
    extra_sql = ("\n  " + "\n  ".join(extra) + "\n") if extra else "\n"
    return (_SCOPE_CTE if scoped else "") + _scoped(head, scoped=scoped) + extra_sql + tail


def compile_search_sql(filters: SearchFilters, *, scoped: bool = False) -> str:
    """Return the vector statement. Filters by `pos_id` when scoped, never by price or stock."""
    return _with_filters(_SEARCH_SELECT, filters, _SEARCH_ORDER_LIMIT, scoped=scoped)


def compile_lexical_sql(
    request: LexicalRequest, filters: SearchFilters, *, scoped: bool = False
) -> tuple[str, dict]:
    """Return the lexical statement and its bound terms. Never filters by price or stock."""
    fragments = build_fragments(request, placeholder=lambda name: f":{name}")
    head = _LEXICAL_SELECT.replace("{match}", fragments.match).replace(
        "{coordination}", fragments.coordination
    )
    return (
        _with_filters(head, filters, _LEXICAL_ORDER_LIMIT, scoped=scoped),
        dict(fragments.params),
    )


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"


def _materials_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(item) for item in value]  # type: ignore[union-attr]


def _optional_uuid(value: object) -> UUID | None:
    return UUID(str(value)) if value is not None else None


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None  # type: ignore[arg-type]


class SqlAlchemyProductSearch:
    """Core implementation over the existing engine (pool 5, max_overflow=0)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def count_compatible(self, *, model_version_key: str, model_id: str) -> int:
        params = {
            "version_prefix": f"{model_version_key}%",
            "model_id": model_id,
        }
        try:
            async with session_scope(self._settings) as session:
                value = (
                    await session.execute(text(COUNT_COMPATIBLE_SQL), params)
                ).scalar()
        except SQLAlchemyError as exc:
            raise RetrievalDependencyError(f"database query failed: {exc}") from exc
        return int(value or 0)

    async def count_scope(self, pos_id: UUID) -> int:
        try:
            async with session_scope(self._settings) as session:
                value = (
                    await session.execute(text(COUNT_SCOPE_SQL), {"pos_id": pos_id})
                ).scalar()
        except SQLAlchemyError as exc:
            raise RetrievalDependencyError(f"database query failed: {exc}") from exc
        return int(value or 0)

    async def projection_synced_at(self) -> datetime | None:
        try:
            async with session_scope(self._settings) as session:
                value = (
                    await session.execute(
                        text(PROJECTION_SYNCED_AT_SQL), {"feed": POS_FEED}
                    )
                ).scalar()
        except SQLAlchemyError as exc:
            raise RetrievalDependencyError(f"database query failed: {exc}") from exc
        return value

    async def search(
        self,
        query_vec: list[float],
        *,
        threshold: float,
        depth: int,
        filters: SearchFilters,
        model_version_key: str,
        model_id: str,
        pos_id: UUID | None = None,
    ) -> list[SearchHit]:
        params: dict[str, object] = {
            "q": _vector_literal(query_vec),
            "threshold": threshold,
            "depth": depth,
            "version_prefix": f"{model_version_key}%",
            "model_id": model_id,
            **_body_filter_params(filters),
        }
        if pos_id is not None:
            params["pos_id"] = pos_id

        sql = compile_search_sql(filters, scoped=pos_id is not None)
        try:
            async with session_scope(self._settings) as session:
                rows = (await session.execute(text(sql), params)).mappings().all()
        except SQLAlchemyError as exc:
            raise RetrievalDependencyError(f"database query failed: {exc}") from exc

        return [
            SearchHit(
                product_id=UUID(str(row["product_id"])),
                sku=str(row["sku"]),
                distance=float(row["distance"]),
                materials=_materials_list(row["materials"]),
                family_id=_optional_uuid(row["family_id"]),
                variant_label=_optional_str(row["variant_label"]),
                price=_optional_float(row["price"]),
                size_label=_optional_str(row["size_label"]),
                qty_bucket=_optional_str(row["qty_bucket"]),
            )
            for row in rows
        ]

    async def search_lexical(
        self,
        request: LexicalRequest,
        *,
        depth: int,
        filters: SearchFilters,
        pos_id: UUID | None = None,
    ) -> list[LexicalHit]:
        sql, terms = compile_lexical_sql(request, filters, scoped=pos_id is not None)
        params: dict[str, object] = {
            "depth": depth,
            **terms,
            **_body_filter_params(filters),
        }
        if pos_id is not None:
            params["pos_id"] = pos_id
        try:
            async with session_scope(self._settings) as session:
                rows = (await session.execute(text(sql), params)).mappings().all()
        except SQLAlchemyError as exc:
            raise RetrievalDependencyError(f"database query failed: {exc}") from exc

        return [
            LexicalHit(
                product_id=UUID(str(row["product_id"])),
                sku=str(row["sku"]),
                ts_rank=float(row["ts_rank"]),
                coordination=int(row["coordination"] or 0),
                materials=_materials_list(row["materials"]),
                family_id=_optional_uuid(row["family_id"]),
                variant_label=_optional_str(row["variant_label"]),
                price=_optional_float(row["price"]),
                size_label=_optional_str(row["size_label"]),
                qty_bucket=_optional_str(row["qty_bucket"]),
            )
            for row in rows
        ]
