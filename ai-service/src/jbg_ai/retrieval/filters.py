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

#: The bucket that demotes. Binary against everything else on purpose: ordering `1-2` before
#: `3+` would be a magic number with no evidence behind it, and both tiers are persisted and
#: unread until the ranking change that can calibrate them against a golden set.
OUT_OF_STOCK_BUCKET = "0"

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
    #: The projection bucket for the point of sale, or `None` when the query ran unscoped.
    qty_bucket: str | None


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
    return getattr(item, "qty_bucket", None) == OUT_OF_STOCK_BUCKET


def demotion_rank(
    item: Constrained, filters: StructuralFilters
) -> tuple[int, int, int, int]:
    """The block a candidate falls into. Lower is better; equal blocks keep the fused order.

    Availability is the **last** component, and one sort key rather than a second pass. Last
    because what the operator typed outranks a signal they did not ask about: a query for a
    ring under 80 EUR should not be reordered by stock before it is reordered by price. The
    opposite is defensible at a till counter and is not settled by argument here — it is
    handed to the ranking change that has a golden set to settle it with.

    One key rather than two sorts because priority should be readable in the tuple instead of
    emerging from the order in which somebody applied two `sorted` calls.
    """
    return (
        int(_over_ceiling(item, filters.price_ceiling)),
        int(_size_mismatch(item, filters.size)),
        int(_material_mismatch(item, filters.materials)),
        int(_out_of_stock(item)),
    )


def demote(
    candidates: Sequence[ConstrainedT], filters: StructuralFilters
) -> tuple[tuple[ConstrainedT, ...], int]:
    """Stable block sort. Returns the reordered candidates and how many were demoted.

    Nothing is removed: `sorted` is stable, so the fused order survives inside each block and
    every candidate stays inside the over-retrieval window the caller returns. That is what
    makes availability a demotion and not a filter — a zero-stock product still reaches the
    operator, ranked below its in-stock peers, exactly as it does today with `HasStock: false`
    on the .NET side.

    The early return is on "nothing to demote by", which since availability joined the key
    means: no typed constraint fired **and** no candidate is out of stock.
    """
    if filters.is_empty and not any(_out_of_stock(item) for item in candidates):
        return tuple(candidates), 0
    demoted = sum(1 for item in candidates if any(demotion_rank(item, filters)))
    return tuple(sorted(candidates, key=lambda item: demotion_rank(item, filters))), demoted
