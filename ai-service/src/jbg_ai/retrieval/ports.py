"""Injectable product-search port. SQL lives in `search`; this file has no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, Sequence
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


@dataclass(frozen=True)
class SourceDocument:
    """The reference product a substitutes request is anchored to. C26.

    The embedding itself is NOT carried: the k-NN runs against the stored vector inside the
    statement, so the only thing the caller needs to know here is whether there is one. A
    1.536-float list crossing this boundary would be a copy of a row the database is about
    to read anyway.

    `is_active` and `has_embedding` travel as VALUES and the absent row travels as `None`,
    because the three unusable cases are three different sentences at the boundary and the
    router is what turns them into an error. A port that raised would decide the wording of
    an HTTP response from inside the SQL layer.
    """

    product_id: UUID
    sku: str
    piece_type: str | None
    size_label: str | None
    materials: list[str]
    style_tags: list[str]
    family_id: UUID | None
    price_band: str | None
    is_active: bool
    has_embedding: bool


@dataclass(frozen=True)
class NeighbourHit:
    """One candidate substitute: a neighbour of a STORED embedding, not of a query. C26.

    It is deliberately not a `SearchHit`. That one answers "what does this query look like",
    is produced with a threshold and a model-compatibility predicate, and carries neither
    `piece_type` nor `style_tags` — the two attributes the substitutes ordering and its
    signals are built on. Widening `SearchHit` to serve both would put four fields nobody
    reads on every row of the product path.

    It satisfies `filters.Constrained` (`price`, `size_label`, `materials`, `qty_bucket`) so
    that `business_score` can be reused unchanged rather than re-derived.
    """

    product_id: UUID
    sku: str
    distance: float
    materials: list[str]
    style_tags: list[str]
    family_id: UUID | None
    variant_label: str | None
    piece_type: str | None
    size_label: str | None
    price_band: str | None = None
    #: Carried for `business_score` and **never** emitted, exactly as on `SearchHit`: .NET
    #: owns price, and a stale projection may reorder a candidate but never delete it.
    price: float | None = None
    #: The projection bucket at the reading point of sale. `None` means the row was not read
    #: — no reading scope, or this point of sale does not carry the product — and absence is
    #: NOT a bucket of zero: no ordering rule may demote on it.
    qty_bucket: str | None = None
    #: The drain's own 30-day figure. `None` is absence and never a zero, as above.
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

    async def scope_buckets(self, pos_id: UUID) -> dict[str, str]:
        """Availability bucket per product for one assortment. Read by the evaluation only.

        The operational metric needs the bucket of every JUDGED document, not only of the
        ones a configuration retrieved, and the response carries no quantity by design — so
        the harness reads the projection rather than inferring it from what came back.
        """
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

    async def source_document(self, product_id: UUID) -> SourceDocument | None:
        """The reference product of a substitutes request, or `None` when no row exists. C26.

        Absence is a RESULT and not an exception, and so are `is_active` and `has_embedding`:
        the three unusable cases — unknown, inactive, unindexed — are one HTTP error each,
        and which sentence a caller writes is not a decision the SQL layer gets to make.
        """
        ...

    async def neighbours_of(
        self,
        product_id: UUID,
        *,
        piece_type: str | None,
        depth: int,
        exclude_product_ids: Sequence[UUID] = (),
        signal_pos_id: UUID | None = None,
    ) -> list[NeighbourHit]:
        """Nearest neighbours of a STORED embedding. No provider is called. C26.

        Three predicates remove a candidate and there is no fourth: the hard filter on
        `piece_type`, the source product itself, and whatever the body listed in
        `exclude_product_ids`. A ring is not a second-best pendant, and the piece type is an
        attribute of the indexed catalogue rather than a projection that goes stale, so
        removing on it carries none of the risk that removing on availability would.

        **There is no `pos_id` parameter here, and its absence is the decision.** On the
        product path `pos_id` RESTRICTS and `signal_pos_id` only READS; substitutes offer
        only the second, because availability degrades a candidate and never eliminates it —
        the projection can lag minutes behind the counter, and a page that hid what the shop
        can actually sell would be worse than one that ranks it last. The exclusion by stock
        belongs to .NET, which owns the stock (C34).
        """
        ...
