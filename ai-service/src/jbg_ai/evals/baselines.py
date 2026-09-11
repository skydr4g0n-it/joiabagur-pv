"""The two lexical baselines, replicating .NET semantics over the `ai` schema. C24.

Both statements read `ai.product_document` and nothing else. Reading `public."Products"` is not
an option — the retrieval port declares that implementations must not read `public` — so the
fidelity has to come from composing the same TEXT the .NET searchers compose, not from querying
the same table.

That constraint is what makes `v0-fts` interesting rather than mechanical. See
`_DESCRIPTION_EXPRESSION`.

Neither baseline is scoped to a point of sale, and both .NET originals are. The golden set is
labelled unscoped by a decision taken in the previous change, so that retrieval quality and
assortment coverage are not compressed into one number; the consequence — that what the
prefilter costs in recall is not measured here — is declared in the report rather than hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.evals.errors import EvaluationUnavailable

#: The line of `source-text/v1` that carries what .NET calls `Product.Description`.
#:
#: `ai.product_document` has no `description` column. It has `doc_text`, which is the canonical
#: rendering and also carries `Tipo:`, `Materiales:`, `Piedra:`, `Colores:`, `Estilo:` and the
#: rest — every field the enrichment extracted. A `to_tsvector` over `doc_text` would therefore
#: not replicate the degraded .NET searcher: it would be a strict UPPER BOUND on it, matching
#: queries through fields that searcher has never seen, and the baseline would flatter itself.
#:
#: So the description is pulled back out by its prefix. That makes `Descripción: ` a CONTRACT of
#: the renderer rather than a formatting detail, and `test_v0_fts_composes_only_over_the_dotnet_
#: columns` asserts it: if `build_source_text` stops emitting the line, a test fails instead of
#: this baseline quietly becoming a search over the empty string.
#:
#: `(?n)` makes `^` and `$` match at line boundaries and stops `.` from crossing a newline, so
#: the expression takes exactly one line. `coalesce` to the empty string mirrors .NET's
#: `(Description ?? string.Empty)` for the 25 live documents that carry no description.
DESCRIPTION_PREFIX = "Descripción: "
_DESCRIPTION_EXPRESSION = (
    "coalesce(substring(d.doc_text from '(?n)^Descripción: (.*)$'), '')"
)

#: `name ‖ ' ' ‖ sku ‖ ' ' ‖ description`, exactly the concatenation the .NET expression tree
#: builds — including the code, which is there so a degraded search for a code still finds its
#: product, "the first thing an operator types when nothing else works".
_FTS_DOCUMENT = f"d.name || ' ' || d.sku || ' ' || {_DESCRIPTION_EXPRESSION}"

#: Ordering: relevance, then name, exactly as .NET does — plus `product_id` for the same reason
#: the live path now carries it. `ts_rank` ties are frequent and a tie the `LIMIT` cuts through
#: would otherwise make two identical runs disagree.
V0_FTS_SQL = f"""
SELECT d.product_id,
       d.sku,
       ts_rank(to_tsvector('spanish', {_FTS_DOCUMENT}),
               websearch_to_tsquery('spanish', :tsquery)) AS rank
FROM ai.product_document d
WHERE d.is_active IS TRUE
  AND to_tsvector('spanish', {_FTS_DOCUMENT})
      @@ websearch_to_tsquery('spanish', :tsquery)
ORDER BY rank DESC, d.name ASC, d.product_id ASC
LIMIT :depth
"""

#: `p.Name.Contains(query, OrdinalIgnoreCase)` — the WHOLE query as a substring, never
#: tokenised — plus `p.SKU.ToUpperInvariant() == query.ToUpperInvariant()`, alphabetical.
#: `position(lower(:q) in lower(d.name)) > 0` is the case-insensitive substring test; it is
#: deliberately not `unaccent`, because the original is not accent-insensitive either.
V0_NOMBRE_SQL = """
SELECT d.product_id,
       d.sku,
       (upper(d.sku) = upper(:q)) AS sku_exact
FROM ai.product_document d
WHERE d.is_active IS TRUE
  AND (upper(d.sku) = upper(:q) OR position(lower(:q) in lower(d.name)) > 0)
ORDER BY sku_exact DESC, d.name ASC, d.product_id ASC
LIMIT :depth
"""

#: Below this the .NET service returns an empty list without querying anything. Replicated
#: because a baseline that answered a one-character query would be measuring a searcher nobody
#: ships.
MIN_QUERY_LENGTH = 2

#: Whitespace split, single characters dropped, at most sixteen distinct terms, joined with
#: ` OR `. Stop words are deliberately NOT stripped: the Spanish configuration removes them
#: when it builds the query, and a second list maintained here would be one more thing to keep
#: in step with the one the database actually applies.
MAX_TERMS = 16


@dataclass(frozen=True)
class BaselineHit:
    product_id: UUID
    sku: str
    score: float


def tokenize(query: str) -> list[str]:
    """The .NET tokeniser, term for term."""
    seen: set[str] = set()
    terms: list[str] = []
    for token in query.split():
        cleaned = token.strip()
        if len(cleaned) <= 1:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        terms.append(cleaned)
        if len(terms) == MAX_TERMS:
            break
    return terms


def websearch_terms(query: str) -> str:
    """Terms joined so that matching ANY of them is enough.

    Requiring all of them returns an empty list on every natural-language query, which is the
    defect this searcher exists to avoid — the .NET comment says exactly that, and the C21
    measurement quantified it: a strict conjunction leaves 7 of the 10 recorded operator
    queries matching zero documents.
    """
    return " OR ".join(tokenize(query))


async def run_v0_nombre(
    query: str, *, settings: Settings, depth: int
) -> list[BaselineHit]:
    """Exact code first, then names containing the whole query, alphabetically."""
    if len(query.strip()) < MIN_QUERY_LENGTH:
        return []
    rows = await _fetch(
        V0_NOMBRE_SQL, {"q": query.strip(), "depth": depth}, settings=settings
    )
    # Rank position IS the score here: the original has no relevance signal at all, so
    # inventing one would attribute to the baseline a capability it does not have.
    return [
        BaselineHit(
            product_id=UUID(str(row["product_id"])),
            sku=str(row["sku"]),
            score=1.0 if row["sku_exact"] else 0.0,
        )
        for row in rows
    ]


async def run_v0_fts(query: str, *, settings: Settings, depth: int) -> list[BaselineHit]:
    """Spanish full text over name, code and description, ordered by rank then name."""
    tsquery = websearch_terms(query)
    if not tsquery:
        return []
    rows = await _fetch(V0_FTS_SQL, {"tsquery": tsquery, "depth": depth}, settings=settings)
    return [
        BaselineHit(
            product_id=UUID(str(row["product_id"])),
            sku=str(row["sku"]),
            score=float(row["rank"]),
        )
        for row in rows
    ]


async def _fetch(sql: str, params: dict[str, object], *, settings: Settings) -> list[dict]:
    try:
        async with session_scope(settings) as session:
            return [dict(row) for row in (await session.execute(text(sql), params)).mappings()]
    except SQLAlchemyError as exc:
        raise EvaluationUnavailable(f"the index is not reachable: {exc}") from exc
