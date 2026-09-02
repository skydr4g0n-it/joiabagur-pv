"""Measure the retriever against the live index. C20 measured reach; C21 compares configurations.

`python -m jbg_ai.retrieval measure` — reach of the synonym dictionary (C20).
`python -m jbg_ai.retrieval compare` — vector-only against lexical-only against the fused
default over the same queries (C21).

Both are read-only and a development aid rather than a gate: they skip cleanly when no
database (or, for `compare`, no embedding key) is reachable, and no unit test depends on
either. A real evaluation CLI with graded relevance is C24; starting one here would duplicate
the home of the same kind of report.

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
from jbg_ai.retrieval.fusion import RankedList, fuse
from jbg_ai.retrieval.lexical import (
    EXPANDED_LIST,
    TYPED_LIST,
    build_fragments,
    compose_group_fragments,
    expanded_request,
    typed_request,
)
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
COMPARISON_REPORT_NAME = "c21-fusion-configuration-comparison.md"
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
    """Return the SQL fragment and its parameters. Terms never touch the SQL text.

    The safe shape now lives in `retrieval/lexical.py`, which the serving branch uses. This
    keeps the **conjunction** between groups on purpose: it is the composition the C20 reach
    report measured, and `c20-query-expansion-reach.md` would stop being comparable with its
    own earlier runs if the operator changed underneath it. C21 serves with `||` plus
    coordination instead, for the reason recorded in `lexical.py`.
    """
    groups, params = compose_group_fragments(expanded.groups, placeholder=lambda _name: "%s")
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


#: The three arms C21's design compares, as `(name, w_typed, w_expanded, w_vector)`. The
#: fused default is the one the service ships; the other two are its endpoints, so the report
#: shows what fusing bought and what it cost against each branch alone.
COMPARISON_ARMS: tuple[tuple[str, float, float, float], ...] = (
    ("vector-only", 0.0, 0.0, 1.0),
    ("lexical-only", 0.5, 0.5, 0.0),
    ("fused-default", 0.5, 0.5, 0.33),
)

#: Recorded operator queries, read from the .NET side's telemetry table. Absent or empty is a
#: normal outcome and never a failure: the curated list is the floor of this report.
_RECORDED_QUERIES = """
SELECT DISTINCT "SearchText"
FROM public."ProductSearchEvents"
WHERE "SearchText" IS NOT NULL AND length(trim("SearchText")) > 0
ORDER BY 1
LIMIT 50
"""

_VECTOR_SQL = """
SELECT product_id, piece_type, materials
FROM ai.product_document
WHERE embedding IS NOT NULL
  AND is_active IS TRUE
  AND (embedding_version LIKE %(prefix)s OR embedding_model = %(model)s)
  AND embedding <=> %(q)s::vector <= %(threshold)s
ORDER BY embedding <=> %(q)s::vector ASC
LIMIT %(depth)s
"""

_LEXICAL_SQL = """
SELECT product_id, piece_type, materials
FROM ai.product_document
WHERE is_active IS TRUE
  AND tsv @@ {match}
ORDER BY ({coordination}) DESC, ts_rank(tsv, {match}) DESC
LIMIT %(depth)s
"""


@dataclass(frozen=True)
class ComparisonConfig:
    """What the comparison needs, and nothing else.

    Deliberately **not** `Settings`: that demands `APP_ENV`, `SERVICE_VERSION` and
    `JWT_SECRET`, which are the serving profile and have nothing to do with measuring. The
    local credentials live in `backend/.env`, which carries only the `JPV_*` keys, so
    requiring the profile made the CLI skip on the one machine that can run it. Same rule as
    `measure`: a development aid reads what it uses.
    """

    embedding_api_key: str | None
    embedding_model: str | None
    embedding_base_url: str | None
    rrf_k: int
    branch_depth: int
    distance_threshold: float

    @classmethod
    def from_env(cls) -> "ComparisonConfig":
        import os

        from jbg_ai.config.settings import FUSION_DEFAULTS

        def _number(name: str, default, cast):
            raw = os.environ.get(name)
            if raw is None or not raw.strip():
                return default
            try:
                return cast(raw)
            except ValueError as exc:
                raise MeasurementUnavailable(f"{name} is not a number: {raw!r}") from exc

        return cls(
            embedding_api_key=os.environ.get("JPV_EMBEDDING_API_KEY"),
            embedding_model=os.environ.get("JPV_EMBEDDING_MODEL"),
            embedding_base_url=os.environ.get("JPV_EMBEDDING_BASE_URL"),
            rrf_k=_number("JPV_RRF_K", FUSION_DEFAULTS["jpv_rrf_k"], int),
            branch_depth=_number("JPV_BRANCH_DEPTH", FUSION_DEFAULTS["jpv_branch_depth"], int),
            distance_threshold=_number("JPV_RETRIEVAL_DISTANCE_THRESHOLD", 0.65, float),
        )


@dataclass(frozen=True)
class ArmScore:
    """Hits in the top ten for one query under one configuration."""

    arm: str
    hits: int
    returned: int


@dataclass(frozen=True)
class QueryComparison:
    query: str
    source: str
    expected_type: str | None
    expected_materials: tuple[str, ...]
    arms: tuple[ArmScore, ...]


@dataclass(frozen=True)
class ComparisonReport:
    corpus_size: int
    model: str
    k: int
    depth: int
    threshold: float
    queries: tuple[QueryComparison, ...]
    recorded_error: str | None = None


def _rubric(expanded: ExpandedQuery) -> tuple[str | None, tuple[str, ...]]:
    """The rubric C20 used, read off the query: right `piece_type` **and** right material.

    Stated plainly because it is also the lexical branch's own objective function: `doc_text`
    carries canonical `Tipo:` and `Materiales:` lines and the expansion aims at them, so this
    score rewards whoever matches those lines by construction. It fixes a starting point, not
    a verdict — the judge is C24's graded golden set with a paraphrase category.
    """
    piece = next((m.canonical for m in expanded.matched if m.field == "piece_type"), None)
    materials = tuple(m.canonical for m in expanded.matched if m.field == "materials")
    return piece, materials


def _is_hit(row: dict, expected_type: str | None, expected_materials: tuple[str, ...]) -> bool:
    if expected_type is not None and row.get("piece_type") != expected_type:
        return False
    if expected_materials:
        held = set(row.get("materials") or ())
        if not held & set(expected_materials):
            return False
    return True


def _lexical_rows(cursor, request, *, depth: int) -> list[dict]:
    fragments = build_fragments(request, placeholder=lambda name: f"%({name})s")
    sql = _LEXICAL_SQL.format(match=fragments.match, coordination=fragments.coordination)
    cursor.execute(sql, {**fragments.params, "depth": depth})
    return [
        {"product_id": row[0], "piece_type": row[1], "materials": row[2]}
        for row in cursor.fetchall()
    ]


def _vector_rows(cursor, vector, *, model: str, threshold: float, depth: int) -> list[dict]:
    literal = "[" + ",".join(str(value) for value in vector) + "]"
    cursor.execute(
        _VECTOR_SQL,
        {
            "prefix": f"{model}:1536%",
            "model": model,
            "q": literal,
            "threshold": threshold,
            "depth": depth,
        },
    )
    return [
        {"product_id": row[0], "piece_type": row[1], "materials": row[2]}
        for row in cursor.fetchall()
    ]


def _recorded_queries(cursor) -> tuple[tuple[str, ...], str | None]:
    """Read what operators actually typed. Returns the queries and why there are none.

    The table belongs to the .NET side and may legitimately not be there, so absence is not a
    failure. It must not be **silent** either: the first version swallowed the exception and
    returned an empty tuple, so a wrong column name produced a report that claimed to cover
    recorded queries while covering none. The reason travels back and is printed and written
    into the report.
    """
    try:
        cursor.execute(_RECORDED_QUERIES)
        return tuple(str(row[0]).strip() for row in cursor.fetchall()), None
    except Exception as exc:  # noqa: BLE001 - absence is a normal outcome, never a failure
        cursor.connection.rollback()
        return (), f"{type(exc).__name__}: {str(exc).splitlines()[0]}"


def _embed_queries(
    texts: Sequence[str], config: ComparisonConfig
) -> tuple[dict[str, list[float]], str]:
    import asyncio

    from jbg_ai.indexing.constants import DEFAULT_EMBEDDING_MODEL
    from jbg_ai.indexing.embeddings import LiteLlmEmbeddingClient
    from jbg_ai.indexing.errors import EmbeddingError

    if not config.embedding_api_key:
        raise MeasurementUnavailable(
            "JPV_EMBEDDING_API_KEY is required to measure the vector arm"
        )
    client = LiteLlmEmbeddingClient(
        api_key=config.embedding_api_key,
        model=config.embedding_model or DEFAULT_EMBEDDING_MODEL,
        base_url=config.embedding_base_url,
        max_attempts=1,
    )
    try:
        result = asyncio.run(client.embed(list(texts)))
    except EmbeddingError as exc:
        raise MeasurementUnavailable(f"the embedding provider is not reachable: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - litellm raises its own hierarchy, not ours
        # A development aid must skip, never traceback. litellm surfaces transport failures as
        # `InternalServerError` / `APIConnectionError`, none of which are `EmbeddingError`, so
        # catching only ours turned an unreachable provider into a crash. Found by running it.
        raise MeasurementUnavailable(
            f"the embedding provider call failed ({type(exc).__name__}): {exc}"
        ) from exc
    return dict(zip(texts, result.vectors, strict=True)), client.model_id


def build_comparison(
    cursor, config: ComparisonConfig, dictionary: SynonymDictionary
) -> ComparisonReport:
    """Score every arm over the curated and the recorded queries. Read-only throughout."""
    cursor.execute(_COUNT_ACTIVE)
    corpus_size = int(cursor.fetchone()[0])

    recorded_all, recorded_error = _recorded_queries(cursor)
    recorded = tuple(q for q in recorded_all if q not in CURATED_QUERIES)
    catalogue = [(text, "curated") for text in CURATED_QUERIES]
    catalogue += [(text, "recorded") for text in recorded]

    vectors, model = _embed_queries([text for text, _ in catalogue], config)
    k = config.rrf_k
    depth = config.branch_depth
    threshold = config.distance_threshold

    comparisons: list[QueryComparison] = []
    for text, source in catalogue:
        expanded = expand_query(text, enabled=True, dictionary=dictionary)
        expected_type, expected_materials = _rubric(expanded)

        typed = _lexical_rows(cursor, typed_request(text), depth=depth)
        widened = _lexical_rows(cursor, expanded_request(expanded), depth=depth)
        vector = _vector_rows(
            cursor, vectors[text], model=model, threshold=threshold, depth=depth
        )
        rows = {row["product_id"]: row for row in (*typed, *widened, *vector)}

        arms: list[ArmScore] = []
        for name, w_typed, w_expanded, w_vector in COMPARISON_ARMS:
            fused = fuse(
                [
                    RankedList(TYPED_LIST, w_typed, [row["product_id"] for row in typed]),
                    RankedList(EXPANDED_LIST, w_expanded, [row["product_id"] for row in widened]),
                    RankedList("vector", w_vector, [row["product_id"] for row in vector]),
                ],
                k=k,
                depth=depth,
            )
            top = [entry for entry in fused if entry.score > 0][:10]
            arms.append(
                ArmScore(
                    arm=name,
                    hits=sum(
                        1
                        for entry in top
                        if _is_hit(rows[entry.key], expected_type, expected_materials)
                    ),
                    returned=len(top),
                )
            )

        comparisons.append(
            QueryComparison(
                query=text,
                source=source,
                expected_type=expected_type,
                expected_materials=expected_materials,
                arms=tuple(arms),
            )
        )

    return ComparisonReport(
        corpus_size=corpus_size,
        model=model,
        k=k,
        depth=depth,
        threshold=threshold,
        queries=tuple(comparisons),
        recorded_error=recorded_error,
    )


def render_comparison(report: ComparisonReport, *, measured_at: datetime) -> str:
    arm_names = [name for name, *_ in COMPARISON_ARMS]
    lines = [
        "# C21 — hits at ten by fusion configuration",
        "",
        f"Measured {measured_at.date().isoformat()} against {report.corpus_size} live rows of "
        f"`ai.product_document`, read-only, with `{report.model}`.",
        "",
        f"`k` = {report.k}, branch depth = {report.depth} (symmetric across the three lists), "
        f"distance threshold = {report.threshold}.",
        "",
        "**The rubric is the lexical branch's own objective function.** A hit is a top-ten "
        "result with the piece type and a material the query named, read off the expansion's "
        "resolved terms. `doc_text` carries canonical `Tipo:` and `Materiales:` lines and the "
        "expansion aims at them, so a lexical arm scores well here by construction. These "
        "figures fix a **starting point, not a verdict**: the judge is C24's graded golden set "
        "with a paraphrase category, where the vector branch wins what this rubric cannot see.",
        "",
        "Queries marked `recorded` come from the .NET telemetry table; the rest are the curated "
        "list C20 used. Both are developer-written, which is the limitation the README declares.",
        "",
        *(
            [
                f"> **The recorded queries could not be read**: `{report.recorded_error}`. "
                "This report covers the curated list only, and says so rather than letting an "
                "empty set look like a complete one.",
                "",
            ]
            if report.recorded_error
            else []
        ),
        "| query | source | expected | " + " | ".join(arm_names) + " |",
        "|---|---|---|" + "---:|" * len(arm_names),
    ]
    for item in report.queries:
        expected = "/".join(
            part for part in (item.expected_type or "", "+".join(item.expected_materials)) if part
        )
        scores = " | ".join(f"{arm.hits}/{arm.returned}" for arm in item.arms)
        lines.append(f"| `{item.query}` | {item.source} | {expected or '-'} | {scores} |")

    totals = {
        name: sum(arm.hits for item in report.queries for arm in item.arms if arm.arm == name)
        for name in arm_names
    }
    ceiling = 10 * len(report.queries)
    lines += [
        "",
        "## Totals",
        "",
        "| configuration | hits | of |",
        "|---|---:|---:|",
    ]
    for name in arm_names:
        lines.append(f"| {name} | {totals[name]} | {ceiling} |")
    lines.append("")
    return "\n".join(lines)


def run_comparison(out_dir: Path | None = None) -> Path:
    """Compare the arms and write the report. Skips rather than fails without a dependency."""
    target_dir = out_dir or RESULTS_DIR
    config = ComparisonConfig.from_env()
    dictionary = load_query_dictionary()
    with _connect() as connection:
        connection.read_only = True
        with connection.cursor() as cursor:
            report = build_comparison(cursor, config, dictionary)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / COMPARISON_REPORT_NAME
    target.write_text(
        render_comparison(report, measured_at=datetime.now(tz=UTC)), encoding="utf-8"
    )
    return target


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
    compare = sub.add_parser("compare", help="Compare fusion configurations over the live index")
    compare.add_argument("--out", default=None, help="Directory for the report")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command not in ("measure", "compare"):
        parser.error("unknown command")
    runner = run_measurement if args.command == "measure" else run_comparison
    try:
        target = runner(Path(args.out) if args.out else None)
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

