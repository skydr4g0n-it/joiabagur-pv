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

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.retrieval.errors import RetrievalDependencyError
from jbg_ai.retrieval.lexical import LexicalRequest, build_fragments
from jbg_ai.retrieval.ports import (
    LexicalHit,
    NeighbourHit,
    SearchFilters,
    SearchHit,
    SourceDocument,
)

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

# The availability of a whole assortment in one statement. Read by the EVALUATION and never
# by the request path: the operational metric needs the bucket of every judged document, and
# the response deliberately carries no quantity, so the harness reads the projection itself.
# One round trip per run rather than one per query, over a table of 6.720 rows.
SCOPE_BUCKETS_SQL = """
SELECT product_id, qty_bucket
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

# One CTE, two uses, and the difference between them is the join and nothing else. C25 D4.
#
#   scope_pos_id   ->  JOIN       restricts the universe   (the C22 prefilter)
#   signal_pos_id  ->  LEFT JOIN  only reads               (the C25 business signals)
#
# Splitting them is what lets the reordering by availability be measured WITHOUT paying the
# recall cost of the prefilter — the confusion C22 declined to introduce and declared unmeasured.
# `sales_30d` joins the selection here because it is the drain's own figure, already counted
# against the `computed_as_of` recorded on that row; reading it costs nothing extra.
_SCOPE_CTE = """
WITH scope AS MATERIALIZED (
  SELECT product_id, qty_bucket, sales_30d
  FROM ai.pos_projection
  WHERE pos_id = :pos_id
    AND is_assigned_hint IS TRUE
)
"""

_SCOPE_JOIN = "JOIN scope s ON s.product_id = d.product_id"
_SIGNAL_JOIN = "LEFT JOIN scope s ON s.product_id = d.product_id"

_SEARCH_SELECT = """SELECT
  d.product_id,
  d.sku,
  (d.embedding <=> CAST(:q AS vector)) AS distance,
  d.materials,
  d.family_id,
  d.variant_label,
  d.price,
  d.size_label,
  {qty_bucket},
  {sales_30d}
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

# `d.product_id` last is a TIEBREAK, never a ranking signal: it only decides between rows the
# preceding key has already declared equal. Without it the ordering is not a total order and
# `LIMIT` cuts inside a tie, so which rows survive is whatever the plan happened to produce —
# undefined in PostgreSQL, and enough to make two identical runs disagree. That is fatal to an
# evaluation harness, whose whole job is to attribute a moved metric to a change rather than to
# chance, and it is why C24 touches the live path at all.
_SEARCH_ORDER_LIMIT = """
ORDER BY d.embedding <=> CAST(:q AS vector) ASC, d.product_id ASC
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
  ({coverage_denominator}) AS coverage_denominator,
  d.materials,
  d.family_id,
  d.variant_label,
  d.price,
  d.size_label,
  {qty_bucket},
  {sales_30d}
FROM ai.product_document d
{scope_join}
WHERE d.is_active IS TRUE
  AND d.tsv @@ {match}
"""

# Same tiebreak, and the branch that needs it most: `coordination` takes a handful of values by
# construction and `ts_rank` repeats across documents matching the same fields, so ties here are
# the norm rather than the exception. The fusion consumes rank POSITIONS, so an undefined order
# inside a tie does not stay local — it propagates into the fused list and from there into every
# metric taken over it.
_LEXICAL_ORDER_LIMIT = """
ORDER BY coordination DESC, ts_rank DESC, d.product_id ASC
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


def _scoped(head: str, *, restricts: bool, reads: bool) -> str:
    """Fill the three holes the scope opens: the bucket, the sales window, and the join.

    `restricts` and `reads` are independent, and only one join is ever emitted because both
    read the same CTE. A restricting scope also reads — the rows are joined already — so the
    caller never has to ask for both in order to get both.
    """
    joined = restricts or reads
    return head.format(
        qty_bucket="s.qty_bucket" if joined else "NULL AS qty_bucket",
        sales_30d="s.sales_30d" if joined else "NULL AS sales_30d",
        scope_join=(_SCOPE_JOIN if restricts else _SIGNAL_JOIN) if joined else "",
    )


def _with_filters(
    head: str, filters: SearchFilters, tail: str, *, restricts: bool, reads: bool
) -> str:
    extra = _body_filter_clauses(filters)
    extra_sql = ("\n  " + "\n  ".join(extra) + "\n") if extra else "\n"
    cte = _SCOPE_CTE if (restricts or reads) else ""
    return cte + _scoped(head, restricts=restricts, reads=reads) + extra_sql + tail


def compile_search_sql(
    filters: SearchFilters, *, restricts: bool = False, reads: bool = False
) -> str:
    """Return the vector statement. Restricts by `pos_id` only when asked; never by price."""
    return _with_filters(
        _SEARCH_SELECT, filters, _SEARCH_ORDER_LIMIT, restricts=restricts, reads=reads
    )


def compile_lexical_sql(
    request: LexicalRequest,
    filters: SearchFilters,
    *,
    restricts: bool = False,
    reads: bool = False,
) -> tuple[str, dict]:
    """Return the lexical statement and its bound terms. Never filters by price or stock."""
    fragments = build_fragments(request, placeholder=lambda name: f":{name}")
    head = (
        _LEXICAL_SELECT.replace("{match}", fragments.match)
        .replace("{coordination}", fragments.coordination)
        # Constant per query and therefore evaluated once by the planner, not per row. It
        # rides along on the statement that already tallies the coordination precisely so
        # that measuring coverage costs no extra trip through a pool capped at five.
        .replace("{coverage_denominator}", fragments.coverage_denominator)
    )
    return (
        _with_filters(
            head, filters, _LEXICAL_ORDER_LIMIT, restricts=restricts, reads=reads
        ),
        dict(fragments.params),
    )


# ---------------------------------------------------------------------------------------
# C26 substitutes. Product -> product, so the anchor is a STORED embedding and no provider
# is called: the vector the k-NN ranks against is read from the source row inside the same
# statement. That is also why there is no `threshold` and no model-compatibility predicate
# here — both belong to a query the provider just embedded, and there is no query.
# ---------------------------------------------------------------------------------------

SOURCE_DOCUMENT_SQL = """
SELECT
  d.product_id,
  d.sku,
  d.piece_type,
  d.size_label,
  d.materials,
  d.style_tags,
  d.family_id,
  d.price_band,
  d.is_active,
  (d.embedding IS NOT NULL) AS has_embedding
FROM ai.product_document d
WHERE d.product_id = :source_id
"""

# An UNCORRELATED scalar subquery on the primary key, written once and substituted into both
# the projection and the ordering. The planner lifts it to an InitPlan and evaluates it once,
# so the distance operator sees a constant on the right — the shape an index scan needs —
# rather than a per-row lookup. Binding the vector from Python instead would ship 1.536
# floats across the wire twice to say what the row already says.
_SOURCE_EMBEDDING = (
    "(SELECT src.embedding FROM ai.product_document src WHERE src.product_id = :source_id)"
)

# `piece_type` is the ONLY hard filter, and `IS NOT DISTINCT FROM` rather than `=` because
# one live document carries none: with `=` a null source type would match nothing through an
# unknown comparison, silently, which is the failure mode this module opens by describing.
# Null matches null, so an untyped source is offered untyped candidates and never a ring.
#
# Availability is absent from this WHERE clause on purpose and the join below is the reason.
_NEIGHBOURS_SELECT = """SELECT
  d.product_id,
  d.sku,
  (d.embedding <=> {source_embedding}) AS distance,
  d.materials,
  d.style_tags,
  d.family_id,
  d.variant_label,
  d.piece_type,
  d.size_label,
  d.price_band,
  d.price,
  {qty_bucket},
  {sales_30d}
FROM ai.product_document d
{scope_join}
WHERE d.embedding IS NOT NULL
  AND d.is_active IS TRUE
  AND d.product_id <> :source_id
  AND d.piece_type IS NOT DISTINCT FROM :piece_type
"""

# The same deterministic tiebreak C24 put on every other statement, and for the same reason:
# without it the ordering is not a total order, `LIMIT` cuts inside a tie, and which rows
# survive is whatever the plan produced. Two identical runs would then disagree, which is
# fatal to a harness whose job is to attribute a moved metric to a change rather than to luck.
_NEIGHBOURS_ORDER_LIMIT = """
ORDER BY d.embedding <=> {source_embedding} ASC, d.product_id ASC
LIMIT :depth
"""


def compile_neighbours_sql(
    *, reads: bool = False, exclude_product_ids: bool = False
) -> str:
    """Return the substitutes k-NN statement.

    `reads` attaches the projection through `_SIGNAL_JOIN` — a `LEFT JOIN`, never
    `_SCOPE_JOIN`. The restricting join has no caller here and must not acquire one: in
    substitutes the availability of a candidate demotes it and never removes it, so a
    candidate this point of sale does not carry still has to come back. Excluding on stock
    is C34's, on the .NET side, which is where the authority over stock lives.
    """
    cte = _SCOPE_CTE if reads else ""
    extra = (
        "  AND d.product_id <> ALL(CAST(:exclude_ids AS uuid[]))\n"
        if exclude_product_ids
        else ""
    )
    # `{source_embedding}` is substituted BEFORE `_scoped`, which runs `str.format` over its
    # own three holes and would raise on a fourth it does not know. Same order as
    # `compile_lexical_sql`, which fills its fragments before handing the head on.
    head = _scoped(
        _NEIGHBOURS_SELECT.replace("{source_embedding}", _SOURCE_EMBEDDING),
        restricts=False,
        reads=reads,
    )
    return (
        cte
        + head
        + extra
        + _NEIGHBOURS_ORDER_LIMIT.replace("{source_embedding}", _SOURCE_EMBEDDING)
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


def _optional_int(value: object) -> int | None:
    """`None` stays `None`: an absent projection row is not a row reporting zero sales."""
    return None if value is None else int(value)


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

    async def scope_buckets(self, pos_id: UUID) -> dict[str, str]:
        """Product identifier to availability bucket, for one point of sale's assortment."""
        try:
            async with session_scope(self._settings) as session:
                rows = (
                    await session.execute(text(SCOPE_BUCKETS_SQL), {"pos_id": pos_id})
                ).mappings().all()
        except SQLAlchemyError as exc:
            raise RetrievalDependencyError(f"database query failed: {exc}") from exc
        return {str(row["product_id"]): str(row["qty_bucket"]) for row in rows}

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
        signal_pos_id: UUID | None = None,
    ) -> list[SearchHit]:
        params: dict[str, object] = {
            "q": _vector_literal(query_vec),
            "threshold": threshold,
            "depth": depth,
            "version_prefix": f"{model_version_key}%",
            "model_id": model_id,
            **_body_filter_params(filters),
        }
        # One bound `pos_id`, because one CTE serves both uses. The restricting scope wins
        # when both are supplied: its join is the stricter of the two and already reads.
        scope_pos_id = pos_id if pos_id is not None else signal_pos_id
        if scope_pos_id is not None:
            params["pos_id"] = scope_pos_id

        sql = compile_search_sql(
            filters, restricts=pos_id is not None, reads=signal_pos_id is not None
        )
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
                sales_30d=_optional_int(row["sales_30d"]),
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
        signal_pos_id: UUID | None = None,
    ) -> list[LexicalHit]:
        sql, terms = compile_lexical_sql(
            request,
            filters,
            restricts=pos_id is not None,
            reads=signal_pos_id is not None,
        )
        params: dict[str, object] = {
            "depth": depth,
            **terms,
            **_body_filter_params(filters),
        }
        scope_pos_id = pos_id if pos_id is not None else signal_pos_id
        if scope_pos_id is not None:
            params["pos_id"] = scope_pos_id
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
                coverage_denominator=int(row["coverage_denominator"] or 0),
                materials=_materials_list(row["materials"]),
                family_id=_optional_uuid(row["family_id"]),
                variant_label=_optional_str(row["variant_label"]),
                price=_optional_float(row["price"]),
                size_label=_optional_str(row["size_label"]),
                qty_bucket=_optional_str(row["qty_bucket"]),
                sales_30d=_optional_int(row["sales_30d"]),
            )
            for row in rows
        ]

    async def source_document(self, product_id: UUID) -> SourceDocument | None:
        """Read the reference product. Absence comes back as `None`, never as an exception."""
        try:
            async with session_scope(self._settings) as session:
                row = (
                    await session.execute(
                        text(SOURCE_DOCUMENT_SQL), {"source_id": product_id}
                    )
                ).mappings().first()
        except SQLAlchemyError as exc:
            raise RetrievalDependencyError(f"database query failed: {exc}") from exc
        if row is None:
            return None
        return SourceDocument(
            product_id=UUID(str(row["product_id"])),
            sku=str(row["sku"]),
            piece_type=_optional_str(row["piece_type"]),
            size_label=_optional_str(row["size_label"]),
            materials=_materials_list(row["materials"]),
            style_tags=_materials_list(row["style_tags"]),
            family_id=_optional_uuid(row["family_id"]),
            price_band=_optional_str(row["price_band"]),
            is_active=bool(row["is_active"]),
            has_embedding=bool(row["has_embedding"]),
        )

    async def neighbours_of(
        self,
        product_id: UUID,
        *,
        piece_type: str | None,
        depth: int,
        exclude_product_ids: Sequence[UUID] = (),
        signal_pos_id: UUID | None = None,
    ) -> list[NeighbourHit]:
        """Neighbours of the stored embedding. One statement, one connection, no provider."""
        params: dict[str, object] = {
            "source_id": product_id,
            "piece_type": piece_type,
            "depth": depth,
        }
        if exclude_product_ids:
            params["exclude_ids"] = [str(item) for item in exclude_product_ids]
        if signal_pos_id is not None:
            params["pos_id"] = signal_pos_id

        sql = compile_neighbours_sql(
            reads=signal_pos_id is not None,
            exclude_product_ids=bool(exclude_product_ids),
        )
        try:
            async with session_scope(self._settings) as session:
                rows = (await session.execute(text(sql), params)).mappings().all()
        except SQLAlchemyError as exc:
            raise RetrievalDependencyError(f"database query failed: {exc}") from exc

        return [
            NeighbourHit(
                product_id=UUID(str(row["product_id"])),
                sku=str(row["sku"]),
                distance=float(row["distance"]),
                materials=_materials_list(row["materials"]),
                style_tags=_materials_list(row["style_tags"]),
                family_id=_optional_uuid(row["family_id"]),
                variant_label=_optional_str(row["variant_label"]),
                piece_type=_optional_str(row["piece_type"]),
                size_label=_optional_str(row["size_label"]),
                price_band=_optional_str(row["price_band"]),
                price=_optional_float(row["price"]),
                qty_bucket=_optional_str(row["qty_bucket"]),
                sales_30d=_optional_int(row["sales_30d"]),
            )
            for row in rows
        ]
