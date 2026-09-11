"""The golden set: files, model, and the composition check that refuses to load. C24.

The set lives in `ai-service/evals/golden/` and is versioned in git, never in the database.
That is a decision about **who may move the yardstick**: changing a query or a judgement has
to pass through code review, and a measurement taken last week stays interpretable against the
version it used, because every run records that version.

**Loading validates, and a violation is a refusal rather than a warning.** The structural risk
of this golden set is that it is written by the person who built the retriever, using the
vocabulary of the catalogue he also wrote — which would produce a set of `<tipo> de <material>`
queries that confirms the previous rubric by construction and arbitrates nothing. The
containment is not good intentions: it is the traceability matrix below, checked here, failing
the load when it is not met.

**Everything the check needs is in the files.** No database, no provider. Two facts that could
only come from the index — whether the lexical branch could reach a judged document, and which
origin that document belongs to — are frozen **into each judgement** when it is recorded, next
to the content hash that says which text it was judged against. Reading them back from a live
index instead would mean the set validated differently depending on when it was loaded, which
is the same class of defect as a measurement that cannot be repeated.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from jbg_ai.data.paths import AI_SERVICE_ROOT
from jbg_ai.enrichment.vocab import fold
from jbg_ai.evals.errors import GoldenSetError
from jbg_ai.retrieval.synonyms import (
    OVERLAY_RESOURCE,
    ClassKey,
    SynonymDictionary,
    expand_query,
    load_overlay_from_path,
    load_query_dictionary,
)

GOLDEN_DIR = AI_SERVICE_ROOT / "evals" / "golden"
QUERIES_FILE = "queries.jsonl"
JUDGEMENTS_FILE = "judgements.jsonl"
CRITERION_FILE = "criterion.md"
VECTORS_FILE = "query_vectors.jsonl"
PRICING_FILE = "pricing.yaml"

#: Bumped only when the SHAPE of these files changes. The rest of the version is the digest
#: of their content, so appending a judgement moves the version without anybody remembering to.
GOLDEN_SET_SCHEMA_VERSION = "1"

MAX_GRADE = 2
RELEVANT_FROM = 1
"""The binarisation rule, fixed once and applied to every configuration: a document is
relevant when its grade is at least the intermediate one. Declared here rather than passed
in, because a rule chosen per configuration is not a rule."""

#: Vocabulary fields whose coverage is high enough that resolving to them cannot be what makes
#: a query subjective. Measured as `doc_text` line coverage over the 1.168 live rows on
#: 2026-09-02 and re-read on 2026-09-07: `Tipo:` 99 %, `Materiales:` 89 %. `Piedra:` (54 %) is
#: deliberately NOT here: C21 left it explicitly undecided whether it should count for the
#: coordination, and the four stone queries of this set exist to produce the evidence. Putting
#: it on either side of this line would prejudge the answer this set is being built to give.
HIGH_COVERAGE_FIELDS = frozenset({"piece_type", "materials"})

#: Piece types that cover enough of the catalogue that naming one cannot be what selects the
#: answer — each is at least a tenth of the corpus, measured 2026-09-07 over the 1.168 live
#: rows: pendientes 275, anillo 268, pulsera 207, colgante 160, collar 138. This is what
#: "the piece type does not discriminate" means for the stone queries, made checkable.
#:
#: A constant of the harness and of nothing else. It governs which golden sets are accepted
#: and asserts no production default, which is the rule C23 paid for: a constant that did both
#: kept a test green while the defect shipped.
NON_DISCRIMINATING_PIECE_TYPES = frozenset(
    {"pendientes", "anillo", "pulsera", "colgante", "collar"}
)

CATEGORIES = (
    "descripcion-sin-anclaje",
    "variante-talla",
    "materiales",
    "piedra",
    "subjetiva",
    "sinonimos",
    "lexico-exacto",
    "fuera-de-dominio",
    "sustituto",
    "ambigua",
)

SYNONYM_KINDS = ("stemmer", "commercial", "bridge")

DATA_ORIGINS = ("real", "synthetic")

#: The traceability matrix: one row per dispute the set has to arbitrate, and the minimum that
#: makes it able to. The numbers come from the C24 exploration, where each is derived from a
#: measurement rather than chosen for roundness.
MINIMUM_UNANCHORED = 12
MINIMUM_SUBJECTIVE = 5
MINIMUM_STONE = 4
MINIMUM_SYNONYM_PER_KIND = 2
#: The category name a query carries when the catalogue cannot answer it at all.
OUT_OF_DOMAIN = "fuera-de-dominio"

#: How many out-of-domain queries the set must carry for an abstention rate to be a figure
#: anybody can act on. Raised from 5 to 20 by C25: with five, the only reachable acceptance
#: number is not credible, and a rule with two parameters fitted against five points is fitted
#: to five points. Growing the category costs no per-document labelling, because every
#: document is grade zero there by the annotation criterion.
MINIMUM_OUT_OF_DOMAIN = 20
MINIMUM_LEXICAL_LITERAL = 4
MINIMUM_JUDGED_QUERIES = 45
"""The hard floor of the composition. 48 is the target; below 45 the set stops covering the
disputes, and the exploration fixed the floor before any query was written."""

_TOKEN = re.compile(r"[0-9A-Za-zÀ-ÿ]+")


@dataclass(frozen=True)
class GoldenQuery:
    """One query of the set. `judged` false means declared but deliberately not labelled."""

    id: str
    text: str
    category: str
    in_tuning_set: bool
    judged: bool
    judged_depth: int | None = None
    isolates_stone: str | None = None
    synonym_kind: str | None = None
    literal_of: str | None = None
    note: str | None = None

    @classmethod
    def from_json(cls, payload: dict[str, Any], *, where: str) -> "GoldenQuery":
        try:
            return cls(
                id=str(payload["id"]),
                text=str(payload["text"]),
                category=str(payload["category"]),
                in_tuning_set=bool(payload["in_tuning_set"]),
                judged=bool(payload["judged"]),
                judged_depth=(
                    None if payload.get("judged_depth") is None else int(payload["judged_depth"])
                ),
                isolates_stone=_optional_str(payload.get("isolates_stone")),
                synonym_kind=_optional_str(payload.get("synonym_kind")),
                literal_of=_optional_str(payload.get("literal_of")),
                note=_optional_str(payload.get("note")),
            )
        except KeyError as exc:
            raise GoldenSetError(f"{where}: query is missing field {exc}") from exc


@dataclass(frozen=True)
class Judgement:
    """One `(query, document)` verdict, with everything needed to read it back later.

    `source_hash` is the document's text at the moment of labelling, so a re-enrichment that
    rewrites a product afterwards is reported instead of silently invalidating the judgement.
    `lexically_reachable` and `data_origin` are frozen from the index for the same reason the
    query vectors are: the composition check has to give the same answer offline as it did on
    the day the label was written.
    """

    query_id: str
    product_id: str
    grade: int
    pooled_in: tuple[str, ...]
    judged_at: str
    source_hash: str
    data_origin: str
    lexically_reachable: bool
    sku: str | None = None
    note: str | None = None

    @property
    def relevant(self) -> bool:
        """The binary reading, derived and never chosen per configuration."""
        return self.grade >= RELEVANT_FROM

    @classmethod
    def from_json(cls, payload: dict[str, Any], *, where: str) -> "Judgement":
        try:
            grade = int(payload["grade"])
            origin = str(payload["data_origin"])
        except KeyError as exc:
            raise GoldenSetError(f"{where}: judgement is missing field {exc}") from exc
        if grade not in range(MAX_GRADE + 1):
            raise GoldenSetError(f"{where}: grade {grade} is outside 0..{MAX_GRADE}")
        if origin not in DATA_ORIGINS:
            raise GoldenSetError(f"{where}: unknown data_origin {origin!r}")
        return cls(
            query_id=str(payload["query_id"]),
            product_id=str(payload["product_id"]),
            grade=grade,
            pooled_in=tuple(str(item) for item in payload.get("pooled_in") or ()),
            judged_at=str(payload["judged_at"]),
            source_hash=str(payload["source_hash"]),
            data_origin=origin,
            lexically_reachable=bool(payload["lexically_reachable"]),
            sku=_optional_str(payload.get("sku")),
            note=_optional_str(payload.get("note")),
        )


@dataclass(frozen=True)
class GoldenSet:
    """The loaded set. Only `load_golden_set` builds one, and only after validating it."""

    version: str
    root: Path
    queries: tuple[GoldenQuery, ...]
    judgements: tuple[Judgement, ...]
    by_query: dict[str, tuple[Judgement, ...]] = field(default_factory=dict)

    def query(self, query_id: str) -> GoldenQuery:
        for item in self.queries:
            if item.id == query_id:
                return item
        raise KeyError(query_id)

    @property
    def judged_queries(self) -> tuple[GoldenQuery, ...]:
        return tuple(item for item in self.queries if item.judged)

    def judgements_for(self, query_id: str) -> tuple[Judgement, ...]:
        return self.by_query.get(query_id, ())

    def grade(self, query_id: str, product_id: str) -> int | None:
        """The recorded grade, or None when nobody judged this pair.

        None and 0 are different answers and the caller must keep them apart: 0 is
        "measured irrelevant", None is "not measured", and conflating them is what makes
        an unjudged top-5 look like a bad one.
        """
        for item in self.by_query.get(query_id, ()):
            if item.product_id == product_id:
                return item.grade
        return None

    def relevant_documents(self, query_id: str) -> tuple[Judgement, ...]:
        return tuple(item for item in self.by_query.get(query_id, ()) if item.relevant)

    def origin_bucket(self, query_id: str) -> str | None:
        """Which origin's documents answer this query. None when nothing is relevant.

        Grouping is by query and counting is by judgement: retrieval always runs over the
        whole catalogue, and restricting the corpus to one origin is not an available
        configuration. See `metrics.py`.
        """
        origins = {item.data_origin for item in self.relevant_documents(query_id)}
        if not origins:
            return None
        if len(origins) == 1:
            return next(iter(origins))
        return "mixed"


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _read_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    if not path.is_file():
        raise GoldenSetError(f"{path} does not exist")
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise GoldenSetError(f"{path}:{number}: {exc}") from exc
            if not isinstance(payload, dict):
                raise GoldenSetError(f"{path}:{number}: each line must be an object")
            yield number, payload


def content_version(root: Path) -> str:
    """`schema:digest` over the three files that ARE the yardstick.

    Derived rather than declared on purpose: appending a judgement moves the version whether
    or not anybody remembers to bump it, which is what the requirement about ampliable
    judgements needs in order to mean anything.
    """
    digest = hashlib.sha256()
    for name in (CRITERION_FILE, QUERIES_FILE, JUDGEMENTS_FILE):
        path = root / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes() if path.is_file() else b"")
    return f"{GOLDEN_SET_SCHEMA_VERSION}:{digest.hexdigest()[:12]}"


# --------------------------------------------------------------------------------------
# Query analysis. Pure: reads the packaged dictionary, never the index.
# --------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _bridge_anchors() -> frozenset[ClassKey]:
    """The classes an overlay bridge widens — the only ones a `bridge` query can exercise."""
    resource = files("jbg_ai.retrieval").joinpath(OVERLAY_RESOURCE)
    overlay = load_overlay_from_path(Path(str(resource)))
    anchors: set[ClassKey] = set()
    for bridge in overlay.get("bridges") or ():
        for entry in bridge.get("widens") or ():
            anchors.add((str(entry["field"]), str(entry["canonical"])))
    return frozenset(anchors)


def resolved_fields(text: str, dictionary: SynonymDictionary) -> set[str]:
    expanded = expand_query(text, enabled=True, dictionary=dictionary)
    return {match.field for match in expanded.matched}


def synonym_kinds(text: str, dictionary: SynonymDictionary) -> set[str]:
    """Which of the three dictionary-entry classes this query actually exercises.

    The three are not interchangeable and a set that covered one of them six times would
    measure one mechanism and report three:

    * **stemmer artefact** — the surface form and the canonical are the SAME WORD that the
      Spanish configuration stems apart. Either the query wrote a variant the folded lookup
      rescued (`bano de oro` for `baño de oro`), or the class emits two forms that fold alike
      and stem differently (`pequeno` and `pequeño`, reaching 71 and 134 documents).
    * **commercial synonym** — a DIFFERENT word for the same thing (`dije` for `colgante`).
    * **directional bridge** — a class widened towards another vocabulary, and the direction
      was measured: the colour reaches solid gold, the plating deliberately does not.
    """
    expanded = expand_query(text, enabled=True, dictionary=dictionary)
    kinds: set[str] = set()
    anchors = _bridge_anchors()
    for match in expanded.matched:
        key = (match.field, match.canonical)
        if key in anchors:
            kinds.add("bridge")
        if match.term != match.canonical:
            kinds.add("stemmer" if fold(match.term) == fold(match.canonical) else "commercial")
        forms = dictionary.forms_for(key)
        folded = Counter(fold(form) for form in forms)
        if any(count > 1 for count in folded.values()):
            kinds.add("stemmer")
    return kinds


def names_stone(text: str, stone: str, dictionary: SynonymDictionary) -> bool:
    """The query names this stone, whichever vocabulary field the dictionary files it under.

    Field-agnostic on purpose. `perla` is filed under `materials` by the query dictionary and
    under `stone_type` by the extractor, in 31 documents and zero respectively — and that
    disagreement is precisely what the query measures. Requiring the field to be `stone_type`
    would have thrown out the one query in the category that tests it.
    """
    expanded = expand_query(text, enabled=True, dictionary=dictionary)
    return any(fold(match.canonical) == fold(stone) for match in expanded.matched)


def piece_type_discriminates(text: str, dictionary: SynonymDictionary) -> bool:
    """True when the query names a piece type narrow enough to be what selects the answer."""
    expanded = expand_query(text, enabled=True, dictionary=dictionary)
    return any(
        match.field == "piece_type" and match.canonical not in NON_DISCRIMINATING_PIECE_TYPES
        for match in expanded.matched
    )


def is_domain_plausible(text: str, dictionary: SynonymDictionary) -> bool:
    """The query speaks the catalogue's own language, even though the catalogue cannot answer it.

    This is what separates a useful out-of-domain query from nonsense. `xyzzy quimbombo` makes
    every configuration abstain, so the metric discriminates nothing and the category measures
    nothing; `un reloj de plata sumergible` names a material the catalogue stocks and a piece
    it does not, which is a question a customer really asks in a jeweller's.
    """
    expanded = expand_query(text, enabled=True, dictionary=dictionary)
    return bool(expanded.matched)


def is_literal(query: GoldenQuery) -> bool:
    """The query IS a code or a product name, rather than a description of one."""
    if not query.literal_of:
        return False
    return _normalise(query.text) == _normalise(query.literal_of)


def _normalise(text: str) -> str:
    return " ".join(fold(token) for token in _TOKEN.findall(text))


def query_terms(text: str, dictionary: SynonymDictionary) -> set[str]:
    """Every surface form the expanded query would search for, folded. Diagnostic only."""
    expanded = expand_query(text, enabled=True, dictionary=dictionary)
    return {fold(form) for group in expanded.groups for form in group}


# --------------------------------------------------------------------------------------
# Loading and validation
# --------------------------------------------------------------------------------------


def load_queries(root: Path | None = None) -> tuple[GoldenQuery, ...]:
    """Read the queries alone, without validating the set.

    The composition check needs judgements, and judgements need a pool, and a pool needs the
    queries — so the bootstrap has to be able to read them before the set is complete. It is
    the only entry point that skips validation, and nothing that measures anything calls it.
    """
    base = root or GOLDEN_DIR
    return tuple(
        GoldenQuery.from_json(payload, where=f"{base / QUERIES_FILE}:{number}")
        for number, payload in _read_jsonl(base / QUERIES_FILE)
    )


def load_golden_set(root: Path | None = None) -> GoldenSet:
    """Read the files, validate the composition, and refuse to return a set that fails it."""
    base = root or GOLDEN_DIR
    criterion = base / CRITERION_FILE
    if not criterion.is_file():
        raise GoldenSetError(
            f"{criterion} does not exist. The annotation criterion is written BEFORE the "
            "first judgement; a set whose yardstick is undocumented cannot be read back."
        )

    queries = tuple(
        GoldenQuery.from_json(payload, where=f"{base / QUERIES_FILE}:{number}")
        for number, payload in _read_jsonl(base / QUERIES_FILE)
    )
    judgements = tuple(
        Judgement.from_json(payload, where=f"{base / JUDGEMENTS_FILE}:{number}")
        for number, payload in _read_jsonl(base / JUDGEMENTS_FILE)
    )
    by_query: dict[str, list[Judgement]] = defaultdict(list)
    for item in judgements:
        by_query[item.query_id].append(item)

    golden = GoldenSet(
        version=content_version(base),
        root=base,
        queries=queries,
        judgements=judgements,
        by_query={key: tuple(value) for key, value in by_query.items()},
    )
    validate(golden)
    return golden


def validate(golden: GoldenSet) -> None:
    """Raise `GoldenSetError` naming the first unmet requirement. Never warns."""
    _validate_structure(golden)
    _validate_traceability(golden)
    _validate_origin_anchoring(golden)


def _validate_structure(golden: GoldenSet) -> None:
    seen_ids: set[str] = set()
    for item in golden.queries:
        if item.id in seen_ids:
            raise GoldenSetError(f"duplicate query id {item.id!r}")
        seen_ids.add(item.id)
        if item.category not in CATEGORIES:
            raise GoldenSetError(f"{item.id}: unknown category {item.category!r}")
        if item.synonym_kind is not None and item.synonym_kind not in SYNONYM_KINDS:
            raise GoldenSetError(f"{item.id}: unknown synonym kind {item.synonym_kind!r}")

    pairs: set[tuple[str, str]] = set()
    for item in golden.judgements:
        if item.query_id not in seen_ids:
            raise GoldenSetError(f"judgement names unknown query {item.query_id!r}")
        key = (item.query_id, item.product_id)
        if key in pairs:
            raise GoldenSetError(
                f"{item.query_id}/{item.product_id}: judged twice. Judgements are keyed by "
                "the pair so that a later change can append without re-recording; two rows "
                "for one pair make which of them counts undefined."
            )
        pairs.add(key)

    for item in golden.queries:
        recorded = golden.judgements_for(item.id)
        if item.judged and not recorded and item.category != OUT_OF_DOMAIN:
            raise GoldenSetError(f"{item.id}: declared as judged and carries no judgement")

        if not item.judged and recorded:
            raise GoldenSetError(
                f"{item.id}: declared WITHOUT judgements and carries {len(recorded)}. The two "
                "unmeasurable categories are written and left unlabelled on purpose: no "
                "configuration retrieves them, so labelling them now would record what the "
                "general retriever happened to return."
            )

    judged = len(golden.judged_queries)
    if judged < MINIMUM_JUDGED_QUERIES:
        raise GoldenSetError(
            f"only {judged} judged queries; the floor fixed before writing any of them "
            f"is {MINIMUM_JUDGED_QUERIES}",
            requirement="floor",
        )


def _validate_traceability(golden: GoldenSet) -> None:
    dictionary = load_query_dictionary()

    unanchored = [
        item.id
        for item in golden.judged_queries
        if any(
            judgement.grade == MAX_GRADE and not judgement.lexically_reachable
            for judgement in golden.judgements_for(item.id)
        )
    ]
    _require(
        len(unanchored),
        MINIMUM_UNANCHORED,
        requirement="P1 vector vs lexical",
        what=(
            "queries whose best document the lexical branch cannot reach at all, even after "
            "synonym expansion. Without them the set is dominated by `<tipo> de <material>` "
            "queries — which is how somebody who knows the catalogue's vocabulary writes — and "
            "confirms the previous rubric by construction"
        ),
    )

    # Out-of-domain queries are excluded, and the reason is what the requirement is FOR: it
    # asks for queries whose answer comes from a sparsely tagged field, and a query nothing
    # answers cannot demonstrate that anything answered it. C25 made this bite — its
    # out-of-domain queries are anchored to the domain through `regalo` and `boda` precisely
    # so they are not nonsense, and five of them landed in this tally, taking it from 6 to 11
    # and letting a real shortfall pass unnoticed.
    subjective = [
        item.id
        for item in golden.judged_queries
        if item.category != OUT_OF_DOMAIN
        and (fields := resolved_fields(item.text, dictionary))
        and fields & {"occasion_tags", "style_tags"}
        and not fields & HIGH_COVERAGE_FIELDS
    ]
    _require(
        len(subjective),
        MINIMUM_SUBJECTIVE,
        requirement="P3 subjective",
        what=(
            "queries that resolve only to a sparsely tagged field and to no high-coverage one. "
            "`boda` matches 5 documents of 1.168: if a query also names a piece type, what "
            "answers it is the 99 %-coverage field and the emergent property C21 claims is "
            "not being tested"
        ),
    )

    stone = [
        item.id
        for item in golden.judged_queries
        if item.isolates_stone
        and names_stone(item.text, item.isolates_stone, dictionary)
        and not piece_type_discriminates(item.text, dictionary)
    ]
    distinct_stones = {
        item.isolates_stone
        for item in golden.judged_queries
        if item.id in set(stone) and item.isolates_stone
    }
    _require(
        len(stone),
        MINIMUM_STONE,
        requirement="P3 stone",
        what=(
            "queries that name a stone where the piece type cannot be what selects the answer. "
            "C21 left it explicitly open whether `stone_type` should count for the "
            "coordination, and said none of its twelve queries isolated it"
        ),
    )
    if len(distinct_stones) < MINIMUM_STONE:
        raise GoldenSetError(
            f"the stone queries isolate only {len(distinct_stones)} distinct stones "
            f"({sorted(distinct_stones)}); {MINIMUM_STONE} different ones are needed, because "
            "four queries about one stone measure one stone four times",
            requirement="P3 stone",
        )

    kinds = Counter(
        kind
        for item in golden.judged_queries
        if item.synonym_kind
        for kind in [item.synonym_kind]
        if kind in synonym_kinds(item.text, dictionary)
    )
    for kind in SYNONYM_KINDS:
        _require(
            kinds.get(kind, 0),
            MINIMUM_SYNONYM_PER_KIND,
            requirement=f"P4 synonyms/{kind}",
            what=(
                f"queries that actually exercise a {kind} dictionary entry. The three classes "
                "are not interchangeable — a stemmer artefact, a commercial synonym and a "
                "directional bridge fail in different ways — and a declared kind the "
                "dictionary does not corroborate is a label, not a test"
            ),
        )

    out_of_domain = [
        item.id
        for item in golden.judged_queries
        if item.category == "fuera-de-dominio"
        and is_domain_plausible(item.text, dictionary)
        and not golden.relevant_documents(item.id)
    ]
    for item in golden.judged_queries:
        if item.category != "fuera-de-dominio":
            continue
        if not is_domain_plausible(item.text, dictionary):
            raise GoldenSetError(
                f"{item.id}: {item.text!r} does not name a single term of the catalogue's own "
                "vocabulary, so it is nonsense rather than a plausible question. Every "
                "configuration abstains on nonsense and the metric would discriminate nothing",
                requirement="P5 abstention",
            )
        if golden.relevant_documents(item.id):
            raise GoldenSetError(
                f"{item.id}: declared out of domain and carries a relevant document. It is "
                "answerable, so it measures ranking and not abstention",
                requirement="P5 abstention",
            )
        # And no grade above zero at all, which is stricter than "no relevant document":
        # the intermediate grade does not make a query answerable, but by the annotation
        # criterion nothing in the catalogue deserves even that for a question it cannot
        # satisfy, so one is evidence of a mislabelled query rather than of a near miss.
        graded = {judgement.grade for judgement in golden.judgements_for(item.id)}
        if graded - {0}:
            raise GoldenSetError(
                f"{item.id}: out of domain and carries a judgement of grade "
                f"{sorted(graded - {0})}. Every document is grade zero here by the annotation "
                "criterion, so a higher one is a mislabelled query or a broken rubric",
                requirement="P5 abstention",
            )
    _require(
        len(out_of_domain),
        MINIMUM_OUT_OF_DOMAIN,
        requirement="P5 abstention",
        what="plausible in-domain queries the catalogue cannot satisfy",
    )

    literal = [item.id for item in golden.judged_queries if is_literal(item)]
    _require(
        len(literal),
        MINIMUM_LEXICAL_LITERAL,
        requirement="P7 decision 12",
        what=(
            "queries that ARE a code or a product name. They are where the pre-existing "
            "substring searcher can win, and a comparison that omits them is not a fair one"
        ),
    )


def _validate_origin_anchoring(golden: GoldenSet) -> None:
    """No category may be answered entirely by products the annotator also wrote.

    Per category and not globally, which is the point: the report breaks every metric down by
    data origin, and a category whose relevant documents all come from one origin contributes
    to one column and nothing to the other, so the two are no longer comparable.
    """
    by_category: dict[str, set[str]] = defaultdict(set)
    for item in golden.judged_queries:
        if item.category == "fuera-de-dominio":
            continue  # It has no relevant document at all; that is its definition.
        for judgement in golden.relevant_documents(item.id):
            by_category[item.category].add(judgement.data_origin)

    for category, origins in sorted(by_category.items()):
        if origins == {"synthetic"}:
            raise GoldenSetError(
                f"every relevant document of category {category!r} is a synthetic product. "
                "The annotator wrote the synthetic corpus, and a category with a single "
                "origin cannot be compared across the breakdown the report publishes",
                requirement="real anchoring",
            )


def _require(actual: int, minimum: int, *, requirement: str, what: str) -> None:
    if actual >= minimum:
        return
    raise GoldenSetError(
        f"the set holds {actual} of the {minimum} required {what}",
        requirement=requirement,
    )


def iter_categories(queries: Iterable[GoldenQuery]) -> Counter:
    return Counter(item.category for item in queries)
