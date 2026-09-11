"""What makes two runs comparable, and what to do when they are not. C24.

The evaluation pipeline has no randomness, so there is no seed to fix. What decides whether a
number can be compared with a number taken last week is **provenance**: which golden set, which
configuration, which indexed document set, which embedding model and which revision of the
code produced it. Five things, recorded on the run rather than in a log, because a run whose
provenance has to be reconstructed from memory is a run that will be compared anyway.

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


@dataclass(frozen=True)
class Provenance:
    """The five-part tuple. `embedding_model_version_key` is None for a configuration that
    calls no embedder, and None is an ANSWER: it says the run does not depend on the model, so
    a model change does not make it incomparable with its own earlier runs."""

    golden_set_version: str
    config_id: str
    index_set_hash: str
    embedding_model_version_key: str | None
    git_sha: str

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
        }


def index_set_hash(product_ids: list[UUID]) -> str:
    """Fingerprint of the indexed set, reusing the function the catalogue feed already agrees on.

    Not a count and not a maximum timestamp: a set that lost one product and gained another has
    the same count, and a reindex that rewrote no row leaves the timestamps alone. The ordering
    inside it is plain byte order, which the earlier change discovered the hard way.
    """
    return of_product_ids(product_ids)


def current_git_sha() -> str:
    """The revision the code was at, or `unknown` — never a guess.

    A run taken from an archive with no repository around it is still a run; recording
    `unknown` says so, and a later comparison then reports itself as not comparable, which is
    the correct outcome rather than an inconvenience.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN_SHA
    sha = result.stdout.strip()
    return sha or UNKNOWN_SHA
