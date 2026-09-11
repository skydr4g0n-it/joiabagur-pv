"""`Report` to Markdown and JSONL, in the repository. C24.

Always, and before anything else: the result of an evaluation is evidence of the project, and
evidence that lives only in a database is evidence nobody diffs between two revisions. The
Markdown goes next to the earlier measurement reports; the per-query detail goes to
`results/runs/<run_id>.jsonl` so two runs can be compared line by line.
"""

from __future__ import annotations

import json
from pathlib import Path

from jbg_ai.data.paths import AI_SERVICE_ROOT
from jbg_ai.evals.metrics import CUTOFF
from jbg_ai.evals.runner import ConfigReport, Report

RESULTS_DIR = AI_SERVICE_ROOT / "evals" / "results"
RUNS_DIR = RESULTS_DIR / "runs"

HEADLINE = ("ndcg_at_5", "ndcg_at_5_binary", "recall_at_5_capped", "precision_at_3", "mrr")

#: Share of the reported results that may carry no judgement before the row stops being a
#: comparable score and becomes an unmeasured one. One in five means the metric was computed
#: over a list a fifth of which nobody looked at, and unjudged counts as irrelevant — so the
#: row is not a bad result, it is an unknown one, and printing it as final would penalise a
#: configuration for surfacing documents the pool never contained.
#:
#: Today every configuration reports zero, because the pool was built from these same
#: configurations. The threshold exists for the ones that come next: a change that reorders
#: results can promote documents nobody judged, and that is precisely when this has to fire.
NOT_COMPARABLE_UNJUDGED = 0.20


def _fmt(value: float | int | None, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}"


def not_comparable(item: ConfigReport) -> bool:
    """True when too much of this row's top results carries no judgement to score it as final."""
    return item.readings["global"].values["unjudged_at_5"] > NOT_COMPARABLE_UNJUDGED


def _ablation_table(report: Report) -> list[str]:
    lines = [
        "| configuración | nDCG@5 | nDCG@5 bin | nDCG@5 oper | Recall@5 | P@3 | MRR "
        "| no juzgado@5 | coste/consulta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report.configs:
        values = item.readings["global"].values
        mark = " ⚠ **no comparable**" if not_comparable(item) else ""
        # An em dash and not a zero: a configuration that reorders by no business signal has
        # no operational reading, and printing 0,000 would rank it last on a metric it never
        # competed in.
        operational = (
            _fmt(values["ndcg_at_5_operational"])
            if "ndcg_at_5_operational" in values
            else "—"
        )
        lines.append(
            f"| `{item.config_id}`{mark} | {_fmt(values['ndcg_at_5'])} | "
            f"{_fmt(values['ndcg_at_5_binary'])} | {operational} | "
            f"{_fmt(values['recall_at_5_capped'])} | "
            f"{_fmt(values['precision_at_3'])} | {_fmt(values['mrr'])} | "
            f"{_fmt(values['unjudged_at_5'])} | ${item.cost_per_query_usd:.7f} |"
        )
    if any("ndcg_at_5_operational" in item.readings["global"].values for item in report.configs):
        lines += [
            "",
            "> **La lectura operativa** aplica `g_efectivo = grado` si `qty_bucket ≠ '0'` y "
            "`máx(grado − 1, 0)` si es `'0'`, declarada el **2026-09-11 antes de calcular "
            "ninguna métrica**. No inventa una constante: reutiliza la escala de "
            "`criterion.md`, donde el grado 1 ya es *«sustituto plausible que el operador "
            "ofrecería como segunda opción»* y una pieza que no se puede poner sobre el paño "
            "es exactamente eso. Una fila con proyección **ausente conserva su grado**, porque "
            "la ausencia no es evidencia de stock cero. `judgements.jsonl` no se modifica: es "
            "una tercera lectura de la misma anotación, y la relevancia pura es su "
            "**guardarraíl** — una configuración que mejore la operativa y degrade la pura "
            "más de 0,05 no se adopta. Un guion significa que esa fila no reordena por "
            "ninguna señal de negocio, no que puntúe cero.",
        ]
    flagged = [item.config_id for item in report.configs if not_comparable(item)]
    if flagged:
        lines += [
            "",
            f"> **Filas no comparables: {', '.join(f'`{name}`' for name in flagged)}.** Más de un "
            f"{NOT_COMPARABLE_UNJUDGED:.0%} de sus primeros resultados **no tiene juicio**, y lo "
            "no juzgado puntúa como irrelevante: su cifra no es un mal resultado sino un "
            "resultado desconocido, y presentarla como definitiva castigaría a la configuración "
            "por sacar a la superficie documentos que el *pool* nunca contuvo. Se amplía el "
            "*pool* y se vuelve a medir; los juicios son apendables justo para esto.",
        ]
    return lines


def _readings_table(item: ConfigReport) -> list[str]:
    lines = [
        f"**`{item.config_id}`** — {item.label}",
        "",
        "| lectura | n | nDCG@5 | nDCG@5 bin | Recall@5 | P@3 | MRR |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("global", "tuning", "new"):
        agg = item.readings[name]
        lines.append(
            f"| {name} | {agg.queries} | {_fmt(agg.values['ndcg_at_5'])} | "
            f"{_fmt(agg.values['ndcg_at_5_binary'])} | "
            f"{_fmt(agg.values['recall_at_5_capped'])} | "
            f"{_fmt(agg.values['precision_at_3'])} | {_fmt(agg.values['mrr'])} |"
        )
    lines.append("")
    return lines


def reading_divergence(report: Report) -> tuple[str, ...]:
    """Configurations the two readings order differently, most-preferred first in each.

    Publishing both readings only answers the objection if a disagreement between them is
    surfaced rather than left for a reader to spot. If the graded scale and the binary one rank
    the configurations the same way, the comparison is demonstrably robust to that choice; if
    they do not, the comparison is not robust and that is the finding.
    """
    graded = [
        item.config_id
        for item in sorted(
            report.configs,
            key=lambda value: value.readings["global"].values["ndcg_at_5"],
            reverse=True,
        )
    ]
    binary = [
        item.config_id
        for item in sorted(
            report.configs,
            key=lambda value: value.readings["global"].values["ndcg_at_5_binary"],
            reverse=True,
        )
    ]
    return () if graded == binary else (", ".join(graded), ", ".join(binary))


def render_markdown(report: Report, *, title: str) -> str:
    prices = report.price_list
    lines: list[str] = [
        f"# {title}",
        "",
        f"Ejecutado el {report.generated_at.date().isoformat()} contra {report.corpus_size} "
        "documentos vivos de `ai.product_document`, en solo lectura sobre el índice.",
        "",
        "| procedencia | valor |",
        "|---|---|",
        f"| versión del golden set | `{report.golden_set_version}` |",
        f"| huella del conjunto indexado | `{report.index_set_hash[:16]}…` |",
        f"| revisión del código | `{report.git_sha[:12]}` |",
        f"| identificador de la ejecución | `{report.run_id}` |",
        "",
        "Dos ejecuciones cuya procedencia no coincida **no son comparables**, y el arnés lo "
        "dice en lugar de compararlas igualmente.",
        "",
        "## Tabla de ablations v0 → v2",
        "",
        *_ablation_table(report),
        "",
        f"`Recall@5` se publica con el denominador acotado a min(5, |relevantes|): con "
        f"consultas que tienen decenas de documentos relevantes, la lectura clásica está "
        f"limitada por el tamaño del conjunto relevante y mide el catálogo en vez del "
        f"recuperador. Las dos cifras están en el JSONL por consulta.",
        "",
        *(
            [
                "> **Hallazgo: las dos lecturas no coinciden.** Con los grados el orden es "
                f"`{reading_divergence(report)[0]}`; con la lectura binaria es "
                f"`{reading_divergence(report)[1]}`. La comparación **no es robusta** a la "
                "elección de escala, y ninguna conclusión sobre qué configuración gana puede "
                "apoyarse sólo en una de las dos.",
                "",
            ]
            if reading_divergence(report)
            else [
                "Las dos lecturas ordenan las configuraciones **igual**, así que la comparación "
                "es robusta a la elección de escala. Ésa es la objeción del apunte de S10 "
                "—que el binario es más consistente entre anotaciones— contestada con datos en "
                "lugar de con argumento.",
                "",
            ]
        ),
        "## Las tres lecturas de la partición de ajuste",
        "",
        "Una decisión de configuración **no se da por confirmada** si no apunta en el mismo "
        "sentido en las tres.",
        "",
    ]
    for item in report.configs:
        lines += _readings_table(item)

    lines += [
        "## Desglose por origen del dato",
        "",
        "La recuperación corre **siempre sobre el catálogo completo**. Lo que se agrupa es la "
        "consulta, por el origen de sus documentos relevantes, y lo que se cuenta son sólo los "
        "relevantes de ese origen. Restringir el corpus a un origen no es una configuración "
        "disponible: daría un problema más fácil y una cifra de titular inflada.",
        "",
        "| configuración | origen | n | nDCG@5 | Recall@5 | desplazamiento sintético@5 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for item in report.configs:
        for origin, agg in item.by_origin.items():
            lines.append(
                f"| `{item.config_id}` | {origin} | {agg.queries} | "
                f"{_fmt(agg.values['ndcg_at_5'])} | "
                f"{_fmt(agg.values['recall_at_5_capped'])} | "
                f"{_fmt(agg.values.get('synthetic_displacement_at_5'))} |"
            )

    lines += [
        "",
        "## Por categoría",
        "",
        "| configuración | " + " | ".join(sorted(report.configs[0].by_category)) + " |",
        "|---|" + "---:|" * len(report.configs[0].by_category),
    ]
    for item in report.configs:
        row = " | ".join(
            _fmt(item.by_category[name].values["ndcg_at_5"])
            for name in sorted(item.by_category)
        )
        lines.append(f"| `{item.config_id}` | {row} |")

    lines += [
        "",
        "## Latencia",
        "",
        "Dos columnas siempre. El criterio de aceptación se aplica a `p95 recuperación`, que "
        "excluye el ida y vuelta del proveedor de embeddings; `p95 extremo a extremo` se "
        "publica junto al presupuesto acordado. Se descarta la primera ejecución de cada "
        "consulta y se promedian las repeticiones, para que el percentil no describa un "
        "arranque en frío.",
        "",
        "| configuración | p50 recup. | p95 recup. | p50 e2e | p95 e2e | p50 léxica | p50 en frío | muestras |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report.configs:
        latency = item.latency
        lines.append(
            f"| `{item.config_id}` | {_fmt(latency.p50_retrieval, 1)} | "
            f"{_fmt(latency.p95_retrieval, 1)} | {_fmt(latency.p50_e2e, 1)} | "
            f"{_fmt(latency.p95_e2e, 1)} | {_fmt(latency.p50_lexical, 1)} | "
            f"{_fmt(latency.cold_e2e_ms, 1)} | {latency.samples} |"
        )

    lines += [
        "",
        "## Abstención",
        "",
        "**Provisional.** El umbral de distancia vigente deja pasar prácticamente todo el "
        "catálogo, así que lo que se mide aquí es la mecánica de las ramas y no una decisión "
        "de confianza. Este change **no** toca el umbral; su re-fijación es alcance del "
        "siguiente, y la distribución que necesita se publica más abajo.",
        "",
        "| configuración | tasa de abstención sobre fuera de dominio |",
        "|---|---:|",
    ]
    for item in report.configs:
        lines.append(f"| `{item.config_id}` | {_fmt(item.abstention_rate)} |")

    lines += [
        "",
        "## El número que haría decidible el reranking",
        "",
        "Consultas cuyo documento de grado máximo está dentro de la ventana que un reranker "
        "reordenaría pero fuera de los cinco que se muestran. Es exactamente lo que un "
        "cross-encoder podría arreglar, y por tanto el denominador del «no» al reranking: sin "
        "esta cifra la decisión se argumenta, con ella se mide. Este change **no** implementa "
        "el reranker; deja el protocolo ejecutable y el número.",
        "",
        "| configuración | consultas con grado 2 en el top-20 y fuera del top-5 |",
        "|---|---:|",
    ]
    for item in report.configs:
        headroom = item.readings["global"].values.get("rerank_headroom", 0.0)
        lines.append(
            f"| `{item.config_id}` | {_fmt(headroom)} "
            f"({round(headroom * item.readings['global'].queries)} de "
            f"{item.readings['global'].queries}) |"
        )

    lines += [
        "",
        "## Distribución de distancias por grado",
        "",
        "| grado | documentos | mínimo | mediana | máximo |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, values in report.distance_distribution.items():
        if name == "separability":
            continue
        lines.append(
            f"| {name} | {int(values['count'])} | {_fmt(values['min'], 4)} | "
            f"{_fmt(values['p50'], 4)} | {_fmt(values['max'], 4)} |"
        )
    separability = report.distance_distribution.get("separability")
    if separability:
        gap = separability["gap"]
        lines += [
            "",
            f"Máxima distancia de un documento relevante: **{separability['max_relevant']:.4f}**. "
            f"Mínima de uno irrelevante: **{separability['min_irrelevant']:.4f}**. "
            f"Hueco: **{gap:+.4f}**.",
            "",
            (
                "Las dos poblaciones **se solapan**: no existe un valor único que las separe, "
                "de modo que un umbral escalar no puede ser la respuesta y hace falta un "
                "cuantil por consulta. Eso es un resultado, no una tarea pendiente."
                if gap <= 0
                else "Las dos poblaciones **son separables por un valor único**, que es la "
                "forma que tenía la respuesta en el corpus de conocimiento."
            ),
        ]

    lines += [
        "",
        "## Juicios y coste",
        "",
        f"- Juicios que se apoyan en un texto que ya cambió desde el etiquetado: "
        f"**{report.stale_judgements}**.",
        f"- Precios: `as_of: {prices.as_of}`, fuente `{prices.source}`, "
        + ("**verificados** el día de la corrida." if prices.verified else "**NO VERIFICADOS**."),
        f"- Lo no juzgado cuenta grado 0, que es el supuesto estándar del *pooling*. Por eso "
        f"`no juzgado@{CUTOFF}` se publica por configuración: una fila con buena parte de su "
        f"top-{CUTOFF} sin juzgar es visiblemente no comparable, no silenciosamente injusta.",
        "",
    ]

    if report.cag:
        cag = report.cag
        lines += [
            "## `v0-cag` — el catálogo entero en el contexto",
            "",
            "Medición **fechada y no reproducible bit a bit**: llama a un modelo de lenguaje, y "
            "ni a temperatura 0 devuelve lo mismo dos veces. No es una fila que se re-ejecute "
            "en cada corrida.",
            "",
            f"- Modelo: `{cag['model']}` · fecha: {cag['measured_at']}",
            f"- Catálogo compactado: **{cag['tokens']} tokens** para "
            f"{cag['documents_total'] - cag['documents_omitted']} de "
            f"{cag['documents_total']} productos "
            f"(presupuesto {cag['budget_tokens']}, omitidos **{cag['documents_omitted']}**).",
            f"- Coste por consulta: **${cag['cost_per_query_usd']:.6f}**.",
            f"- Recall@5 sobre las {cag['queries']} consultas sin anclaje léxico: "
            f"**{_fmt(cag['recall_at_5_capped'])}**.",
            "",
            "| catálogo | tokens | ¿cabe? |",
            "|---:|---:|---|",
        ]
        for point in cag["scale"]:
            lines.append(
                f"| {point['documents']} | {point['tokens']} | "
                f"{'sí' if point['fits'] else '**no**'} |"
            )
        # The curve is three sampled sizes and they can all fit, so the wall has to be named
        # rather than left implicit in a column of «sí». It is the figure the requirement asks
        # for — «up to the point where it no longer fits» — and the one that makes the row an
        # argument about scale instead of a snapshot of today's catalogue.
        lines += [
            "",
            f"El contexto **deja de caber en {cag['breaks_at_documents']} productos** con el "
            f"presupuesto de {cag['budget_tokens']} tokens. La recuperación no tiene ese techo: "
            "su coste por consulta no se mueve con el tamaño del catálogo.",
            "",
        ]

    if report.notes:
        lines += ["## Notas", "", *(f"- {note}" for note in report.notes), ""]
    return "\n".join(lines)


def write(report: Report, *, title: str, name: str, out_dir: Path | None = None) -> Path:
    """Write the Markdown and the per-query JSONL. Always, and without a database."""
    target_dir = out_dir or RESULTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "runs").mkdir(parents=True, exist_ok=True)

    detail = target_dir / "runs" / f"{report.run_id}.jsonl"
    with detail.open("w", encoding="utf-8", newline="\n") as handle:
        for item in report.configs:
            for case in item.cases:
                handle.write(
                    json.dumps(
                        {
                            "run_id": report.run_id,
                            "config_id": item.config_id,
                            "query_id": case.query_id,
                            **case.as_dict(),
                            "ranked": list(item.ranked.get(case.query_id, ())),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    markdown = target_dir / name
    markdown.write_text(render_markdown(report, title=title), encoding="utf-8")
    return markdown
