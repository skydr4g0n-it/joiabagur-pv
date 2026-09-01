"""Measure the synonym dictionary's reach over the live index. Delivered by C20.

`python -m jbg_ai.retrieval measure` — read-only, and a development aid rather than a
gate: it skips cleanly when no database is reachable, and no unit test depends on it.

This is the one place in C20 that composes a `tsquery`, because measuring requires it.
The composition is the safe one — `plainto_tsquery` per surface form, OR-ed with `||`
inside a group and AND-ed with `&&` between groups — so terms travel as parameters and
no query syntax is ever concatenated. C21 inherits this shape; the library itself still
returns groups, because `ts_rank` cannot tell the operator's own word from a synonym
once they are OR-ed into a single query.

Groups made only of stop words need no special handling: PostgreSQL absorbs an empty
`tsquery` on either side of `&&`, verified against this index.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from jbg_ai.data.paths import AI_SERVICE_ROOT
from jbg_ai.retrieval.synonyms import (
    OVERLAY_RESOURCE,
    ExpandedQuery,
    SynonymDictionary,
    expand_query,
    load_overlay_from_path,
    load_query_dictionary,
)

RESULTS_DIR = AI_SERVICE_ROOT / "evals" / "results"
REPORT_NAME = "c20-query-expansion-reach.md"
OVERLAY_PATH = Path(__file__).resolve().parent / OVERLAY_RESOURCE

#: Curated, not sampled: `ProductSearchEvents` holds 31 rows and 12 texts, all written
#: by the developer in canonical vocabulary, so there is no observed demand to draw on.
#: This limitation is declared in the README rather than papered over.
CURATED_QUERIES: tuple[str, ...] = (
    "gargantilla dorada",
    "collares de plata",
    "criollas de oro",
    "sortija de plata",
    "aros de plata",
    "brazalete de cuero",
    "pendiente de oro",
    "bano de oro",
    "aro de dedo de plata",
    "anillo pequeno",
    "dije de plata",
    "alfiler dorado",
)

_COUNT_ACTIVE = "SELECT count(*) FROM ai.product_document WHERE is_active IS TRUE"

_MATCH_TEMPLATE = (
    "SELECT count(*) FROM ai.product_document WHERE is_active IS TRUE AND tsv @@ ({query})"
)


@dataclass(frozen=True)
class QueryReach:
    query: str
    plain: int
    expanded: int
    matched_terms: int

    @property
    def gained(self) -> int:
        return self.expanded - self.plain


@dataclass(frozen=True)
class FormReach:
    field: str
    canonical: str
    form: str
    alone: int
    with_class: int

    @property
    def gained(self) -> int:
        return self.with_class - self.alone


@dataclass(frozen=True)
class Report:
    corpus_size: int
    queries: tuple[QueryReach, ...]
    forms: tuple[FormReach, ...]


class MeasurementUnavailable(RuntimeError):
    """No database to measure against. A skip, never a failure."""


def compose_tsquery(expanded: ExpandedQuery) -> tuple[str, list[str]]:
    """Return the SQL fragment and its parameters. Terms never touch the SQL text."""
    groups: list[str] = []
    params: list[str] = []
    for group in expanded.groups:
        alternatives = " || ".join("plainto_tsquery('spanish', %s)" for _ in group)
        groups.append(f"({alternatives})")
        params.extend(group)
    if not groups:
        return "plainto_tsquery('spanish', %s)", [""]
    return " && ".join(groups), params


def _count(cursor, expanded: ExpandedQuery) -> int:
    fragment, params = compose_tsquery(expanded)
    cursor.execute(_MATCH_TEMPLATE.format(query=fragment), params)
    return int(cursor.fetchone()[0])


def _count_plain(cursor, text: str) -> int:
    cursor.execute(
        _MATCH_TEMPLATE.format(query="plainto_tsquery('spanish', %s)"),
        [text],
    )
    return int(cursor.fetchone()[0])


def build_report(cursor, dictionary: SynonymDictionary) -> Report:
    cursor.execute(_COUNT_ACTIVE)
    corpus_size = int(cursor.fetchone()[0])

    queries: list[QueryReach] = []
    for text in CURATED_QUERIES:
        expanded = expand_query(text, enabled=True, dictionary=dictionary)
        queries.append(
            QueryReach(
                query=text,
                plain=_count_plain(cursor, text),
                expanded=_count(cursor, expanded),
                matched_terms=len(expanded.matched),
            )
        )

    overlay = load_overlay_from_path(OVERLAY_PATH)
    forms: list[FormReach] = []
    for entry in overlay.get("classes") or ():
        key = (str(entry["field"]), str(entry["canonical"]))
        for form in entry.get("forms") or ():
            surface = str(form)
            expanded = expand_query(surface, enabled=True, dictionary=dictionary)
            forms.append(
                FormReach(
                    field=key[0],
                    canonical=key[1],
                    form=surface,
                    alone=_count_plain(cursor, surface),
                    with_class=_count(cursor, expanded),
                )
            )
    return Report(corpus_size=corpus_size, queries=tuple(queries), forms=tuple(forms))


def render_markdown(report: Report, *, measured_at: datetime) -> str:
    lines = [
        "# C20 — reach of the query expansion dictionary",
        "",
        f"Measured {measured_at.date().isoformat()} against {report.corpus_size} live rows of "
        "`ai.product_document`, read-only.",
        "",
        "The queries are **curated, not sampled**: `public.\"ProductSearchEvents\"` holds 31 rows "
        "and 12 distinct texts, all written by the developer in canonical vocabulary, so there is "
        "no observed demand to draw on. C24 re-measures this with graded relevance.",
        "",
        "Counts are candidate sets, not precision. What the expansion is worth in ranking terms "
        "is nDCG@5 on the golden set, which is C24's job and the reason the flag exists.",
        "",
        "## Operator queries",
        "",
        "| query | without expansion | with expansion | gained | terms resolved |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in report.queries:
        lines.append(
            f"| `{item.query}` | {item.plain} | {item.expanded} | "
            f"{item.gained:+d} | {item.matched_terms} |"
        )
    lines += [
        "",
        "## Overlay entries",
        "",
        "| field | canonical | overlay form | form alone | with its class | gained |",
        "|---|---|---|---:|---:|---:|",
    ]
    for form in sorted(report.forms, key=lambda item: -item.gained):
        lines.append(
            f"| {form.field} | {form.canonical} | `{form.form}` | "
            f"{form.alone} | {form.with_class} | {form.gained:+d} |"
        )
    lines.append("")
    return "\n".join(lines)


def _connect():
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - psycopg is a hard dependency
        raise MeasurementUnavailable("psycopg is not installed") from exc

    from jbg_ai.data.errors import IngestError
    from jbg_ai.data.ingest import pg_connect_kwargs_from_env

    try:
        kwargs = pg_connect_kwargs_from_env()
    except IngestError as exc:
        raise MeasurementUnavailable(str(exc)) from exc
    try:
        return psycopg.connect(**kwargs)
    except psycopg.Error as exc:
        raise MeasurementUnavailable(f"cannot reach the index: {exc}") from exc


def run_measurement(out_dir: Path | None = None) -> Path:
    """Measure and write the report. Raises `MeasurementUnavailable` when there is no index."""
    target_dir = out_dir or RESULTS_DIR
    dictionary = load_query_dictionary()
    with _connect() as connection:
        connection.read_only = True
        with connection.cursor() as cursor:
            report = build_report(cursor, dictionary)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / REPORT_NAME
    target.write_text(render_markdown(report, measured_at=datetime.now(tz=UTC)), encoding="utf-8")
    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m jbg_ai.retrieval")
    sub = parser.add_subparsers(dest="command", required=True)
    measure = sub.add_parser("measure", help="Measure the dictionary reach over the live index")
    measure.add_argument("--out", default=None, help="Directory for the report")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command != "measure":
        parser.error("unknown command")
    try:
        target = run_measurement(Path(args.out) if args.out else None)
    except MeasurementUnavailable as exc:
        sys.stdout.write(f"skipping measurement: {exc}\n")
        return 0
    sys.stdout.write(f"wrote {target}\n")
    return 0


def run_module(argv: Sequence[str] | None = None) -> int:
    """Process entry point. Loads `backend/.env`, the single place local credentials live.

    It lives here and not in `main` for the same reason it does in `indexing/cli.py`:
    tests call `main`, and `support.settings.build_settings` pins the optional fields to
    `None` precisely so an exported credential cannot make an "absent configuration"
    case stop failing.
    """
    from jbg_ai.data.envload import load_local_env

    load_local_env()
    return main(argv)

