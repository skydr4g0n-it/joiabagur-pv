"""SQLAlchemy Core k-NN and full text over `ai.product_document`. No mapped class, no second engine."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.retrieval.errors import RetrievalDependencyError
from jbg_ai.retrieval.lexical import LexicalRequest, build_fragments
from jbg_ai.retrieval.ports import LexicalHit, SearchFilters, SearchHit

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

_SEARCH_SELECT = """
SELECT
  product_id,
  sku,
  (embedding <=> CAST(:q AS vector)) AS distance,
  materials,
  family_id,
  variant_label,
  price,
  size_label
FROM ai.product_document
WHERE embedding IS NOT NULL
  AND is_active IS TRUE
  AND (
    embedding_version LIKE :version_prefix
    OR embedding_model = :model_id
  )
  AND embedding <=> CAST(:q AS vector) <= :threshold
"""

_SEARCH_ORDER_LIMIT = """
ORDER BY embedding <=> CAST(:q AS vector) ASC
LIMIT :depth
"""

# `tsv @@ (...)` is the GIN-indexed predicate; `coordination DESC, ts_rank DESC` is the
# ordering D2 measured. Coordination first is what puts the conjunction's own result at the
# head of the OR list, so precision is not traded away — only a tail is added.
_LEXICAL_SELECT = """
SELECT
  product_id,
  sku,
  ts_rank(tsv, {match}) AS ts_rank,
  ({coordination}) AS coordination,
  materials,
  family_id,
  variant_label,
  price,
  size_label
FROM ai.product_document
WHERE is_active IS TRUE
  AND tsv @@ {match}
"""

_LEXICAL_ORDER_LIMIT = """
ORDER BY coordination DESC, ts_rank DESC
LIMIT :depth
"""


def _body_filter_clauses(filters: SearchFilters) -> list[str]:
    """The four predicates a person selected in the panel. They exclude; rules never do."""
    extra: list[str] = []
    if filters.materials:
        extra.append("AND materials && CAST(:materials AS text[])")
    if filters.category is not None:
        extra.append("AND piece_type = :category")
    if filters.family_id is not None:
        extra.append("AND family_id = :family_id")
    if filters.exclude_product_ids:
        extra.append("AND product_id <> ALL(CAST(:exclude_ids AS uuid[]))")
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


def _with_filters(head: str, filters: SearchFilters, tail: str) -> str:
    extra = _body_filter_clauses(filters)
    extra_sql = ("\n  " + "\n  ".join(extra) + "\n") if extra else "\n"
    return head + extra_sql + tail


def compile_search_sql(filters: SearchFilters) -> str:
    """Return the vector statement. Never filters by `pos_id`, price or stock."""
    return _with_filters(_SEARCH_SELECT, filters, _SEARCH_ORDER_LIMIT)


def compile_lexical_sql(request: LexicalRequest, filters: SearchFilters) -> tuple[str, dict]:
    """Return the lexical statement and its bound terms. Never filters by price or stock."""
    fragments = build_fragments(request, placeholder=lambda name: f":{name}")
    head = _LEXICAL_SELECT.format(
        match=fragments.match,
        coordination=fragments.coordination,
    )
    return _with_filters(head, filters, _LEXICAL_ORDER_LIMIT), dict(fragments.params)


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

    async def search(
        self,
        query_vec: list[float],
        *,
        threshold: float,
        depth: int,
        filters: SearchFilters,
        model_version_key: str,
        model_id: str,
    ) -> list[SearchHit]:
        params: dict[str, object] = {
            "q": _vector_literal(query_vec),
            "threshold": threshold,
            "depth": depth,
            "version_prefix": f"{model_version_key}%",
            "model_id": model_id,
            **_body_filter_params(filters),
        }

        sql = compile_search_sql(filters)
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
            )
            for row in rows
        ]

    async def search_lexical(
        self,
        request: LexicalRequest,
        *,
        depth: int,
        filters: SearchFilters,
    ) -> list[LexicalHit]:
        sql, terms = compile_lexical_sql(request, filters)
        params: dict[str, object] = {
            "depth": depth,
            **terms,
            **_body_filter_params(filters),
        }
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
            )
            for row in rows
        ]
