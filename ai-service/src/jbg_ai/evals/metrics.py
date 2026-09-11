"""Ranking metrics over graded judgements, in both readings. C24.

Every ranking metric is computed **twice**: once with the three grades and once with the binary
reading derived from them, where a document is relevant when its grade is at least the
intermediate one. The binarisation rule is fixed in `golden.py` and never chosen per
configuration — a rule selected after seeing the result is not a rule.

Publishing both answers an objection with data instead of with argument. The course notes
recommend a binary scale for consistency between annotations; the design mandates three grades
because the critical case of this domain — the right ring in the wrong size — is neither 0 nor
2. If the two readings order the configurations the same way, the comparison is demonstrably
robust to that choice. If they disagree, that is a finding and the report says so.

**Unjudged is not zero, even though it scores as zero.** Documents outside the pool count as
irrelevant, which is the standard assumption and is declared; but `unjudged_at_5` is reported
separately, because a configuration whose top five nobody has looked at is not a bad
configuration — it is an unmeasured one, and the two must not print the same.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from jbg_ai.evals.golden import MAX_GRADE, OUT_OF_DOMAIN, RELEVANT_FROM, GoldenSet

#: Where the acceptance criterion is applied and where the report reads its headline.
CUTOFF = 5
PRECISION_CUTOFF = 3

#: The window a reranker would reorder. A maximum-grade document sitting inside it but outside
#: the top five is precisely what a cross-encoder could fix, so counting those queries is the
#: number that makes the "no" to reranking decidable instead of merely argued.
RERANK_WINDOW = 20

GradeFn = Callable[[int], float]


def graded_gain(grade: int) -> float:
    """Exponential gain, the standard nDCG formulation: 0, 1, 3 for grades 0, 1, 2."""
    return float(2**grade - 1)


def binary_gain(grade: int) -> float:
    return 1.0 if grade >= RELEVANT_FROM else 0.0


READINGS: dict[str, GradeFn] = {"graded": graded_gain, "binary": binary_gain}

#: The bucket that lowers the effective grade. One value, and the same constant the ordering
#: uses, so the metric and the ranking can never disagree about what "exhausted" means.
OUT_OF_STOCK_BUCKET = "0"


def effective_grade(grade: int, bucket: str | None) -> int:
    """The operational reading of a labelled grade. Declared 2026-09-11, before measuring.

        g_efectivo = grade                   if bucket != '0'
                     max(grade - 1, 0)       if bucket == '0'

    **It reuses the rubric's own scale rather than inventing a constant.** `criterion.md`
    already defines grade 1 as "a plausible substitute the operator would offer as a second
    option", and a piece that cannot be put on the cloth is exactly that. Stepping down one
    rung for being exhausted APPLIES the rubric instead of bending it, which is what separates
    this from the `+0.3 if in stock` multiplier the design rejected as a magic number.

    An ABSENT bucket keeps the grade. `None` means no reading scope ran, or this point of sale
    does not carry the product; neither is evidence of zero stock, and treating absence as
    exhausted would turn assortment coverage into a relevance penalty — the conflation the
    projection capability exists to keep apart.

    Grade 0 cannot fall further, hence the floor. The judgement file is never modified: this
    is a third READING of the same annotation, alongside the graded and the binary ones.
    """
    if bucket == OUT_OF_STOCK_BUCKET:
        return max(grade - 1, 0)
    return grade


def operational_gain(grade: int, bucket: str | None) -> float:
    """`graded_gain` of the effective grade. Same exponential formulation, different input."""
    return graded_gain(effective_grade(grade, bucket))


@dataclass(frozen=True)
class CaseMetrics:
    """What one query scored under one configuration."""

    query_id: str
    ndcg_at_5: float
    ndcg_at_5_binary: float
    recall_at_5: float
    recall_at_5_capped: float
    precision_at_3: float
    mrr: float
    unjudged_at_5: float
    synthetic_displacement_at_5: bool | None
    #: A maximum-grade document inside the reranking window but outside the reported five.
    rerank_headroom: bool
    abstained: bool
    relevant_total: int
    #: The third reading. `None` when no availability signal was read, which is the honest
    #: report for a configuration that does not reorder by one: the reading is NOT APPLICABLE
    #: rather than equal to the graded one, and printing them as the same number would hide
    #: which is which. Defaulted so a configuration with no business signal constructs the
    #: same way it always did.
    ndcg_at_5_operational: float | None = None

    def as_dict(self) -> dict[str, float | bool | int | None]:
        return {
            "ndcg_at_5": self.ndcg_at_5,
            "ndcg_at_5_binary": self.ndcg_at_5_binary,
            "ndcg_at_5_operational": self.ndcg_at_5_operational,
            "recall_at_5": self.recall_at_5,
            "recall_at_5_capped": self.recall_at_5_capped,
            "precision_at_3": self.precision_at_3,
            "mrr": self.mrr,
            "unjudged_at_5": self.unjudged_at_5,
            "synthetic_displacement_at_5": self.synthetic_displacement_at_5,
            "rerank_headroom": self.rerank_headroom,
            "abstained": self.abstained,
            "relevant_total": self.relevant_total,
        }


def dcg(gains: Sequence[float]) -> float:
    return sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))


def ndcg(
    ranked_grades: Sequence[int], ideal_grades: Sequence[int], *, gain: GradeFn, k: int = CUTOFF
) -> float:
    """nDCG at `k`. Zero when the query has no relevant document at all.

    Zero rather than one for an empty ideal: a query nothing can answer is not perfectly
    answered by every configuration, and the out-of-domain category would otherwise hand a
    free point to whoever returned the most rubbish.
    """
    ideal = dcg([gain(grade) for grade in sorted(ideal_grades, reverse=True)[:k]])
    if ideal <= 0:
        return 0.0
    return dcg([gain(grade) for grade in ranked_grades[:k]]) / ideal


def reciprocal_rank(ranked_grades: Sequence[int]) -> float:
    for index, grade in enumerate(ranked_grades, start=1):
        if grade >= RELEVANT_FROM:
            return 1.0 / index
    return 0.0


def precision_at(ranked_grades: Sequence[int], k: int) -> float:
    if k <= 0:
        return 0.0
    window = list(ranked_grades[:k])
    if not window:
        return 0.0
    return sum(1 for grade in window if grade >= RELEVANT_FROM) / k


def score_case(
    golden: GoldenSet,
    query_id: str,
    ranked: Sequence[UUID],
    *,
    abstained: bool,
    origin: str | None = None,
    buckets: Mapping[str, str] | None = None,
) -> CaseMetrics:
    """Score one query's ranked list. `origin` restricts which relevant documents count.

    Restricting the COUNTING is the whole of the origin breakdown: retrieval always ran over
    the complete catalogue. Restricting the corpus instead would give the real portion 404
    documents to compete in rather than 1.168 — an easier problem, and a headline number
    inflated by making the task smaller.
    """
    judged = {item.product_id: item for item in golden.judgements_for(query_id)}
    # An out-of-domain query has every document at grade zero BY the annotation criterion, so
    # nothing about it is unjudged. Reading the absence of rows as "unjudged" would mark the
    # whole category not comparable and hide the one figure it exists to produce; writing
    # thousands of zero rows to say the same thing would be worse.
    out_of_domain = golden.query(query_id).category == OUT_OF_DOMAIN
    relevant = [
        item
        for item in golden.relevant_documents(query_id)
        if origin is None or item.data_origin == origin
    ]

    def grade_of(product_id: UUID) -> int | None:
        item = judged.get(str(product_id))
        if item is None:
            return 0 if out_of_domain else None
        if origin is not None and item.data_origin != origin:
            return 0
        return item.grade

    raw = [grade_of(product_id) for product_id in ranked]
    grades = [0 if value is None else value for value in raw]
    ideal = [item.grade for item in relevant]

    window = grades[:CUTOFF]
    found = sum(1 for grade in window if grade >= RELEVANT_FROM)
    total = len(relevant)

    return CaseMetrics(
        query_id=query_id,
        ndcg_at_5=ndcg(grades, ideal, gain=graded_gain),
        ndcg_at_5_binary=ndcg(grades, ideal, gain=binary_gain),
        ndcg_at_5_operational=_operational_ndcg(
            ranked, grades, relevant, buckets=buckets
        ),
        recall_at_5=(found / total) if total else 0.0,
        recall_at_5_capped=(found / min(CUTOFF, total)) if total else 0.0,
        precision_at_3=precision_at(grades, PRECISION_CUTOFF),
        mrr=reciprocal_rank(grades),
        unjudged_at_5=(
            sum(1 for value in raw[:CUTOFF] if value is None) / len(raw[:CUTOFF])
            if raw[:CUTOFF]
            else 0.0
        ),
        synthetic_displacement_at_5=_synthetic_displacement(golden, query_id, ranked),
        rerank_headroom=(
            MAX_GRADE not in grades[:CUTOFF] and MAX_GRADE in grades[:RERANK_WINDOW]
        ),
        abstained=abstained,
        relevant_total=total,
    )


def _operational_ndcg(
    ranked: Sequence[UUID],
    grades: Sequence[int],
    relevant: Sequence[object],
    *,
    buckets: Mapping[str, str] | None,
) -> float | None:
    """nDCG@5 over the effective gains. `None` when no availability signal was read.

    **The ideal is built with the same gain function**, so this is a proper nDCG and not a
    penalised one: the denominator is the best ordering achievable given what the shop
    actually has. A relevant document whose bucket is unknown keeps its grade, by the same
    rule the numerator uses, so the two sides of the ratio can never disagree about a document.

    The ordering of configurations is what this metric is for, and every configuration is
    scored against the same denominator on the same query, so the choice is consistent by
    construction rather than by luck.
    """
    if buckets is None:
        return None
    ranked_gains = [
        operational_gain(grade, buckets.get(str(product_id)))
        for product_id, grade in zip(ranked, grades, strict=False)
    ]
    ideal_gains = sorted(
        (
            operational_gain(item.grade, buckets.get(str(item.product_id)))
            for item in relevant
        ),
        reverse=True,
    )
    ideal = dcg(ideal_gains[:CUTOFF])
    if ideal <= 0:
        return 0.0
    return dcg(ranked_gains[:CUTOFF]) / ideal


def _synthetic_displacement(
    golden: GoldenSet, query_id: str, ranked: Sequence[UUID]
) -> bool | None:
    """Did an irrelevant synthetic product outrank the first relevant REAL one?

    `None` when the question does not apply — the query has no real relevant document, so
    nothing could be displaced. It is the direct test of the design's own hypothesis, and it
    separates two things nobody could tell apart before: "the synthetic corpus is easier" and
    "the synthetic corpus gets in the way".
    """
    judged = {item.product_id: item for item in golden.judgements_for(query_id)}
    if not any(item.relevant and item.data_origin == "real" for item in judged.values()):
        return None
    for product_id in ranked[:CUTOFF]:
        item = judged.get(str(product_id))
        if item is None:
            # Unjudged: it counts as irrelevant for scoring, but its origin is unknown, so it
            # cannot be charged to the synthetic corpus. `unjudged_at_5` is where it shows up.
            continue
        if item.relevant and item.data_origin == "real":
            return False
        if not item.relevant and item.data_origin == "synthetic":
            return True
    return False


@dataclass(frozen=True)
class Aggregate:
    """A metric averaged over a set of queries, with the size that produced it."""

    queries: int
    values: dict[str, float]

    def as_dict(self) -> dict[str, float | int]:
        return {"queries": self.queries, **self.values}


AVERAGED = (
    "rerank_headroom",
    "ndcg_at_5",
    "ndcg_at_5_binary",
    "recall_at_5",
    "recall_at_5_capped",
    "precision_at_3",
    "mrr",
    "unjudged_at_5",
)


def aggregate(cases: Sequence[CaseMetrics]) -> Aggregate:
    """Mean over queries, never over documents: every query weighs the same."""
    if not cases:
        return Aggregate(queries=0, values={name: 0.0 for name in AVERAGED})
    values = {
        name: sum(float(getattr(case, name)) for case in cases) / len(cases)
        for name in AVERAGED
    }
    displacement = [
        case for case in cases if case.synthetic_displacement_at_5 is not None
    ]
    values["synthetic_displacement_at_5"] = (
        sum(1 for case in displacement if case.synthetic_displacement_at_5) / len(displacement)
        if displacement
        else 0.0
    )
    # Averaged over the queries that HAVE the reading, and omitted entirely when none does.
    # A configuration that reads no availability signal has no operational reading, and
    # printing a zero for it would rank it last on a metric it never competed in.
    operational = [
        case.ndcg_at_5_operational
        for case in cases
        if case.ndcg_at_5_operational is not None
    ]
    if operational:
        values["ndcg_at_5_operational"] = sum(operational) / len(operational)
    return Aggregate(queries=len(cases), values=values)


def abstention_rate(cases: Sequence[CaseMetrics]) -> float:
    """Share of queries the configuration declined to answer with confidence.

    Reported over the out-of-domain category, and PROVISIONAL: the live distance threshold
    admits essentially the whole catalogue, so what this measures is branch mechanics rather
    than a confidence decision. Recalibrating the threshold is a later change; this change
    publishes the distance distribution it will need.
    """
    if not cases:
        return 0.0
    return sum(1 for case in cases if case.abstained) / len(cases)


def stale_judgements(golden: GoldenSet, current_hashes: dict[str, str]) -> int:
    """How many judgements rest on a document whose text has since been rewritten.

    Reported next to the metrics and not in a separate log. A re-enrichment landing after the
    labelling would otherwise invalidate judgements silently, and the last one was kept out of
    the way by planning rather than by anything mechanical.
    """
    return sum(
        1
        for item in golden.judgements
        if item.product_id in current_hashes
        and current_hashes[item.product_id] != item.source_hash
    )


def grade_distribution(pairs: Sequence[tuple[int, float]]) -> dict[str, dict[str, float]]:
    """Distance statistics per grade, and whether one value separates relevant from irrelevant.

    This is the input a later change needs to decide whether a scalar threshold is viable at
    all. In the knowledge corpus the answer was a clean gap of eight thousandths; the question
    here is whether the product corpus has one, and either answer is a result.
    """
    buckets: dict[int, list[float]] = {grade: [] for grade in range(MAX_GRADE + 1)}
    for grade, distance in pairs:
        buckets.setdefault(grade, []).append(distance)
    out: dict[str, dict[str, float]] = {}
    for grade, values in sorted(buckets.items()):
        if not values:
            continue
        ordered = sorted(values)
        out[f"grade_{grade}"] = {
            "count": float(len(ordered)),
            "min": ordered[0],
            "p50": ordered[len(ordered) // 2],
            "max": ordered[-1],
        }
    relevant = [distance for grade, distance in pairs if grade >= RELEVANT_FROM]
    irrelevant = [distance for grade, distance in pairs if grade < RELEVANT_FROM]
    if relevant and irrelevant:
        out["separability"] = {
            "max_relevant": max(relevant),
            "min_irrelevant": min(irrelevant),
            "gap": min(irrelevant) - max(relevant),
        }
    return out
