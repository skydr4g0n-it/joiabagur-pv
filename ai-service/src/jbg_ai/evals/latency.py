"""Per-stage latency, read off the logs the orchestrator already emits. C24.

The orchestrator logs `stage=expand|embed|projection|lexical|search|fuse` with a `latency_ms`
on the stages that take time. The harness collects those rather than instrumenting the pipeline
a second time: a second channel would have to be kept in step with the first, and the day they
disagreed there would be no way to tell which one was lying.

**Two figures, always.** The acceptance criterion from the design — retrieval under 500 ms at
the 95th percentile — cannot be met read as one number: the embedding provider alone measures
170 to 1707 ms, so an end-to-end p95 is about 1700 ms and the criterion would be declared
missed for a reason that is not this service's. So `retrieval` excludes the provider round trip
and carries the criterion, and `e2e` includes it and is published next to the agreed budget.

**Warm, and repeated.** The first execution of each query is discarded and the rest are kept.
With 48 queries a p95 is the third-worst sample and is noise; with three repetitions it starts
to mean something.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field

STAGE_PATTERN = re.compile(r"stage=(?P<stage>[a-z]+)\b")
LATENCY_PATTERN = re.compile(r"latency_ms=(?P<value>[0-9]+(?:\.[0-9]+)?)")

ORCHESTRATOR_LOGGER = "jbg_ai.retrieval.orchestrator"

#: The provider round trip. Everything else in the pipeline is retrieval, which is what the
#: acceptance criterion is about.
PROVIDER_STAGE = "embed"


@dataclass
class StageCollector(logging.Handler):
    """Captures the per-stage latencies of whatever runs inside its context.

    A handler rather than a monkeypatch: it observes what the pipeline already says about
    itself and cannot change what the pipeline does, so a measured run and a served request go
    down exactly the same path.
    """

    stages: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def __post_init__(self) -> None:
        super().__init__(level=logging.INFO)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - a measurement must never break the thing measured
            return
        stage = STAGE_PATTERN.search(message)
        latency = LATENCY_PATTERN.search(message)
        if stage is None or latency is None:
            return
        self.stages[stage.group("stage")].append(float(latency.group("value")))

    def reset(self) -> None:
        self.stages = defaultdict(list)

    def total(self, stage: str) -> float:
        return sum(self.stages.get(stage, ()))

    def __enter__(self) -> "StageCollector":
        logger = logging.getLogger(ORCHESTRATOR_LOGGER)
        self._previous_level = logger.level
        self._previous_propagate = logger.propagate
        logger.setLevel(logging.INFO)
        logger.addHandler(self)
        return self

    def __exit__(self, *_exc: object) -> None:
        logger = logging.getLogger(ORCHESTRATOR_LOGGER)
        logger.removeHandler(self)
        logger.setLevel(self._previous_level)
        logger.propagate = self._previous_propagate


@dataclass(frozen=True)
class Sample:
    """One timed execution of one query."""

    query_id: str
    e2e_ms: float
    provider_ms: float
    lexical_ms: float

    @property
    def retrieval_ms(self) -> float:
        """End to end minus the provider round trip, floored at zero.

        Subtraction rather than a second stopwatch: the provider is raced against the lexical
        branch, so the two overlap in wall-clock time and adding up stage timings would double
        count. What the criterion is about is what remains when the provider is free.
        """
        return max(self.e2e_ms - self.provider_ms, 0.0)


def percentile(values: list[float], fraction: float) -> float | None:
    """Nearest-rank percentile. `None` for an empty sample, never zero.

    Zero would be indistinguishable from an instantaneous pipeline, and a latency table with a
    zero in it invites exactly the wrong conclusion.
    """
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(fraction * len(ordered) + 0.5) - 1))
    return ordered[index]


@dataclass(frozen=True)
class LatencySummary:
    p50_retrieval: float | None
    p95_retrieval: float | None
    p50_e2e: float | None
    p95_e2e: float | None
    p50_lexical: float | None
    p95_lexical: float | None
    cold_e2e_ms: float | None
    samples: int

    def as_dict(self) -> dict[str, float | int | None]:
        return {
            "p50_retrieval_ms": self.p50_retrieval,
            "p95_retrieval_ms": self.p95_retrieval,
            "p50_e2e_ms": self.p50_e2e,
            "p95_e2e_ms": self.p95_e2e,
            "p50_lexical_ms": self.p50_lexical,
            "p95_lexical_ms": self.p95_lexical,
            "cold_e2e_ms": self.cold_e2e_ms,
            "latency_samples": self.samples,
        }


def summarise(warm: list[Sample], *, cold: list[Sample] | None = None) -> LatencySummary:
    """Percentiles over the warm samples, with the discarded cold one kept as a figure.

    The cold execution is excluded from the percentiles and REPORTED, because it is the answer
    to a question the previous change left without an owner: what the singleton embedding
    client is worth on the first call against a warm one.
    """
    retrieval = [item.retrieval_ms for item in warm]
    e2e = [item.e2e_ms for item in warm]
    lexical = [item.lexical_ms for item in warm if item.lexical_ms > 0]
    cold_samples = [item.e2e_ms for item in (cold or [])]
    return LatencySummary(
        p50_retrieval=percentile(retrieval, 0.50),
        p95_retrieval=percentile(retrieval, 0.95),
        p50_e2e=percentile(e2e, 0.50),
        p95_e2e=percentile(e2e, 0.95),
        p50_lexical=percentile(lexical, 0.50),
        p95_lexical=percentile(lexical, 0.95),
        cold_e2e_ms=percentile(cold_samples, 0.50),
        samples=len(warm),
    )
