"""CLI of the knowledge corpus: `python -m jbg_ai.knowledge <comando>`. Delivered by C23.

Everything here runs **without a database and without a provider**. Indexing is the one
operation that needs both, and it lives where the other two drains live:
`python -m jbg_ai.indexing sync-knowledge`.

- `validate` — the seven authoring rules plus the coverage invariant. The pre-commit gate
- `stats`    — the composition of the corpus, which is the figure the README publishes
- `sidecar`  — write `_corpus.meta.json`, sealing how the corpus was produced
- `measure`  — Recall@3, MRR and abstention over the fixture
- `calibrate` — the threshold curve, for the rule of D8
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

from jbg_ai.config.settings import KNOWLEDGE_DEFAULTS
from jbg_ai.knowledge.constants import (
    GENERATOR_VERSION,
    PROMPT_VERSION,
    SIDECAR_PATH,
)
from jbg_ai.knowledge.corpus import KnowledgeCorpus, load_corpus, validate_corpus
from jbg_ai.knowledge.errors import KnowledgeError
from jbg_ai.knowledge.measure import calibrated_threshold, measure, sweep
from jbg_ai.knowledge.sizing import ring_size_table

#: Every document but one was written by an assistant against the eight versioned block
#: prompts. `material-plata` was written by hand first, as the pattern the eight prompts
#: quote. Recorded here and not per row: it is a property of how the corpus was produced.
GENERATION_MODEL = "anthropic/claude-opus-5"
HAND_WRITTEN = ("material-plata",)

DEFAULT_SWEEP = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95)


def _stats_payload(corpus: KnowledgeCorpus) -> dict[str, object]:
    by_scope = corpus.counts_by_claim_scope()
    total_sections = corpus.section_count
    return {
        "document_count": len(corpus),
        "section_count": total_sections,
        "counts_by_doc_type": corpus.counts_by_doc_type(),
        "counts_by_claim_scope": by_scope,
        "ratios_by_claim_scope": {
            scope: round(count * 100 / total_sections, 1) for scope, count in by_scope.items()
        },
    }


def _sidecar_payload(corpus: KnowledgeCorpus, *, generated_at: str) -> dict[str, object]:
    return {
        "generator_version": GENERATOR_VERSION,
        "model": GENERATION_MODEL,
        "prompt_version": PROMPT_VERSION,
        "generated_at": generated_at,
        "authorship": (
            "Redactado con asistencia de un LLM contra los ocho prompts de bloque "
            "versionados en ai-service/prompts/knowledge/v1/, y revisado a mano bloque a "
            "bloque. El corpus es sintético: los textos comerciales de la joyería nunca "
            "llegaron. La verificación de citas es estructural, no semántica."
        ),
        "hand_written_documents": list(HAND_WRITTEN),
        **_stats_payload(corpus),
    }


def _cmd_validate(_: argparse.Namespace) -> int:
    corpus = validate_corpus()
    table = ring_size_table(corpus)
    sys.stdout.write(
        f"ok: {len(corpus)} documentos, {corpus.section_count} secciones, "
        f"{len(table)} filas en la tabla de tallas\n"
    )
    return 0


def _cmd_stats(_: argparse.Namespace) -> int:
    sys.stdout.write(json.dumps(_stats_payload(load_corpus()), indent=2, ensure_ascii=False) + "\n")
    return 0


def _cmd_sidecar(args: argparse.Namespace) -> int:
    corpus = validate_corpus()
    generated_at = args.generated_at or datetime.now(tz=UTC).isoformat()
    payload = _sidecar_payload(corpus, generated_at=generated_at)
    SIDECAR_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    sys.stdout.write(f"escrito {SIDECAR_PATH}\n")
    return 0


def _cmd_measure(args: argparse.Namespace) -> int:
    hybrid = measure(threshold=args.threshold, hybrid_enabled=True, label="híbrido")
    sys.stdout.write(hybrid.format() + "\n")
    if args.compare:
        vector = measure(threshold=args.threshold, hybrid_enabled=False, label="vectorial solo")
        sys.stdout.write(vector.format() + "\n")
        delta = (hybrid.recall_at_3 - vector.recall_at_3) * 100
        sys.stdout.write(
            f"delta Recall@3 híbrido - vectorial = {delta:+.1f} pp · "
            f"delta MRR = {hybrid.mrr - vector.mrr:+.3f}\n"
        )
    return 0


def _cmd_calibrate(args: argparse.Namespace) -> int:
    values = args.thresholds or list(DEFAULT_SWEEP)
    reports = sweep(values, hybrid_enabled=not args.vector_only)
    for report in reports:
        sys.stdout.write(
            f"threshold={report.threshold:.2f}  Recall@3={report.recall_at_3 * 100:5.1f}%  "
            f"MRR={report.mrr:.3f}  abstención={report.abstention_rate * 100:5.1f}%  "
            f"fallos={len(report.misses)}  citas_fuera_de_dominio={len(report.false_citations)}\n"
        )
    best = calibrated_threshold(reports)
    if best is None:
        sys.stdout.write(
            "ningún umbral del barrido mantiene en cero las fuera de dominio sin perder "
            "ninguna con respuesta\n"
        )
        return 1
    sys.stdout.write(f"calibrado: JPV_KNOWLEDGE_DISTANCE_THRESHOLD={best.threshold:.2f}\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m jbg_ai.knowledge")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="Las siete reglas de autoría y la cobertura del vocabulario")
    sub.add_parser("stats", help="Recuento por doc_type y por claim_scope")

    sidecar = sub.add_parser("sidecar", help="Escribir _corpus.meta.json")
    sidecar.add_argument("--generated-at", help="Instante ISO-8601 a sellar (por defecto, ahora)")

    measure_parser = sub.add_parser("measure", help="Recall@3, MRR y tasa de abstención")
    # The KNOWLEDGE default, never the product one: measuring this corpus at the cutoff
    # calibrated for 40-120-word product documents answers a question nobody asked, and a
    # bare `measure` is exactly how somebody would ask it.
    measure_parser.add_argument(
        "--threshold",
        type=float,
        default=KNOWLEDGE_DEFAULTS["jpv_knowledge_distance_threshold"],
    )
    measure_parser.add_argument(
        "--compare", action="store_true", help="Correr también vectorial solo y dar la diferencia"
    )

    calibrate = sub.add_parser("calibrate", help="Barrido de umbral con la regla de D8")
    calibrate.add_argument("--thresholds", type=float, nargs="*")
    calibrate.add_argument("--vector-only", action="store_true")

    args = parser.parse_args(list(argv) if argv is not None else None)
    handlers = {
        "validate": _cmd_validate,
        "stats": _cmd_stats,
        "sidecar": _cmd_sidecar,
        "measure": _cmd_measure,
        "calibrate": _cmd_calibrate,
    }
    try:
        return handlers[args.command](args)
    except KnowledgeError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
