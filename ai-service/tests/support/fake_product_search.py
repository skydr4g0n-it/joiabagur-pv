"""In-memory product search port. No sockets, no RDS. Delivered by C14, extended by C21."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from jbg_ai.enrichment.vocab import fold
from jbg_ai.retrieval.lexical import LexicalRequest
from jbg_ai.retrieval.ports import LexicalHit, SearchFilters, SearchHit


@dataclass
class FakeIndexedRow:
    """A stored document with a precomputed distance to the test query vector.

    `doc_text` stands in for the generated `tsv`: the fake matches a surface form when the
    folded form appears in the folded text, which is enough to exercise OR between groups,
    the coordination tally and the body filters without a Spanish text-search configuration.
    """

    product_id: UUID
    sku: str
    distance: float
    materials: list[str] = field(default_factory=list)
    family_id: UUID | None = None
    variant_label: str | None = None
    piece_type: str | None = None
    price: float | None = None
    size_label: str | None = None
    doc_text: str = ""
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
        self.lexical_calls: list[dict[str, object]] = []

    async def count_compatible(self, *, model_version_key: str, model_id: str) -> int:
        self.count_calls.append((model_version_key, model_id))
        if self.compatible_count_override is not None:
            return self.compatible_count_override
        return sum(
            1
            for row in self.rows
            if row.is_active and row.has_embedding and row.compatible
        )

    def _passes_body_filters(self, row: FakeIndexedRow, filters: SearchFilters) -> bool:
        if filters.materials and not set(filters.materials) & set(row.materials):
            return False
        if filters.category is not None and row.piece_type != filters.category:
            return False
        if filters.family_id is not None and row.family_id != filters.family_id:
            return False
        return row.product_id not in filters.exclude_product_ids

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
        self.search_calls.append(
            {
                "query_vec": list(query_vec),
                "threshold": threshold,
                "depth": depth,
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
            if not self._passes_body_filters(row, filters):
                continue
            hits.append(
                SearchHit(
                    product_id=row.product_id,
                    sku=row.sku,
                    distance=row.distance,
                    materials=list(row.materials),
                    family_id=row.family_id,
                    variant_label=row.variant_label,
                    price=row.price,
                    size_label=row.size_label,
                )
            )
        hits.sort(key=lambda item: item.distance)
        return hits[:depth]

    async def search_lexical(
        self,
        request: LexicalRequest,
        *,
        depth: int,
        filters: SearchFilters,
    ) -> list[LexicalHit]:
        self.lexical_calls.append(
            {"request": request, "depth": depth, "filters": filters}
        )
        groups = request.groups or ((request.text,),)
        counting = request.counting or tuple(True for _ in groups)

        hits: list[LexicalHit] = []
        for row in self.rows:
            if not row.is_active:
                continue
            if not self._passes_body_filters(row, filters):
                continue
            matched = [self._group_matches(row, group) for group in groups]
            if not any(matched):
                continue
            coordination = sum(
                1
                for hit, counts in zip(matched, counting, strict=False)
                if hit and counts
            )
            hits.append(
                LexicalHit(
                    product_id=row.product_id,
                    sku=row.sku,
                    ts_rank=sum(matched) / len(matched),
                    coordination=coordination,
                    materials=list(row.materials),
                    family_id=row.family_id,
                    variant_label=row.variant_label,
                    price=row.price,
                    size_label=row.size_label,
                )
            )
        hits.sort(key=lambda item: (-item.coordination, -item.ts_rank, item.sku))
        return hits[:depth]

    @staticmethod
    def _group_matches(row: FakeIndexedRow, group: tuple[str, ...]) -> bool:
        haystack = fold(row.doc_text)
        return any(fold(form) in haystack for form in group if form.strip())
