"""Injectable product-search port. SQL lives in `search`; this file has no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from jbg_ai.retrieval.lexical import LexicalRequest


@dataclass(frozen=True)
class SearchFilters:
    """Body predicates already parsed. `family_id` is a UUID or absent."""

    materials: list[str] = field(default_factory=list)
    category: str | None = None
    family_id: UUID | None = None
    exclude_product_ids: list[UUID] = field(default_factory=list)


@dataclass(frozen=True)
class SearchHit:
    product_id: UUID
    sku: str
    distance: float
    materials: list[str]
    family_id: UUID | None
    variant_label: str | None
    #: Carried for the demoting filters of C21 and **never** emitted: the boundary rule is
    #: that .NET owns price. A stale projection may reorder a candidate, never delete it.
    price: float | None = None
    size_label: str | None = None


@dataclass(frozen=True)
class LexicalHit:
    """One row of a lexical list. `coordination` is how many counting groups it matched."""

    product_id: UUID
    sku: str
    ts_rank: float
    coordination: int
    materials: list[str]
    family_id: UUID | None
    variant_label: str | None
    price: float | None = None
    size_label: str | None = None


class ProductSearchPort(Protocol):
    """k-NN and full-text over `ai.product_document`. Implementations must not read `public`."""

    async def count_compatible(self, *, model_version_key: str, model_id: str) -> int: ...

    async def search(
        self,
        query_vec: list[float],
        *,
        threshold: float,
        depth: int,
        filters: SearchFilters,
        model_version_key: str,
        model_id: str,
    ) -> list[SearchHit]: ...

    async def search_lexical(
        self,
        request: LexicalRequest,
        *,
        depth: int,
        filters: SearchFilters,
    ) -> list[LexicalHit]: ...
