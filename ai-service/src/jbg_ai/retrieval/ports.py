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
    #: The drain's own 30-day figure, already counted against the `computed_as_of` recorded
    #: on that projection row and never against the wall clock. `None` means the row was not
    #: read at all — no reading scope, or this point of sale does not carry the product — and
    #: absence is NOT zero sales: no ordering rule may treat it as one.
    sales_30d: int | None = None


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
    #: How many counting groups could match any document at all. Constant per query, carried
    #: per row because it is selected in the same statement. `coordination / this` is the
    #: coverage that scales the lexical branch's weight; zero means the query expressed
    #: nothing the index can be asked about, and the caller must not divide by it.
    coverage_denominator: int = 0
    price: float | None = None
    size_label: str | None = None
    qty_bucket: str | None = None
    #: The drain's own 30-day figure, already counted against the `computed_as_of` recorded
    #: on that projection row and never against the wall clock. `None` means the row was not
    #: read at all — no reading scope, or this point of sale does not carry the product — and
    #: absence is NOT zero sales: no ordering rule may treat it as one.
    sales_30d: int | None = None


class ProductSearchPort(Protocol):
    """k-NN and full-text over `ai.product_document`. Implementations must not read `public`.

    The point of sale enters through TWO independent parameters, because restricting the
    universe and reading a signal are different things that one flag used to do at once:

    * `pos_id` RESTRICTS — the C22 prefilter, the only predicate here that removes a
      candidate on availability grounds. `None` means the whole indexed catalogue.
    * `signal_pos_id` only READS — the C25 business signals. It MUST preserve every
      candidate the branches produced, and a product this point of sale does not carry
      reports its signals as absent rather than as zero.

    Both come from a token claim or from the evaluation harness, never from the request body.
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
        signal_pos_id: UUID | None = None,
    ) -> list[SearchHit]: ...

    async def search_lexical(
        self,
        request: LexicalRequest,
        *,
        depth: int,
        filters: SearchFilters,
        pos_id: UUID | None = None,
        signal_pos_id: UUID | None = None,
    ) -> list[LexicalHit]: ...
