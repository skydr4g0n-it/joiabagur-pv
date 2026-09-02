"""Weighted Reciprocal Rank Fusion over N ranked lists. Delivered by C21.

Pure and domain-free on purpose: C23 (knowledge corpus), C25 (business signals) and C26
(substitutes) fuse ranked lists **without going through `POST /v1/retrieval/products`**, and
they import this module rather than restating it. Nothing here opens a session, calls a
provider or knows what a product, a material or a word is — it sees ordered identifiers and
weights, and nothing else.

`score(d) = sum over lists i of w_i / (k + rank_i(d))`, with `rank` one-based.

**Raw branch scores are never read.** The cosine distance and `ts_rank` live on incomparable
scales whose distributions move per query, and normalising them is the swamp RRF exists to
avoid. Weighting *rank reciprocals* is a different operation from weighting raw scores: it is
dimensionless, so a weight does not calibrate a scale — it declares how many votes a branch
holds. The two look alike, which is why the distinction is written down.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

# `k` and `depth` are **required arguments with no default here**, deliberately. The spec says
# the weights and the smoothing constant are read from settings and are not written into the
# code, and a module-level default is exactly how a value gets written into the code without
# anybody deciding to: it would be picked up silently by the next importer. `config.settings`
# owns the measured figures (`FUSION_DEFAULTS`), and every caller passes them.
#
# What belongs here is the *rule*, not the number. `k` smooths the reciprocal so the leader
# does not dominate: at k = 60 rank 1 scores 1/61 and rank 200 still scores 1/260, which is
# 38 % of the leader's vote. Depth is therefore coupled to k rather than swept independently,
# because a list far longer than k hands positive votes to candidates the other lists do not
# score at all, and that tail displaces the candidates two lists rank well without ranking
# first. Measured: depth 40 -> 113/120, 60 -> 111, 100 -> 107, 200 -> 107, and an asymmetric
# 200 lexical / 60 vector -> 105. Rule: **depth is of the order of k**, and they are swept
# together or not at all.


@dataclass(frozen=True)
class RankedList:
    """One branch's opinion: identifiers in order, plus how many votes the branch holds."""

    name: str
    weight: float
    keys: Sequence[Hashable]


@dataclass(frozen=True)
class FusedCandidate:
    """A candidate and its provenance: which lists placed it, and where."""

    key: Hashable
    score: float
    ranks: Mapping[str, int]

    @property
    def lists(self) -> tuple[str, ...]:
        return tuple(self.ranks)

    @property
    def list_count(self) -> int:
        return len(self.ranks)


def truncate(keys: Iterable[Hashable], *, depth: int) -> tuple[Hashable, ...]:
    """First `depth` distinct keys, order preserved. Every list is cut at the same point."""
    seen: set[Hashable] = set()
    out: list[Hashable] = []
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
        if len(out) >= depth:
            break
    return tuple(out)


def fuse(
    lists: Sequence[RankedList],
    *,
    k: int,
    depth: int,
) -> tuple[FusedCandidate, ...]:
    """Fuse the lists and return the candidates in descending fused score.

    Every list is truncated at `depth` **before** fusing, so membership of some top-N is the
    entry requirement — which is where RRF's consensus premium bites. Ties keep the order in
    which candidates were first seen, so the result is deterministic.
    """
    scores: dict[Hashable, float] = {}
    ranks: dict[Hashable, dict[str, int]] = {}
    order: dict[Hashable, int] = {}

    for ranked in lists:
        for position, key in enumerate(truncate(ranked.keys, depth=depth), start=1):
            scores[key] = scores.get(key, 0.0) + ranked.weight / (k + position)
            ranks.setdefault(key, {})[ranked.name] = position
            order.setdefault(key, len(order))

    return tuple(
        FusedCandidate(
            key=key,
            score=scores[key],
            ranks=MappingProxyType(dict(ranks[key])),
        )
        for key in sorted(scores, key=lambda item: (-scores[item], order[item]))
    )


def normalised_scores(fused: Sequence[FusedCandidate]) -> tuple[float, ...]:
    """Scale the fused scores so the first is 1.0, staying inside [0, 1] and non-increasing.

    Raw RRF scores are 0,0001-0,03 numbers with no meaning outside one query, and the .NET
    side persists `score` as telemetry: storing them would look like a broken field.
    """
    if not fused:
        return ()
    top = fused[0].score
    if top <= 0:
        return tuple(0.0 for _ in fused)
    return tuple(min(max(item.score / top, 0.0), 1.0) for item in fused)
