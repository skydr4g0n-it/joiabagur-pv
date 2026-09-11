"""The directional sweep and the rule that may move a default. C24.

**The rule was written before the measurement ran**, which is the only thing that makes
"the sweep was redone with the good judge" a claim rather than an impression:

    a default changes if and only if
      · the nDCG@5 improvement exceeds 0.05, AND
      · the sign is the same in the three readings of the tuning split, AND
      · no measured category degrades by more than 0.05.

**The sweep is directional, and the direction was argued before it ran too.** The rubric that
fixed the live weights is the lexical branch's own objective function, so it undervalues the
vector branch by construction; the true optimum can only be at or above the weight in force,
never below it. Exploring downwards would spend provider calls confirming a bias.

Also swept: the branch depth, because it is not independent of the fusion constant — a deeper
branch keeps more of its tail voting — so the two move together or neither means anything.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product

from jbg_ai.config.settings import FUSION_DEFAULTS, Settings
from jbg_ai.evals.configs import EvalConfig
from jbg_ai.evals.golden import GoldenSet
from jbg_ai.evals.metrics import Aggregate
from jbg_ai.evals.pricing import PriceList
from jbg_ai.evals.provenance import Provenance
from jbg_ai.evals.runner import ConfigReport, run_config
from jbg_ai.indexing.embeddings import EmbeddingClient
from jbg_ai.retrieval.ports import ProductSearchPort

#: Never below the value in force. See the module docstring.
WEIGHT_VECTOR_GRID = (0.33, 0.5, 0.75, 1.0, 1.5, 2.0)

#: The plateau the earlier sweep found was 40-60, decaying monotonically past 100.
BRANCH_DEPTH_GRID = (40, 60)

#: Above the annotation noise a golden set of this size can resolve. With a confidence interval
#: of about ±0.13 on the real portion, anything smaller is a difference this set cannot see.
MATERIAL_DELTA = 0.05

#: No category may pay for the gain by more than this.
CATEGORY_TOLERANCE = 0.05

DECISION_METRIC = "ndcg_at_5"


@dataclass(frozen=True)
class SweepPoint:
    weight_vector: float
    branch_depth: int
    report: ConfigReport

    @property
    def label(self) -> str:
        return f"wC={self.weight_vector} depth={self.branch_depth}"

    def score(self, reading: str = "global") -> float:
        return self.report.readings[reading].values[DECISION_METRIC]


@dataclass(frozen=True)
class Verdict:
    """What the rule says, and every figure it says it from."""

    moved: bool
    reason: str
    baseline: SweepPoint
    best: SweepPoint
    deltas: dict[str, float]
    category_deltas: dict[str, float]

    def as_lines(self) -> list[str]:
        lines = [
            f"- Configuración vigente: **{self.baseline.label}** → "
            f"nDCG@5 {self.baseline.score():.3f}",
            f"- Mejor del barrido: **{self.best.label}** → nDCG@5 {self.best.score():.3f}",
            "- Deltas por lectura: "
            + ", ".join(f"{name} {value:+.3f}" for name, value in self.deltas.items()),
            "- Peor categoría: "
            + ", ".join(
                f"{name} {value:+.3f}"
                for name, value in sorted(self.category_deltas.items(), key=lambda i: i[1])[:3]
            ),
            f"- **Veredicto: {'se mueve el default' if self.moved else 'NO se mueve el default'}** "
            f"— {self.reason}",
        ]
        return lines


def _values(agg: Aggregate) -> float:
    return agg.values[DECISION_METRIC]


def decide(baseline: SweepPoint, candidates: list[SweepPoint]) -> Verdict:
    """Apply the three conditions. Documents the outcome whether or not anything moves."""
    best = max(candidates, key=lambda point: point.score())
    deltas = {
        reading: _values(best.report.readings[reading])
        - _values(baseline.report.readings[reading])
        for reading in ("global", "tuning", "new")
    }
    category_deltas = {
        name: _values(best.report.by_category[name]) - _values(agg)
        for name, agg in baseline.report.by_category.items()
    }

    if deltas["global"] <= MATERIAL_DELTA:
        return Verdict(
            moved=False,
            reason=(
                f"la mejora global es {deltas['global']:+.3f}, por debajo del margen acordado "
                f"de {MATERIAL_DELTA}; con un intervalo de ±0,13 sobre la porción real, una "
                "diferencia así no se distingue del ruido de anotación"
            ),
            baseline=baseline,
            best=best,
            deltas=deltas,
            category_deltas=category_deltas,
        )
    if not all(value > 0 for value in deltas.values()):
        disagreeing = [name for name, value in deltas.items() if value <= 0]
        return Verdict(
            moved=False,
            reason=(
                f"el signo no es el mismo en las tres lecturas: {disagreeing} no mejora. "
                "Un resultado que sólo se sostiene en el conjunto de ajuste es sobreajuste, y "
                "encontrarlo es el trabajo"
            ),
            baseline=baseline,
            best=best,
            deltas=deltas,
            category_deltas=category_deltas,
        )
    worst = min(category_deltas.items(), key=lambda item: item[1], default=("", 0.0))
    if worst[1] < -CATEGORY_TOLERANCE:
        return Verdict(
            moved=False,
            reason=(
                f"la categoría `{worst[0]}` empeora {worst[1]:+.3f}, más de lo acordado "
                f"({CATEGORY_TOLERANCE}). La media puede subir mientras un caso de uso entero "
                "se rompe, y por eso la regla mira las categorías y no sólo el agregado"
            ),
            baseline=baseline,
            best=best,
            deltas=deltas,
            category_deltas=category_deltas,
        )
    return Verdict(
        moved=True,
        reason=(
            "supera el margen, apunta en el mismo sentido en las tres lecturas y ninguna "
            "categoría paga más de lo acordado"
        ),
        baseline=baseline,
        best=best,
        deltas=deltas,
        category_deltas=category_deltas,
    )


async def sweep(
    config: EvalConfig,
    golden: GoldenSet,
    *,
    settings: Settings,
    search: ProductSearchPort,
    embed: EmbeddingClient,
    prices: PriceList,
    provenance: Provenance,
    repeat: int = 1,
) -> tuple[SweepPoint, list[SweepPoint]]:
    """Run the grid in series and return the point in force plus every candidate."""
    points: list[SweepPoint] = []
    for weight, depth in product(WEIGHT_VECTOR_GRID, BRANCH_DEPTH_GRID):
        variant = replace(config, weight_vector=weight, branch_depth=depth)
        report = await run_config(
            variant,
            golden,
            settings=settings,
            search=search,
            embed=embed,
            prices=prices,
            provenance=provenance,
            repeat=repeat,
        )
        points.append(SweepPoint(weight_vector=weight, branch_depth=depth, report=report))

    live = (
        FUSION_DEFAULTS["jpv_rrf_weight_vector"],
        FUSION_DEFAULTS["jpv_branch_depth"],
    )
    baseline = next(
        point
        for point in points
        if (point.weight_vector, point.branch_depth) == live
    )
    return baseline, [point for point in points if point is not baseline]
