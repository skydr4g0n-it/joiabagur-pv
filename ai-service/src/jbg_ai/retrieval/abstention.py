"""Whether the catalogue can answer this query at all. Delivered by C25.

**The form of this rule was chosen by a measurement, under a criterion written before the
measurement was taken.** D11 of the change design fixed the two candidate forms and the rule
for selecting between them on 2026-09-11, before the distribution was inspected:

    a scalar bound on the best distance, if and only if  max(answerable) < min(out-of-domain)
    a relative rule per query, in every other case

Measured over the 48 judged queries, the best hit of the answerable ones reaches **0,7118**
while the out-of-domain ones start at **0,4469**. That is not a partial overlap: the whole
out-of-domain range sits **inside** the answerable one. A scalar cannot separate them because
there is nothing to separate — silencing all five out-of-domain queries would silence
**19 of the 43** answerable ones. So the relative form was selected, and with it the phase:
this rule runs **after** the fusion and **does not alter the candidate set**, which is what
lets the calibration re-score persisted windows.

**What the relative rule reads is the SHAPE of the distance profile, not its level.** An
answerable query has a peak — something stands out. An out-of-domain query is flat: everything
is equally mediocre, because the catalogue has nothing that answers it and the nearest pieces
are near in the way any piece is near. Measured, the median `d1/d10` is 0,877 for answerable
queries and 0,963 for out-of-domain ones.

    abstain  <=>  |{ d : d <= d_min * (1 + alpha) }| >= min_candidates

At the same out-of-domain capture, this costs **four times less** than the scalar: catching
three of the five costs 4 answerable queries instead of 17.

**It ships disabled, and that is not caution.** Its two parameters cannot be fixed credibly
against **five** out-of-domain queries — fitting two numbers to five points is what this change
has refused to do everywhere else — so they are fixed once the category grows to 15-20, which
costs no per-document labelling because every document is grade zero there by the annotation
criterion. Until then the rule is implemented, measured and published, and it decides nothing.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

logger = logging.getLogger(__name__)

#: What the log calls this stage. Named so the report and the code cannot drift.
STAGE = "abstain"


@dataclass(frozen=True)
class AbstentionRule:
    """The relative rule and its two parameters. Disabled is a value, not a missing one."""

    enabled: bool = False
    #: Half-width of the band around the best distance, as a fraction of it.
    band_alpha: float = 0.05
    #: How many candidates must fall inside that band before the profile counts as flat.
    min_candidates: int = 10

    def describe(self) -> str:
        if not self.enabled:
            return "disabled"
        return f"band(alpha={self.band_alpha:g},n>={self.min_candidates})"


def candidates_in_band(distances: Sequence[float], alpha: float) -> int:
    """How many candidates sit within `d_min * (1 + alpha)`. The flatness of the profile.

    Returns zero for an empty list rather than raising: a query the vector branch answered
    with nothing is not a flat profile, it is an absent one, and the caller decides what that
    means. Conflating the two is how an abstention comes to stand in for a failure.
    """
    if not distances:
        return 0
    best = min(distances)
    if best <= 0:
        # An exact match on the query vector. Nothing is flatter than a perfect hit, and
        # scaling zero by anything leaves zero, so the band would admit only exact ties.
        return sum(1 for value in distances if value <= 0)
    limit = best * (1.0 + alpha)
    return sum(1 for value in distances if value <= limit)


def should_abstain(distances: Sequence[float], rule: AbstentionRule) -> bool:
    """Does the catalogue have nothing that answers this query?

    A decision about the QUERY, applied to the whole response. It never removes candidates one
    by one: an abstention produced by filtering would be indistinguishable from a retrieval
    that simply found little, and the two call for different things from the operator.
    """
    if not rule.enabled or not distances:
        return False
    return candidates_in_band(distances, rule.band_alpha) >= rule.min_candidates


def log_decision(
    *,
    trace_id: str,
    rule: AbstentionRule,
    distances: Sequence[float],
    abstained: bool,
) -> None:
    """The stage's observability: the rule, the best distance observed, and the decision.

    No embedding vector reaches this entry, and none can: the stage receives distances, which
    are scalars, and never the vectors that produced them.
    """
    best = min(distances) if distances else None
    logger.info(
        "stage=%s trace_id=%s rule=%s best_distance=%s in_band=%s candidates=%s decision=%s",
        STAGE,
        trace_id,
        rule.describe(),
        "none" if best is None else f"{best:.4f}",
        candidates_in_band(distances, rule.band_alpha) if distances else 0,
        len(distances),
        "abstain" if abstained else "answer",
        extra={"trace_id": trace_id},
    )
