"""What makes two runs comparable, and what to do when they are not. C24.

The evaluation pipeline has no randomness, so there is no seed to fix. What decides whether a
number can be compared with a number taken last week is **provenance**: which golden set, which
configuration, which indexed document set, which embedding model, which fusion mode and which
revision of the code produced it. Six things, recorded on the run rather than in a log, because
a run whose provenance has to be reconstructed from memory is a run that will be compared anyway.

The composition is the sixth, and C25bis is the reason it STAYS one. C25 added it because the
flat fusion was selectable, so two runs of the same configuration at the same revision could
compose their lists differently; retiring that mode removes the case, and the tempting
conclusion is that the element can go back to being implied by the revision.

It cannot, and the distinction is worth writing down because it is the one C25bis turns on:
**selecting a composition and recording it are different things.** No configuration can choose
one any more, but a run archived under the retired composition must still be distinguishable
from one taken today — `differences()` is what keeps the published baseline from being compared
with a current row as if nothing had changed — and a run must declare what it actually composed
rather than what somebody's environment was thought to request. So the value comes from the
code, never from a setting, and it is exactly because it is no longer a knob that it has to
remain a record.

Two runs whose provenance differs are reported as NOT COMPARABLE and the differing element is
named. That is the whole mechanism: it is cheaper to say "the index moved" than to explain a
metric that moved for a reason nobody can find.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from uuid import UUID

from jbg_ai.indexing.set_hash import of_product_ids

UNKNOWN_SHA = "unknown"

#: Appended to the revision when the working tree carried uncommitted changes at run time.
#: A run taken on a dirty tree was NOT produced by the commit it names, so recording the bare
#: sha would invert the mechanism this module exists for: a later re-run at that commit would
#: be declared comparable and produce different numbers. C25 was bitten by exactly this — its
#: published table was measured with metric code that only landed in the NEXT commit.
DIRTY_SUFFIX = "+dirty"

#: Recorded as the fusion mode of a configuration that fuses nothing — the two degraded
#: baselines, the context-only row, and the single-branch vector row. Naming the absence is
#: not pedantry: defaulting them to the live mode would put a composition rule on four rows
#: that never composed anything, and the column would stop meaning what it says.
NO_FUSION = "none"

#: The one composition the code can produce: the two lexical lists fused into one ranked list,
#: that list fused against the vector list under the per-branch weights.
#:
#: It lives here, in the module that RECORDS provenance, and no longer in settings, because
#: C25bis retired the knob and kept the record. The archived baseline carries `flat` in its own
#: provenance, so the two values still disagree where they should — which is the entire reason
#: this element survived the knob.
BRANCH_FUSION = "branch"


@dataclass(frozen=True)
class Provenance:
    """The six-part tuple. `embedding_model_version_key` is None for a configuration that
    calls no embedder, and None is an ANSWER: it says the run does not depend on the model, so
    a model change does not make it incomparable with its own earlier runs."""

    golden_set_version: str
    config_id: str
    index_set_hash: str
    embedding_model_version_key: str | None
    git_sha: str
    #: How the branches were composed. Live runs record `BRANCH_FUSION`; rows that fuse nothing
    #: record `NO_FUSION`; and archived runs still carry the `flat` of the retired single-stage
    #: composition. Two runs that fused differently are not comparable even at the same revision.
    fusion_mode: str

    def differences(self, other: "Provenance") -> tuple[str, ...]:
        """Which elements disagree. Empty means the two runs may be compared."""
        return tuple(
            name
            for name in (
                "golden_set_version",
                "config_id",
                "index_set_hash",
                "embedding_model_version_key",
                "git_sha",
                "fusion_mode",
            )
            if getattr(self, name) != getattr(other, name)
        )

    def comparable_with(self, other: "Provenance") -> bool:
        """Same configuration and same everything else. A different config is the POINT of an
        ablation table, so it is excluded from the comparison of provenance itself."""
        return not [name for name in self.differences(other) if name != "config_id"]

    def as_dict(self) -> dict[str, str | None]:
        return {
            "golden_set_version": self.golden_set_version,
            "config_id": self.config_id,
            "index_set_hash": self.index_set_hash,
            "embedding_model_version_key": self.embedding_model_version_key,
            "git_sha": self.git_sha,
            "fusion_mode": self.fusion_mode,
        }


def index_set_hash(product_ids: list[UUID]) -> str:
    """Fingerprint of the indexed set, reusing the function the catalogue feed already agrees on.

    Not a count and not a maximum timestamp: a set that lost one product and gained another has
    the same count, and a reindex that rewrote no row leaves the timestamps alone. The ordering
    inside it is plain byte order, which the earlier change discovered the hard way.
    """
    return of_product_ids(product_ids)


def _git(*args: str) -> str | None:
    """One git command, or `None` when there is no repository to ask."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip()


def current_git_sha() -> str:
    """The revision the code was at, or `unknown` — never a guess.

    A run taken from an archive with no repository around it is still a run; recording
    `unknown` says so, and a later comparison then reports itself as not comparable, which is
    the correct outcome rather than an inconvenience.

    A **dirty working tree** is marked, because a bare sha would be a false statement rather
    than an imprecise one: the code that produced the run is not the code at that commit, and
    the difference is invisible afterwards. The marker makes the run incomparable with a clean
    run at the same commit, which is the honest outcome — an unmarked sha claims a
    reproducibility the run does not have.
    """
    sha = _git("rev-parse", "HEAD")
    if not sha:
        return UNKNOWN_SHA
    # `--porcelain` is empty exactly when nothing is staged, modified or untracked. `None`
    # here means the status could not be taken, and an unverifiable tree is treated as dirty:
    # the failure mode of over-marking is a spurious "not comparable", and of under-marking a
    # silently wrong number.
    status = _git("status", "--porcelain")
    return sha if status == "" else f"{sha}{DIRTY_SUFFIX}"
