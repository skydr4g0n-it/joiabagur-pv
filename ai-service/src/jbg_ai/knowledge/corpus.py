"""Discovery, parsing and validation of the knowledge corpus. Delivered by C23.

Pure with respect to everything but the filesystem: no session, no provider, no socket.

The seven authoring rules are **validated here and not trusted to the author**, and every
failure names the file and, when it applies, the section. A corpus that holds together only
by good intentions drifts, and the drift is invisible until a citation points at prose that
no longer says what it said.

Two of the validations exist for reasons that are not obvious:

**Text before the first section is an error, not untidiness.** Such text would produce a
fragment with no heading of its own — a citation that resolves and does not *locate*, which
is the one property this corpus exists to provide.

**An oversized section fails rather than being split.** The author knows where a claim ends;
an automatic splitter does not, and it would manufacture exactly the headingless fragment
the previous rule forbids.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from jbg_ai.enrichment.vocab import Vocabularies, fold, load_vocabularies
from jbg_ai.knowledge.constants import (
    ALLOWED_DOC_TYPES,
    CLAIM_SCOPES,
    CORPUS_DIR,
    FORBIDDEN_DOC_TYPE,
    MAX_SECTION_CHARS,
    NON_DOCUMENT_STEMS,
)
from jbg_ai.knowledge.errors import KnowledgeCorpusError, KnowledgeCoverageError

#: `<!-- clave: valor -->` on a line of its own. The only metadata carrier in a document,
#: and invisible to any Markdown renderer, which is why an author never has to look at it.
_MARKER = re.compile(r"^<!--\s*([a-z_]+)\s*:\s*(.*?)\s*-->$")

_DOC_TITLE = re.compile(r"^#\s+(?P<title>\S.*)$")
_SECTION_TITLE = re.compile(r"^##\s+(?P<title>\S.*)$")
_DEEPER_HEADING = re.compile(r"^#{3,}\s")

_SLUG_TRIM = re.compile(r"^-+|-+$")

#: Nouns that count things in the catalogue. A number in front of one of these is a
#: statistic about the assortment, and a statistic about the assortment goes stale the day
#: a product is added or withdrawn.
_CATALOGUE_UNITS = r"productos?|piezas?|unidades|fichas?|referencias|art[íi]culos?|colecciones|modelos"

#: Spelled-out numerals that only ever precede one of those nouns when something is being
#: counted. It starts at eleven on purpose: «dos piezas de oro que comparten cajón se rayan»
#: is ordinary prose, while «veintiocho colecciones» is a census. Below eleven the word is
#: almost always generic and above it almost always a tally, so the line is drawn there
#: rather than pretending a regular expression can read intent.
_SPELLED_TALLY = (
    r"once|doce|trece|catorce|quince|diecis[ée]is|diecisiete|dieciocho|diecinueve|veinte|"
    r"veinti\w+|treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|cien|ciento|mil"
)

#: Rule 5, in its two halves.
#:
#: **A stock keeping unit, a catalogue reference or a price.** The euro sign is caught on
#: its own: there is no legitimate reason for it to appear in a corpus that never names one.
#:
#: **And any figure counting the catalogue.** This is the half that is easy to get wrong,
#: because a measured number reads like rigour. It is the opposite: «`pequeño` encabeza con
#: 71 etiquetas» stops being true the moment one product changes, and a corpus whose
#: sentences expire silently is worse than one that never claimed the number — the citation
#: still resolves, still locates, and now carries a falsehood with a verified stamp. The
#: measured evidence decides **which** documents exist and how deep each one goes; it lives
#: in the block prompts and in the report, never in the citable text. What a section may say
#: is the durable shape of the fact: *most*, *a large part*, *the exception*, *rarely*.
#:
#: A percentage is refused **only next to one of those nouns**, and not on sight. Not every
#: proportion in a jewellery corpus is a statistic about the shop: an opal carries three to
#: ten per cent water by structure, and that sentence is mineralogy that will read the same
#: in twenty years. What expires is «el 24,4 % del surtido». The rule therefore reads the
#: neighbourhood rather than the symbol.
_FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("nombra una referencia de artículo", re.compile(r"\bSKU\s*\d+\b", re.IGNORECASE)),
    (
        "nombra una referencia de artículo",
        re.compile(r"\bref(?:\.|erencia)\s*n?º?\s*\d{2,}\b", re.IGNORECASE),
    ),
    ("nombra un precio", re.compile(r"€")),
    ("nombra un precio", re.compile(r"\d[\d.,]*\s*(?:EUR\b|euros?\b)", re.IGNORECASE)),
    (
        "nombra un precio",
        re.compile(r"\b(?:precio|importe|coste|cuesta|vale)\w*\s+(?:de\s+)?\d", re.IGNORECASE),
    ),
    (
        "cuenta productos del catálogo",
        re.compile(rf"\d[\d.,]*\s+(?:{_CATALOGUE_UNITS})\b", re.IGNORECASE),
    ),
    (
        "cuenta productos del catálogo",
        re.compile(
            rf"\b(?:{_SPELLED_TALLY})\b[^.;]{{0,60}}?\b(?:{_CATALOGUE_UNITS})\b", re.IGNORECASE
        ),
    ),
    (
        "expresa una proporción del catálogo en porcentaje",
        re.compile(
            rf"(?:\d[\d.,]*\s*%|\bpor ciento\b)[^.;]{{0,40}}?"
            rf"\b(?:{_CATALOGUE_UNITS}|cat[áa]logo|surtido|[íi]ndice)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "expresa una proporción del catálogo en porcentaje",
        re.compile(
            rf"\b(?:{_CATALOGUE_UNITS}|cat[áa]logo|surtido|[íi]ndice)\b[^.;]{{0,40}}?"
            rf"(?:\d[\d.,]*\s*%|\bpor ciento\b)",
            re.IGNORECASE,
        ),
    ),
)

#: Document-level markers. `doc_type` and `eval_question` are required; `source_ref` is not.
_DOCUMENT_MARKERS = frozenset({"doc_type", "eval_question", "source_ref"})

#: Section-level markers. `claim_scope` is required; `source_ref` is not.
_SECTION_MARKERS = frozenset({"claim_scope", "source_ref"})


def slugify(text: str) -> str:
    """Fold to the slug used in identifiers and citations.

    Built on `enrichment.vocab.fold`, so a section title and a vocabulary term fold the
    same way and `baño de oro` reaches `bano-de-oro` from both sides.
    """
    return _SLUG_TRIM.sub("", fold(text).replace(" ", "-"))


def material_sheet_slug(canonical: str) -> str:
    """The document slug the coverage invariant expects for one canonical material."""
    return f"material-{slugify(canonical)}"


@dataclass(frozen=True)
class Section:
    """One `##` section: one citable claim, and one chunk once it is indexed."""

    slug: str
    title: str
    claim_scope: str
    body: str
    order: int
    source_ref: str | None = None


@dataclass(frozen=True)
class KnowledgeDocument:
    """One file of the corpus, parsed and validated."""

    slug: str
    title: str
    doc_type: str
    eval_question: str
    sections: tuple[Section, ...]
    path: Path
    source_ref: str | None = None

    def section(self, slug: str) -> Section | None:
        return next((item for item in self.sections if item.slug == slug), None)


@dataclass(frozen=True)
class KnowledgeCorpus:
    """Every document of `data/knowledge/`, in a stable order."""

    documents: tuple[KnowledgeDocument, ...]
    root: Path

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.documents)

    def __len__(self) -> int:
        return len(self.documents)

    @property
    def section_count(self) -> int:
        return sum(len(document.sections) for document in self.documents)

    def document(self, slug: str) -> KnowledgeDocument | None:
        return next((item for item in self.documents if item.slug == slug), None)

    def counts_by_doc_type(self) -> dict[str, int]:
        counts = {doc_type: 0 for doc_type in sorted(ALLOWED_DOC_TYPES)}
        for document in self.documents:
            counts[document.doc_type] = counts.get(document.doc_type, 0) + 1
        return counts

    def counts_by_claim_scope(self) -> dict[str, int]:
        counts = {scope: 0 for scope in sorted(CLAIM_SCOPES)}
        for document in self.documents:
            for section in document.sections:
                counts[section.claim_scope] = counts.get(section.claim_scope, 0) + 1
        return counts


def _marker(line: str) -> tuple[str, str] | None:
    match = _MARKER.match(line.strip())
    return (match.group(1), match.group(2)) if match else None


def forbidden_content_reason(text: str) -> str | None:
    """Why rule 5 refuses this text, or `None` if it does not.

    Public because the rule is a concept of this module and not an implementation detail:
    a caller checking a draft before committing it asks the same question the ingest does,
    and should not have to reach for a private name to ask it.
    """
    for reason, pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(text):
            return reason
    return None


def _require_no_forbidden_content(text: str, *, path: str, section: str | None) -> None:
    reason = forbidden_content_reason(text)
    if reason is not None:
        raise KnowledgeCorpusError(
            f"{reason}. El conocimiento es general y tiene que seguir siendo cierto cuando "
            "el catálogo cambie: una afirmación que solo vale para una pieza, o que sólo "
            "vale mientras el surtido tenga exactamente los productos de hoy, es catálogo "
            "—y el catálogo ya tiene su propio índice—. Di la forma duradera del hecho "
            "(la mayoría, buena parte, la excepción, rara vez); la cifra medida vive en el "
            "prompt del bloque y en el informe",
            path=path,
            section=section,
        )


def _parse_header(
    lines: list[str], path: str
) -> tuple[str, dict[str, str], int]:
    """Read the title and the document markers. Returns the index of the first section."""
    title: str | None = None
    markers: dict[str, str] = {}

    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        if _SECTION_TITLE.match(line):
            if title is None:
                raise KnowledgeCorpusError(
                    "el documento empieza por una sección y no por su título `# Título`",
                    path=path,
                )
            return title, markers, index
        if _DEEPER_HEADING.match(line):
            raise KnowledgeCorpusError(
                "usa un encabezado de tercer nivel o más profundo. La unidad de cita es "
                "la sección `##` y solo esa",
                path=path,
            )
        heading = _DOC_TITLE.match(line)
        if heading is not None:
            if title is not None:
                raise KnowledgeCorpusError(
                    "declara dos títulos de documento; un fichero es un documento",
                    path=path,
                )
            title = heading.group("title").strip()
            continue
        if title is None:
            raise KnowledgeCorpusError(
                "empieza con texto antes de su título `# Título`", path=path
            )
        pair = _marker(line)
        if pair is None:
            raise KnowledgeCorpusError(
                "lleva texto entre el título y la primera sección. Un preámbulo sin "
                "sección sería un fragmento sin encabezado propio, o sea una cita que "
                "resuelve y no localiza",
                path=path,
            )
        key, value = pair
        if key not in _DOCUMENT_MARKERS:
            raise KnowledgeCorpusError(
                f"declara la marca de documento desconocida `{key}`; se admiten "
                f"{', '.join(sorted(_DOCUMENT_MARKERS))}",
                path=path,
            )
        markers[key] = value

    if title is None:
        raise KnowledgeCorpusError("está vacío o no tiene título `# Título`", path=path)
    raise KnowledgeCorpusError("no tiene ninguna sección `##`", path=path)


def _parse_sections(lines: list[str], start: int, path: str) -> tuple[Section, ...]:
    sections: list[Section] = []
    current_title: str | None = None
    current_markers: dict[str, str] = {}
    current_body: list[str] = []
    body_started = False

    def flush() -> None:
        nonlocal current_title, current_markers, current_body, body_started
        if current_title is None:
            return
        sections.append(
            _build_section(
                title=current_title,
                markers=current_markers,
                body="\n".join(current_body).strip(),
                order=len(sections),
                path=path,
            )
        )
        current_title, current_markers, current_body, body_started = None, {}, [], False

    for raw in lines[start:]:
        line = raw.rstrip()
        stripped = line.strip()

        if _DOC_TITLE.match(stripped):
            raise KnowledgeCorpusError(
                "declara dos títulos de documento; un fichero es un documento", path=path
            )
        if _DEEPER_HEADING.match(stripped):
            raise KnowledgeCorpusError(
                "usa un encabezado de tercer nivel o más profundo. La unidad de cita es "
                "la sección `##` y solo esa",
                path=path,
                section=current_title,
            )

        heading = _SECTION_TITLE.match(stripped)
        if heading is not None:
            flush()
            current_title = heading.group("title").strip()
            continue

        pair = _marker(stripped)
        if pair is not None:
            key, value = pair
            if body_started:
                raise KnowledgeCorpusError(
                    f"coloca la marca `{key}` después del texto de la sección; las marcas "
                    "van justo bajo el encabezado",
                    path=path,
                    section=current_title,
                )
            if key not in _SECTION_MARKERS:
                raise KnowledgeCorpusError(
                    f"declara la marca de sección desconocida `{key}`; se admiten "
                    f"{', '.join(sorted(_SECTION_MARKERS))}",
                    path=path,
                    section=current_title,
                )
            current_markers[key] = value
            continue

        if stripped:
            body_started = True
        current_body.append(line)

    flush()
    return tuple(sections)


def _build_section(
    *, title: str, markers: dict[str, str], body: str, order: int, path: str
) -> Section:
    slug = slugify(title)
    if not slug:
        raise KnowledgeCorpusError(
            f"tiene una sección cuyo título no produce ningún identificador: `{title}`",
            path=path,
        )

    claim_scope = markers.get("claim_scope", "").strip()
    if not claim_scope:
        raise KnowledgeCorpusError(
            "no declara `claim_scope`. Sin él, un compromiso de la casa se leería como un "
            "hecho comprobable fuera de ella",
            path=path,
            section=slug,
        )
    if claim_scope not in CLAIM_SCOPES:
        raise KnowledgeCorpusError(
            f"declara `claim_scope: {claim_scope}`, que no es ni "
            f"{' ni '.join(sorted(CLAIM_SCOPES))}",
            path=path,
            section=slug,
        )

    if not body:
        raise KnowledgeCorpusError("está vacía", path=path, section=slug)

    if len(body) > MAX_SECTION_CHARS:
        raise KnowledgeCorpusError(
            f"ocupa {len(body)} caracteres y el tope es {MAX_SECTION_CHARS}. El código no "
            "trocea por su cuenta: parte el autor, que es quien sabe dónde acaba una "
            "afirmación",
            path=path,
            section=slug,
        )

    _require_no_forbidden_content(f"{title}\n{body}", path=path, section=slug)

    source_ref = (markers.get("source_ref") or "").strip() or None
    return Section(
        slug=slug,
        title=title,
        claim_scope=claim_scope,
        body=body,
        order=order,
        source_ref=source_ref,
    )


def parse_document(text: str, *, slug: str, path: str | Path | None = None) -> KnowledgeDocument:
    """Parse and validate one document. Pure: takes the text, never opens the file."""
    where = str(path) if path is not None else f"{slug}.md"
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    title, markers, first_section = _parse_header(lines, where)
    _require_no_forbidden_content(title, path=where, section=None)

    doc_type = markers.get("doc_type", "").strip()
    if not doc_type:
        raise KnowledgeCorpusError("no declara `doc_type`", path=where)
    if doc_type == FORBIDDEN_DOC_TYPE:
        raise KnowledgeCorpusError(
            f"declara `doc_type: {FORBIDDEN_DOC_TYPE}`. El corpus guarda hechos para citar; "
            "las instrucciones para obedecer viven en los prompts versionados, porque un "
            "fragmento imperativo recuperado dentro de un prompt es indistinguible de una "
            "instrucción",
            path=where,
        )
    if doc_type not in ALLOWED_DOC_TYPES:
        raise KnowledgeCorpusError(
            f"declara `doc_type: {doc_type}`, que no está en el vocabulario cerrado "
            f"({', '.join(sorted(ALLOWED_DOC_TYPES))})",
            path=where,
        )

    eval_question = markers.get("eval_question", "").strip()
    if not eval_question:
        raise KnowledgeCorpusError(
            "no declara `eval_question`. Cada documento aporta una pregunta a la medición",
            path=where,
        )

    sections = _parse_sections(lines, first_section, where)
    if not sections:
        raise KnowledgeCorpusError("no tiene ninguna sección `##`", path=where)

    seen: set[str] = set()
    for section in sections:
        if section.slug in seen:
            raise KnowledgeCorpusError(
                "repite el identificador de sección; dos secciones con el mismo título "
                "producirían dos citas indistinguibles",
                path=where,
                section=section.slug,
            )
        seen.add(section.slug)

    return KnowledgeDocument(
        slug=slug,
        title=title,
        doc_type=doc_type,
        eval_question=eval_question,
        sections=sections,
        path=Path(where),
        source_ref=(markers.get("source_ref") or "").strip() or None,
    )


def discover_documents(root: Path | None = None) -> tuple[Path, ...]:
    """Every Markdown file of the corpus, sorted. `README.md` and `_*` are not documents."""
    directory = root or CORPUS_DIR
    if not directory.is_dir():
        raise KnowledgeCorpusError("el directorio del corpus no existe", path=str(directory))
    return tuple(
        sorted(
            path
            for path in directory.glob("*.md")
            if path.stem not in NON_DOCUMENT_STEMS and not path.stem.startswith("_")
        )
    )


def load_corpus(root: Path | None = None) -> KnowledgeCorpus:
    """Load, parse and validate every document. Raises on the first fault, naming it."""
    directory = root or CORPUS_DIR
    documents = [
        parse_document(path.read_text(encoding="utf-8"), slug=path.stem, path=path)
        for path in discover_documents(directory)
    ]
    if not documents:
        raise KnowledgeCorpusError("el corpus no contiene ningún documento", path=str(directory))
    return KnowledgeCorpus(documents=tuple(documents), root=directory)


def missing_material_sheets(
    corpus: KnowledgeCorpus, vocabularies: Vocabularies | None = None
) -> tuple[str, ...]:
    """Canonical materials with no sheet. Coverage is derived, never chosen by hand.

    Reads `enrichment/vocabularies.yaml` **without modifying it**: touching that file forces
    a prompt version bump and a re-enrichment of every affected row, which is a change of
    its own. Here it is only asked what the closed vocabulary contains.
    """
    vocabs = vocabularies or load_vocabularies()
    missing: list[str] = []
    for canonical in vocabs.materials.canonical:
        document = corpus.document(material_sheet_slug(canonical))
        if document is None or document.doc_type != "material":
            missing.append(canonical)
    return tuple(missing)


def require_material_coverage(
    corpus: KnowledgeCorpus, vocabularies: Vocabularies | None = None
) -> None:
    """Fail naming the terms whose sheet is missing."""
    missing = missing_material_sheets(corpus, vocabularies)
    if missing:
        raise KnowledgeCoverageError(
            "el vocabulario de materiales tiene términos sin ficha: "
            + ", ".join(f"{term} (falta `{material_sheet_slug(term)}.md`)" for term in missing)
        )


def validate_corpus(root: Path | None = None) -> KnowledgeCorpus:
    """Load the corpus and assert the coverage invariant on top of the per-file rules."""
    corpus = load_corpus(root)
    require_material_coverage(corpus)
    return corpus
