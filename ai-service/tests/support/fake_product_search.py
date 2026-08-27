"""In-memory product search port. No sockets, no RDS. Delivered by C14."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from jbg_ai.retrieval.ports import SearchFilters, SearchHit


@dataclass
class FakeIndexedRow:
    """A stored document with a precomputed distance to the test query vector."""

    product_id: UUID
    sku: str
    distance: float
    materials: list[str] = field(default_factory=list)
    family_id: UUID | None = None
    variant_label: str | None = None
    piece_type: str | None = None
    is_active: bool = True
    has_embedding: bool = True
    compatible: bool = True


class FakeProductSearch:
    """Applies the same predicates as the SQL port against in-memory rows."""

    def __init__(
        self,
        rows: list[FakeIndexedRow] | None = None,
        *,
        compatible_count: int | None = None,
    ) -> None:
        self.rows = list(rows or [])
        self.compatible_count_override = compatible_count
        self.count_calls: list[tuple[str, str]] = []
        self.search_calls: list[dict[str, object]] = []

    async def count_compatible(self, *, model_version_key: str, model_id: str) -> int:
        self.count_calls.append((model_version_key, model_id))
        if self.compatible_count_override is not None:
            return self.compatible_count_override
        return sum(
            1
            for row in self.rows
            if row.is_active and row.has_embedding and row.compatible
        )

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
        self.search_calls.append(
            {
                "query_vec": list(query_vec),
                "threshold": threshold,
                "overfetch": overfetch,
                "filters": filters,
                "model_version_key": model_version_key,
                "model_id": model_id,
            }
        )
        hits: list[SearchHit] = []
        for row in self.rows:
            if not row.is_active or not row.has_embedding or not row.compatible:
                continue
            if row.distance > threshold:
                continue
            if filters.materials and not set(filters.materials) & set(row.materials):
                continue
            if filters.category is not None and row.piece_type != filters.category:
                continue
            if filters.family_id is not None and row.family_id != filters.family_id:
                continue
            if row.product_id in filters.exclude_product_ids:
                continue
            hits.append(
                SearchHit(
                    product_id=row.product_id,
                    sku=row.sku,
                    distance=row.distance,
                    materials=list(row.materials),
                    family_id=row.family_id,
                    variant_label=row.variant_label,
                )
            )
        hits.sort(key=lambda item: item.distance)
        return hits[:overfetch]
