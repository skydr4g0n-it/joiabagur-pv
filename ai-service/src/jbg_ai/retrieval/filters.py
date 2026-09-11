"""Structural constraints read out of the operator's text. Delivered by C21.

One sentence governs this module: **what a human clicked filters; what a rule inferred from
text demotes.** The body filters of `RetrievalFilters` keep excluding, because somebody
selected them in the panel. A price ceiling, a size or a material *guessed* from a sentence
reorders and never removes — the index's price is a projection of the feed and .NET is the
authority, so a stale figure must never delete a valid product before that authority sees it.

Excluding would also buy nothing here. At 1.168 rows a hard filter saves no time; it only
risks removing the best candidate with total confidence and leaving a hole nobody sees. And
`materials && ARRAY[...]` applied hard would delete the 126 documents (10,8 % of the
catalogue) that carry no extracted materials at all — 36 rings out of every silver-ring query.

The lookup is `ExpandedQuery.matched`, which C20 already built: no second mapping from typed
term to vocabulary field is constructed over the same data.

This module is the seam C25 replaces with calibrated weights against the golden set. Doing so
undoes nothing, because a stable block sort is a score with two values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, Sequence, TypeVar

from jbg_ai.enrichment.vocab import fold
from jbg_ai.retrieval.synonyms import ExpandedQuery

MATERIALS_FIELD = "materials"
SIZE_FIELD = "size_label"

#: The bucket that demotes. Binary against everything else, and that is now a MEASURED
#: conclusion rather than a deferral: under the operational gain function both non-zero
#: buckets fall in the same branch and neither loses grade, so no objective function can order
#: them; and measured over the live projection, `1-2` is 191 assigned pairs against `3+`'s
#: 5.431 — 3,4 % of the non-zero ones — so even a function that could would be fitting noise.
#: The two business readings also point in opposite directions at a counter.
OUT_OF_STOCK_BUCKET = "0"


@dataclass(frozen=True)
class BusinessWeights:
    """What the business score is made of. Both values come from configuration. C25.

    Held as a value object rather than two loose floats so that `demote` cannot be called
    with one of them and not the other, and so the "all zero" case — the rollback — is one
    readable predicate instead of a conjunction spelled out at every call site.
    """

    availability: float = 0.0
    rotation: float = 0.0

    @property
    def is_zero(self) -> bool:
        return self.availability == 0.0 and self.rotation == 0.0

#: Ceiling phrases an operator actually types, with the figure captured. Deliberately narrow:
#: a rule that fires on "80" alone would invent a constraint out of a reference number.
_PRICE_CEILING = re.compile(
    r"(?:menos\s+de|por\s+debajo\s+de|no\s+m[aá]s\s+de|hasta|m[aá]x(?:imo)?\.?|bajo)"
    r"\s*(\d+(?:[.,]\d+)?)\s*(?:€|eur\b|euros?\b)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StructuralFilters:
    """What the rules read out of the query. Empty is the normal case and means "no rule fired"."""

    price_ceiling: float | None = None
    size: str | None = None
    materials: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return self.price_ceiling is None and self.size is None and not self.materials

    def describe(self) -> str:
        """Compact rendering for `debug.notes` and the `stage=filters` entry."""
        parts: list[str] = []
        if self.price_ceiling is not None:
            parts.append(f"price_ceiling={self.price_ceiling:g}")
        if self.size is not None:
            parts.append(f"size={self.size}")
        if self.materials:
            parts.append("materials=" + "|".join(self.materials))
        return ",".join(parts) if parts else "none"


class Constrained(Protocol):
    """What demotion needs to read. Anything the fusion produced satisfies it."""

    price: float | None
    size_label: str | None
    materials: list[str]
    #: The projection bucket for the point of sale, or `None` when no reading scope was
    #: applied or this point of sale does not carry the product.
    qty_bucket: str | None
    #: The 30-day sales window from the same projection row, counted against that row's own
    #: `computed_as_of`. `None` is absence and never a zero.
    sales_30d: int | None


ConstrainedT = TypeVar("ConstrainedT", bound=Constrained)


def extract_filters(expanded: ExpandedQuery) -> StructuralFilters:
    """Read a ceiling, a size and materials out of the query. Never invents one."""
    materials = tuple(
        item.canonical for item in expanded.matched if item.field == MATERIALS_FIELD
    )
    size = next(
        (item.canonical for item in expanded.matched if item.field == SIZE_FIELD),
        None,
    )
    return StructuralFilters(
        price_ceiling=_price_ceiling(expanded.original),
        size=size,
        materials=materials,
    )


def _price_ceiling(text: str) -> float | None:
    match = _PRICE_CEILING.search(text)
    if match is None:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:  # pragma: no cover - the group is \d+ with one optional separator
        return None


def _over_ceiling(item: Constrained, ceiling: float | None) -> bool:
    """An unknown price never demotes: absence of a projection is not evidence of a price."""
    return ceiling is not None and item.price is not None and item.price > ceiling


def _size_mismatch(item: Constrained, size: str | None) -> bool:
    """`Talla:` covers 45 % of the corpus, so an untagged piece is not a mismatch."""
    if size is None or item.size_label is None:
        return False
    return fold(item.size_label) != fold(size)


def _material_mismatch(item: Constrained, materials: Sequence[str]) -> bool:
    """Overlap, never containment: `@>` reaches 60 documents where `&&` reaches 913.

    A document with no extracted materials at all is never a mismatch: there are 126 of them
    and they are ordinary pieces the feed did not describe, not pieces made of nothing.
    """
    if not materials or not item.materials:
        return False
    wanted = {fold(value) for value in materials}
    held = {fold(value) for value in item.materials}
    return not (wanted & held)


def _out_of_stock(item: Constrained) -> bool:
    """Zero stock at this point of sale, as the projection reports it.

    `None` is not zero. It means the query ran unscoped, so there is no projection row to
    read, and an absent signal must not demote anything — the same rule an unknown price
    already follows two blocks up.
    """
    return item.qty_bucket == OUT_OF_STOCK_BUCKET


def business_score(item: Constrained, weights: BusinessWeights) -> float:
    """The continuous score that orders the tail block. Higher is better. C25 D9.

    Two terms, both binary, and neither invents a value for an absent signal:

    * **availability** costs its weight when the projection reports `qty_bucket` of zero.
      An ABSENT row costs nothing — no reading scope, or a product this point of sale does
      not carry — because absence is not evidence of zero stock.
    * **rotation** pays its weight when the window records a sale. It is binary, not
      proportional to the count, because the sentence that justifies it is about a tiebreak:
      "between two pieces the retriever and the stock rank equally, show the one that sells".
      No sentence justifies a piece that sold forty outranking one that sold four, and a
      weight with no hypothesis behind it fits the noise of 48 queries.

    Rotation cannot overturn availability, and that is structural rather than hoped for: the
    settings refuse a rotation weight that is not strictly below the availability one, so the
    most rotation can ever add is less than what zero stock costs.
    """
    score = 0.0
    if _out_of_stock(item):
        score -= weights.availability
    if item.sales_30d is not None and item.sales_30d > 0:
        score += weights.rotation
    return score


def demotion_rank(
    item: Constrained,
    filters: StructuralFilters,
    weights: BusinessWeights | None = None,
) -> tuple[int, int, int, float]:
    """The block a candidate falls into. Lower is better; equal blocks keep the fused order.

    Three integer blocks read out of the operator's own text, then **one continuous score in
    the tail**. The shape is the decision: what the operator typed keeps strict lexicographic
    precedence over a signal they did not ask about, so no amount of stock or rotation can
    lift a candidate over a price ceiling the operator expressed.

    Before C25 the fourth component was a fourth integer. Making it continuous loses nothing —
    a stable block sort is a score with two values — and it bounds the blast radius of the
    magic numbers: the weights live in one term at the end of the key, not spread across six
    coupled components where nobody can say why a document came third.

    The tail is negated because the key sorts ascending and a higher business score is better.
    """
    weights = weights or BusinessWeights()
    return (
        int(_over_ceiling(item, filters.price_ceiling)),
        int(_size_mismatch(item, filters.size)),
        int(_material_mismatch(item, filters.materials)),
        -business_score(item, weights),
    )


def demote(
    candidates: Sequence[ConstrainedT],
    filters: StructuralFilters,
    weights: BusinessWeights | None = None,
) -> tuple[tuple[ConstrainedT, ...], int]:
    """Stable block sort. Returns the reordered candidates and how many were demoted.

    Nothing is removed: `sorted` is stable, so the fused order survives inside each block and
    every candidate stays inside the over-retrieval window the caller returns. That is what
    makes availability a demotion and not a filter — a zero-stock product still reaches the
    operator, ranked below its in-stock peers, exactly as it does today with `HasStock: false`
    on the .NET side.

    The early return is on "nothing to demote by": no typed constraint fired **and** every
    business score is zero — either because the weights are zero, which is the rollback, or
    because no candidate carries a signal that moves one. It is kept because it is the
    majority case, and it is what makes the tail block the whole list where it matters.

    Zero weights reproduce exactly the ordering the fusion and the typed blocks produce alone.
    """
    weights = weights or BusinessWeights()
    scores = [business_score(item, weights) for item in candidates]
    if filters.is_empty and not any(scores):
        return tuple(candidates), 0
    demoted = sum(
        1
        for item, score in zip(candidates, scores, strict=True)
        if any(demotion_rank(item, filters)[:3]) or score < 0
    )
    return (
        tuple(sorted(candidates, key=lambda item: demotion_rank(item, filters, weights))),
        demoted,
    )
