"""Injectable product-search port. SQL lives in `search`; this file has no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
    #: The projection bucket for this point of sale, when the scope was applied. Carried for
    #: the availability demotion and never emitted: an exact stock figure does not exist here
    #: and a bucket on the wire would be the beginning of one. `None` means the query ran
    #: unscoped, which is not the same as a bucket of zero.
    qty_bucket: str | None = None


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
    qty_bucket: str | None = None


class ProductSearchPort(Protocol):
    """k-NN and full-text over `ai.product_document`. Implementations must not read `public`.

    `pos_id` is the point-of-sale scope and the only predicate here that removes a candidate
    on availability grounds. It comes from the token claim, never from the request body, and
    `None` means the query runs over the whole indexed catalogue.
    """

    async def count_compatible(self, *, model_version_key: str, model_id: str) -> int: ...

    async def count_scope(self, pos_id: UUID) -> int:
        """Assigned rows this point of sale carries. Zero is a dependency failure."""
        ...

    async def projection_synced_at(self) -> datetime | None:
        """When the POS drain last ran, from the checkpoint — never from `refreshed_at`."""
        ...

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
    ) -> list[SearchHit]: ...

    async def search_lexical(
        self,
        request: LexicalRequest,
        *,
        depth: int,
        filters: SearchFilters,
        pos_id: UUID | None = None,
    ) -> list[LexicalHit]: ...
