"""Relative embedding veto over formed candidates. Delivered by C18a.

The veto answers one question — *does the vector support this membership?* — and
it answers it **relative to the other candidate memberships**, never against a
global cutoff. Measured over the 1200 indexed documents, an absolute threshold
cannot work: the worst-sibling and nearest-stranger populations overlap, and two
synthetic families built to be distinct come within five thousandths of each
other.

The test is therefore comparative. A member is flagged when some product in a
**different proposed family** is closer to it than its own worst sibling, by more
than a configured margin. Two properties make this the right shape:

* **The universe is other family members, not the whole catalogue.** A product
  competing for no membership is not an alternative membership, so it cannot
  vote. Comparing against all 1200 documents flags 16% of members on similarity
  to products that were never candidates for anything.
* **The margin exists because ties are noise.** A stranger beating the worst
  sibling by 0.001 says nothing; by 0.16 it says the grouping is wrong.

A flagged member is **marked, never removed**. A product that shares a root and a
piece type but whose vector disagrees is exactly what a person should look at;
deleting it would hide the disagreement instead of reporting it.

**A note on the numbers, because an earlier one was wrong.** The exploration that
justified this design measured 1.7% of members as overlapping. That figure came
from families formed by the size suffix alone — 24 real families instead of the
68 this package builds — whose members are far more homogeneous. Richer families
carry more internal spread by construction: one grouping `pequeño` with
`pequeño oro` holds genuinely different vectors. On the algorithm actually
shipped, the honest figure at margin 0.05 is **15 of 486 members (3.1%) across 5
families**, and the largest of those five is the family where a synthetic product
drifted into a real one.
"""

from __future__ import annotations

from dataclasses import replace

from jbg_ai.families.grouping import FamilyProposal, ProposedMember

__all__ = ["VETO_REASON", "MemberSimilarity", "apply_relative_veto"]

#: Recorded on a member the veto flagged, so the reason travels with the mark.
VETO_REASON = "closer_to_another_family"


class MemberSimilarity:
    """Per-member extremes the veto needs, as computed by the repository query."""

    __slots__ = ("worst_sibling", "best_stranger", "stranger_family")

    def __init__(
        self,
        worst_sibling: float | None,
        best_stranger: float | None,
        stranger_family: str | None = None,
    ) -> None:
        self.worst_sibling = worst_sibling
        self.best_stranger = best_stranger
        self.stranger_family = stranger_family

    @property
    def margin(self) -> float | None:
        """How far the nearest stranger beats the worst sibling. None when undecidable."""
        if self.worst_sibling is None or self.best_stranger is None:
            return None
        return self.best_stranger - self.worst_sibling


def apply_relative_veto(
    proposal: FamilyProposal,
    similarities: dict[str, MemberSimilarity],
    *,
    margin: float,
) -> FamilyProposal:
    """Flag members a product of another proposed family sits closer to.

    `similarities` is keyed by SKU. A member absent from it, or one whose extremes
    could not be computed, is left untouched rather than flagged: a missing vector
    is an indexing gap, not evidence against the membership, and treating the two
    alike would blame the product for the index.
    """
    flagged = tuple(
        _mark(member, similarities.get(member.sku), margin) for member in proposal.members
    )
    return replace(proposal, members=flagged)


def _mark(
    member: ProposedMember, similarity: MemberSimilarity | None, margin: float
) -> ProposedMember:
    if similarity is None:
        return member
    gap = similarity.margin
    if gap is None or gap <= margin:
        return member
    return replace(
        member,
        flagged_for_review=True,
        review_reason=VETO_REASON,
        distance=round(gap, 6),
    )
