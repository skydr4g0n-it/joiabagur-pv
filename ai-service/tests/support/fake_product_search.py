"""In-memory product search port. No sockets, no RDS. Delivered by C14, extended by C21 and C22."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from jbg_ai.enrichment.vocab import fold
from jbg_ai.retrieval.lexical import LexicalRequest
from jbg_ai.retrieval.ports import LexicalHit, SearchFilters, SearchHit

#: What an unspecified projection means here: this point of sale carries the whole indexed
#: set, in stock. A legitimate world state, and the one that leaves a test about fusion or
#: about the lexical branch saying what it says without also having to describe an assortment.
#: A test about the scope passes `assignments` explicitly.
DEFAULT_BUCKET = "3+"

#: Stand-in for `numnode(plainto_tsquery('spanish', term)) > 0`, which is what the statement
#: actually asks. These are the Spanish stop words the golden set's queries actually contain,
#: and they are the whole reason the coverage denominator exists: `plainto_tsquery('spanish',
#: 'de')` is an EMPTY tsquery, so that group can never match any document, and counting it
#: would lower the coverage of a query that is in fact fully anchored.
#:
#: A stand-in and not a reimplementation: the real predicate is PostgreSQL's, and the C25
#: implementation report records it verified against the live index query by query. What this
#: buys is that a test about coverage can run with no database at all.
EMPTY_TSQUERY_FORMS = frozenset(
    {"de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas",
     "y", "o", "que", "en", "a", "al", "con", "para", "se", "lo", "su", "sus"}
)


@dataclass
class FakeAssignment:
    """One row of `ai.pos_projection`. `is_assigned_hint=False` is the soft delete."""

    pos_id: UUID
    product_id: UUID
    qty_bucket: str = DEFAULT_BUCKET
    is_assigned_hint: bool = True
    #: The drain's 30-day figure for this pair, counted against the row's own reference
    #: instant. Zero is a real value — "carried here, sold none" — and is a different thing
    #: from the absence a product this point of sale does not carry reports.
    sales_30d: int = 0


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
        assignments: list[FakeAssignment] | None = None,
        synced_at: datetime | None = None,
        never_synchronised: bool = False,
    ) -> None:
        self.rows = list(rows or [])
        self.compatible_count_override = compatible_count
        #: `None` means "no projection was described", which the helpers below read as the
        #: whole catalogue being carried. An empty list is a different thing entirely: a
        #: point of sale that carries nothing, which is the 503 case.
        self.assignments = None if assignments is None else list(assignments)
        self.synced_at = (
            None if never_synchronised else (synced_at or datetime.now(tz=UTC))
        )
        self.count_calls: list[tuple[str, str]] = []
        self.search_calls: list[dict[str, object]] = []
        self.lexical_calls: list[dict[str, object]] = []
        self.scope_calls: list[UUID] = []
        self.synced_at_calls = 0

    def _scope(self, pos_id: UUID) -> dict[UUID, FakeAssignment]:
        """What this point of sale actually carries, by product identifier."""
        if self.assignments is None:
            return {
                row.product_id: FakeAssignment(pos_id=pos_id, product_id=row.product_id)
                for row in self.rows
            }
        return {
            item.product_id: item
            for item in self.assignments
            if item.pos_id == pos_id and item.is_assigned_hint
        }

    def _scopes(
        self, pos_id: UUID | None, signal_pos_id: UUID | None
    ) -> tuple[dict[UUID, FakeAssignment] | None, dict[UUID, FakeAssignment] | None]:
        """The restricting scope and the reading one, mirroring the two joins of the SQL.

        `None` for the restricting one means no candidate is removed; `None` for the reading
        one means no signal is read at all, which is what leaves both signals absent. A
        restricting scope reads too: in SQL the rows are joined already.
        """
        if pos_id is not None:
            scope = self._scope(pos_id)
            return scope, scope
        if signal_pos_id is not None:
            return None, self._scope(signal_pos_id)
        return None, None

    @staticmethod
    def _bucket(reading: dict[UUID, "FakeAssignment"] | None, product_id: UUID) -> str | None:
        if reading is None:
            return None
        row = reading.get(product_id)
        return None if row is None else row.qty_bucket

    @staticmethod
    def _sales(reading: dict[UUID, "FakeAssignment"] | None, product_id: UUID) -> int | None:
        """Absent when the row is not read or not carried. Absence is never a zero."""
        if reading is None:
            return None
        row = reading.get(product_id)
        return None if row is None else row.sales_30d

    async def count_scope(self, pos_id: UUID) -> int:
        self.scope_calls.append(pos_id)
        return len(self._scope(pos_id))

    async def projection_synced_at(self) -> datetime | None:
        self.synced_at_calls += 1
        return self.synced_at

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
        pos_id: UUID | None = None,
        signal_pos_id: UUID | None = None,
    ) -> list[SearchHit]:
        self.search_calls.append(
            {
                "query_vec": list(query_vec),
                "threshold": threshold,
                "depth": depth,
                "filters": filters,
                "model_version_key": model_version_key,
                "model_id": model_id,
                "pos_id": pos_id,
                "signal_pos_id": signal_pos_id,
            }
        )
        restricting, reading = self._scopes(pos_id, signal_pos_id)
        hits: list[SearchHit] = []
        for row in self.rows:
            if not row.is_active or not row.has_embedding or not row.compatible:
                continue
            if row.distance > threshold:
                continue
            if not self._passes_body_filters(row, filters):
                continue
            if restricting is not None and row.product_id not in restricting:
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
                    qty_bucket=self._bucket(reading, row.product_id),
                    sales_30d=self._sales(reading, row.product_id),
                )
            )
        # Mirrors `_SEARCH_ORDER_LIMIT` key for key, including the `product_id` tiebreak:
        # a fake that truncated under a weaker order than the statement would let a test
        # about truncation pass while the real branch cut arbitrarily. `UUID` compares by
        # its 128-bit value, which is the byte order PostgreSQL uses for `uuid`.
        hits.sort(key=lambda item: (item.distance, item.product_id))
        return hits[:depth]

    async def search_lexical(
        self,
        request: LexicalRequest,
        *,
        depth: int,
        filters: SearchFilters,
        pos_id: UUID | None = None,
        signal_pos_id: UUID | None = None,
    ) -> list[LexicalHit]:
        self.lexical_calls.append(
            {
                "request": request,
                "depth": depth,
                "filters": filters,
                "pos_id": pos_id,
                "signal_pos_id": signal_pos_id,
            }
        )
        groups = request.groups or ((request.text,),)
        counting = request.counting or tuple(True for _ in groups)
        restricting, reading = self._scopes(pos_id, signal_pos_id)

        hits: list[LexicalHit] = []
        for row in self.rows:
            if not row.is_active:
                continue
            if not self._passes_body_filters(row, filters):
                continue
            if restricting is not None and row.product_id not in restricting:
                continue
            matched = [self._group_matches(row, group) for group in groups]
            if not any(matched):
                continue
            coordination = sum(
                1
                for hit, counts in zip(matched, counting, strict=False)
                if hit and counts
            )
            coverage_denominator = sum(
                1
                for group, counts in zip(groups, counting, strict=False)
                if counts and self._group_is_expressible(group)
            )
            hits.append(
                LexicalHit(
                    product_id=row.product_id,
                    sku=row.sku,
                    ts_rank=sum(matched) / len(matched),
                    coordination=coordination,
                    coverage_denominator=coverage_denominator,
                    materials=list(row.materials),
                    family_id=row.family_id,
                    variant_label=row.variant_label,
                    price=row.price,
                    size_label=row.size_label,
                    qty_bucket=self._bucket(reading, row.product_id),
                    sales_30d=self._sales(reading, row.product_id),
                )
            )
        # Same reason as the vector branch, and the same final key as the statement. It is
        # `product_id` and not `sku` because the statement has no `sku` key: a fake ordering
        # by something the SQL never mentions is a fake that cannot witness the property.
        hits.sort(key=lambda item: (-item.coordination, -item.ts_rank, item.product_id))
        return hits[:depth]

    @staticmethod
    def _group_is_expressible(group: tuple[str, ...]) -> bool:
        """Could this group's tsquery match ANY document? Mirrors `numnode(...) > 0`."""
        return any(
            form.strip() and fold(form) not in EMPTY_TSQUERY_FORMS for form in group
        )

    @staticmethod
    def _group_matches(row: FakeIndexedRow, group: tuple[str, ...]) -> bool:
        haystack = fold(row.doc_text)
        return any(fold(form) in haystack for form in group if form.strip())
