"""SQLAlchemy Core k-NN over `ai.product_document`. No mapped class, no second engine."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.retrieval.errors import RetrievalDependencyError
from jbg_ai.retrieval.ports import SearchFilters, SearchHit

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
  variant_label
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
LIMIT :overfetch
"""


def compile_search_sql(filters: SearchFilters) -> str:
    """Return the search statement. Never filters by `pos_id`, price or stock."""
    extra: list[str] = []
    if filters.materials:
        extra.append("AND materials && CAST(:materials AS text[])")
    if filters.category is not None:
        extra.append("AND piece_type = :category")
    if filters.family_id is not None:
        extra.append("AND family_id = :family_id")
    if filters.exclude_product_ids:
        extra.append("AND product_id <> ALL(CAST(:exclude_ids AS uuid[]))")
    extra_sql = ("\n  " + "\n  ".join(extra) + "\n") if extra else "\n"
    return _SEARCH_SELECT + extra_sql + _SEARCH_ORDER_LIMIT


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"


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
        overfetch: int,
        filters: SearchFilters,
        model_version_key: str,
        model_id: str,
    ) -> list[SearchHit]:
        params: dict[str, object] = {
            "q": _vector_literal(query_vec),
            "threshold": threshold,
            "overfetch": overfetch,
            "version_prefix": f"{model_version_key}%",
            "model_id": model_id,
        }
        if filters.materials:
            params["materials"] = list(filters.materials)
        if filters.category is not None:
            params["category"] = filters.category
        if filters.family_id is not None:
            params["family_id"] = filters.family_id
        if filters.exclude_product_ids:
            params["exclude_ids"] = [str(item) for item in filters.exclude_product_ids]

        sql = compile_search_sql(filters)
        try:
            async with session_scope(self._settings) as session:
                rows = (await session.execute(text(sql), params)).mappings().all()
        except SQLAlchemyError as exc:
            raise RetrievalDependencyError(f"database query failed: {exc}") from exc

        hits: list[SearchHit] = []
        for row in rows:
            materials = row["materials"]
            if materials is None:
                materials_list: list[str] = []
            elif isinstance(materials, list):
                materials_list = [str(item) for item in materials]
            else:
                materials_list = list(materials)
            family = row["family_id"]
            hits.append(
                SearchHit(
                    product_id=UUID(str(row["product_id"])),
                    sku=str(row["sku"]),
                    distance=float(row["distance"]),
                    materials=materials_list,
                    family_id=UUID(str(family)) if family is not None else None,
                    variant_label=(
                        str(row["variant_label"])
                        if row["variant_label"] is not None
                        else None
                    ),
                )
            )
        return hits
