"""The substitutes evaluation slice: its own run, its own report, its own table. C26.

**Why a slice and not a row of the ablation table.** The published table compares
configurations of the product retriever over the judged queries; two of its rows (`v0-fts`,
`v1-vectorial`) could not execute this endpoint at all, because it takes a `product_id` and
not text. Adding these queries as rows would move the denominator of a table that has been
published twice, and a number that changes when nothing about its configuration changed is
worse than a number that is missing.

**Why the queries are anchored and not chained.** The four reserved queries are text. Feeding
that text to the product retriever and handing its best hit to the substitutes endpoint would
measure the CHAIN — which is C32's — and would charge every failure of the first step to this
capability. Each query declares `source_product_id` instead, so what is measured is the
quality of the substitute GIVEN the correct source product. That limit is real and is
declared in the report rather than papered over.

The run is in-process, exactly as `execute.py` calls `retrieve_products`: a harness that
re-implemented the ordering would measure the re-implementation.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from jbg_ai.api.schemas.retrieval import SubstitutesRequest
from jbg_ai.config.settings import Settings
from jbg_ai.evals.errors import EvaluationUnavailable
from jbg_ai.evals.execute import RankedHit, QueryRun, harness_principal
from jbg_ai.evals.golden import SUBSTITUTE, GoldenQuery, GoldenSet
from jbg_ai.evals.latency import Sample
from jbg_ai.evals.metrics import CaseMetrics, score_case
from jbg_ai.retrieval.ports import ProductSearchPort
from jbg_ai.retrieval.substitutes import retrieve_substitutes

#: `retrieve_substitutes` returns `min(top_k * 3, 60)`, the same over-retrieval rule as the
#: products route, so twenty is how the harness sees the whole sixty-candidate window.
TOP_K_FOR_FULL_WINDOW = 20

#: The grid the size weight is swept over. `0.0` is in it because it is the ROLLBACK and its
#: row is what proves the term does something; `0.05` because the exploration simulated it as
#: the interleaving point; `0.08` because the same simulation showed it banishing a sibling to
#: position 8, so the grid has to contain a value that is visibly too strong or the sweep is
#: only exploring the half that works.
SWEEP_WEIGHTS: tuple[float, ...] = (0.0, 0.02, 0.05, 0.08, 0.12)


def config_id(weight_size: float) -> str:
    """Identifier of one point of the sweep. Never a row of the published ablations table."""
    return f"c26-substitutes-w{weight_size:g}"


@dataclass(frozen=True)
class SliceCase:
    """One query under one weight: the ranked list and what it scored."""

    config_id: str
    weight_size: float
    query_id: str
    ranked: tuple[UUID, ...]
    skus: tuple[str, ...]
    metrics: CaseMetrics


def substitute_queries(golden: GoldenSet) -> tuple[GoldenQuery, ...]:
    """The anchored substitutes queries, in file order. Unjudged ones are excluded.

    A query without judgements cannot be scored, and scoring it as zero would report the
    annotator's backlog as a defect of the retriever.
    """
    return tuple(
        item
        for item in golden.queries
        if item.category == SUBSTITUTE and item.judged and item.source_product_id
    )


async def execute_substitutes(
    query: GoldenQuery,
    *,
    settings: Settings,
    search: ProductSearchPort,
    weight_size: float,
    depth: int = TOP_K_FOR_FULL_WINDOW,
) -> QueryRun:
    """Run one substitutes query at one weight. In process, and no provider is called.

    The point of sale is NOT applied: the golden set is labelled unscoped, exactly as every
    configuration of the published table sets `pos_prefilter: false`. Letting the assortment
    of one shop in here would make the measured number depend on which shop the harness
    borrowed, and the judgements say nothing about that.
    """
    if not query.source_product_id:
        raise EvaluationUnavailable(
            f"{query.id} has no `source_product_id`; the substitutes endpoint takes a product"
        )

    started = time.perf_counter()
    response = await retrieve_substitutes(
        SubstitutesRequest(
            product_id=query.source_product_id,
            top_k=TOP_K_FOR_FULL_WINDOW,
            reason=query.text,
        ),
        harness_principal(),
        settings=settings,
        search=search,
        weight_size=weight_size,
        pos_signals=False,
    )
    e2e_ms = (time.perf_counter() - started) * 1000

    hits = tuple(
        RankedHit(UUID(item.product_id), item.sku, item.score) for item in response.results
    )
    return QueryRun(
        query_id=query.id,
        hits=hits[:depth],
        # The provider cost is zero and zero is a VALUE here, not a blank: "no provider call"
        # is the headline property of this capability, so the column has to carry a figure
        # somebody can point at rather than an empty cell that reads as "not measured".
        sample=Sample(query_id=query.id, e2e_ms=e2e_ms, provider_ms=0.0, lexical_ms=0.0),
        low_confidence=response.low_confidence,
    )


async def run_slice(
    golden: GoldenSet,
    *,
    settings: Settings,
    search: ProductSearchPort,
    weights: Sequence[float] = SWEEP_WEIGHTS,
) -> tuple[SliceCase, ...]:
    """Every anchored query at every weight of the grid."""
    queries = substitute_queries(golden)
    if not queries:
        raise EvaluationUnavailable(
            "no judged substitutes query declares a source product; there is nothing to run"
        )

    cases: list[SliceCase] = []
    for weight in weights:
        for query in queries:
            run = await execute_substitutes(
                query, settings=settings, search=search, weight_size=weight
            )
            ranked = tuple(hit.product_id for hit in run.hits)
            cases.append(
                SliceCase(
                    config_id=config_id(weight),
                    weight_size=weight,
                    query_id=query.id,
                    ranked=ranked,
                    skus=tuple(hit.sku for hit in run.hits),
                    metrics=score_case(
                        golden,
                        query.id,
                        ranked,
                        abstained=run.low_confidence,
                    ),
                )
            )
    return tuple(cases)
