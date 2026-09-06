"""The ring size convention, read back out of the corpus. Delivered by C23.

The letter scale of the catalogue —`XXS` to `XXL`— **is not a normalised ring sizing
system**: not the Spanish one (a number), not ISO 8653 (a circumference in millimetres),
not the American one, and not the British letters `A`–`Z`, where `L`, `M` and `N` really
are sizes but `XS` and `XL` do not exist. It is a **garment scale** applied to the whole
catalogue, and the measurement confirms it: the letter travels on earrings, pendants,
necklaces, bracelets and rings alike, and the piece type that uses it most — earrings —
has no fit at all.

The ring is the only piece type where the letter *also* commits to a fit, so the ring is
the only one with an equivalence table, and that table lives in exactly one document.

This module parses it back out of the Markdown and states the invariants, so the numbers
are checked against arithmetic rather than trusted to whoever last edited the file:

- whole Spanish sizes, three per letter, contiguous and without overlap;
- `circunferencia (mm) = talla española + 40`, the ordinary Spanish relation — which is
  why the section stating it is scoped `general` while the section assigning the letters
  is scoped `establecimiento`;
- the diameter derived from the circumference;
- every letter of the size vocabulary present, with the two the catalogue never stocks
  marked as available to order instead of quietly dropped.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from jbg_ai.enrichment.vocab import Vocabularies, load_vocabularies
from jbg_ai.knowledge.constants import (
    MOTIF_SCALE_WORDS,
    SPANISH_SIZE_TO_CIRCUMFERENCE_OFFSET,
    TO_ORDER_SIZE_LETTERS,
)
from jbg_ai.knowledge.corpus import KnowledgeCorpus
from jbg_ai.knowledge.errors import KnowledgeCorpusError

RING_SIZE_DOCUMENT = "tallas-anillos"
RING_SIZE_SECTION = "nuestra-escala-de-letras-que-talla-es-cada-una"
RESIZING_SECTION = "que-aro-se-puede-ajustar-y-cual-no"

STOCKED = "De surtido"
TO_ORDER = "Por encargo"

#: `4 – 6` with an en dash, `4 - 6` with a hyphen, or `4` on its own.
_RANGE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(?:[–—-]\s*(\d+(?:[.,]\d+)?))?\s*(?:mm)?\s*$")
_TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")
_SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")


@dataclass(frozen=True)
class RingSizeRow:
    """One letter of the scale and everything it commits to."""

    letter: str
    size_min: int
    size_max: int
    circumference_min: int
    circumference_max: int
    diameter_min: float
    diameter_max: float
    availability: str

    @property
    def to_order(self) -> bool:
        return self.availability.casefold() == TO_ORDER.casefold()

    @property
    def sizes(self) -> tuple[int, ...]:
        return tuple(range(self.size_min, self.size_max + 1))


def _number(value: str) -> float:
    return float(value.replace(",", "."))


def _range(cell: str, *, letter: str, column: str) -> tuple[float, float]:
    match = _RANGE.match(cell)
    if match is None:
        raise KnowledgeCorpusError(
            f"la fila `{letter}` de la tabla de tallas no expresa un rango en la columna "
            f"«{column}»: `{cell}`",
            path=f"{RING_SIZE_DOCUMENT}.md",
            section=RING_SIZE_SECTION,
        )
    low = _number(match.group(1))
    high = _number(match.group(2)) if match.group(2) else low
    return low, high


def _whole(value: float, *, letter: str, column: str) -> int:
    if not float(value).is_integer():
        raise KnowledgeCorpusError(
            f"la fila `{letter}` de la tabla de tallas usa un valor no entero en la columna "
            f"«{column}»: `{value}`. Las tallas españolas de la escala son enteras",
            path=f"{RING_SIZE_DOCUMENT}.md",
            section=RING_SIZE_SECTION,
        )
    return int(value)


def ring_size_table(corpus: KnowledgeCorpus) -> tuple[RingSizeRow, ...]:
    """Parse the equivalence table out of the one section that carries it."""
    document = corpus.document(RING_SIZE_DOCUMENT)
    if document is None:
        raise KnowledgeCorpusError(
            "el corpus no contiene el documento de tallas de anillo",
            path=f"{RING_SIZE_DOCUMENT}.md",
        )
    section = document.section(RING_SIZE_SECTION)
    if section is None:
        raise KnowledgeCorpusError(
            "el documento de tallas de anillo no contiene la sección de la escala de letras",
            path=str(document.path),
            section=RING_SIZE_SECTION,
        )

    rows: list[RingSizeRow] = []
    for line in section.body.splitlines():
        stripped = line.strip()
        match = _TABLE_ROW.match(stripped)
        if match is None or _SEPARATOR.match(stripped):
            continue
        cells = [cell.strip() for cell in match.group(1).split("|")]
        if len(cells) < 5 or cells[0].casefold() == "letra":
            continue
        letter = cells[0].strip("`* ")
        size_low, size_high = _range(cells[1], letter=letter, column="Talla española")
        circ_low, circ_high = _range(cells[2], letter=letter, column="Circunferencia interior")
        diam_low, diam_high = _range(cells[3], letter=letter, column="Diámetro interior")
        rows.append(
            RingSizeRow(
                letter=letter,
                size_min=_whole(size_low, letter=letter, column="Talla española"),
                size_max=_whole(size_high, letter=letter, column="Talla española"),
                circumference_min=_whole(circ_low, letter=letter, column="Circunferencia interior"),
                circumference_max=_whole(circ_high, letter=letter, column="Circunferencia interior"),
                diameter_min=diam_low,
                diameter_max=diam_high,
                availability=cells[4],
            )
        )

    if not rows:
        raise KnowledgeCorpusError(
            "la sección de la escala de letras no contiene ninguna fila de tabla",
            path=str(document.path),
            section=RING_SIZE_SECTION,
        )
    return tuple(rows)


def circumference_for(size: int) -> int:
    """`circunferencia (mm) = talla española + 40`. Verifiable outside the jewellery."""
    return size + SPANISH_SIZE_TO_CIRCUMFERENCE_OFFSET


def diameter_for(circumference: float) -> float:
    """The diameter the circumference implies, to one decimal place."""
    return round(circumference / math.pi, 1)


def size_letters(vocabularies: Vocabularies | None = None) -> tuple[str, ...]:
    """The letters of the size vocabulary, without the words that describe a motif.

    `mini`, `extramini`, `pequeño`, `mediano` and `grande` are `size_label` terms too and
    are **never** a ring fit label: they describe the scale of the motif, and the
    measurement shows them travelling on earrings and pendants, which have no fit.
    """
    vocabs = vocabularies or load_vocabularies()
    motif = {word.casefold() for word in MOTIF_SCALE_WORDS}
    # `pequeno` is how the vocabulary stores `pequeño`; compare folded on both sides.
    motif |= {"pequeno"}
    return tuple(
        term for term in vocabs.size_label.canonical if term.casefold() not in motif
    )


def to_order_letters() -> tuple[str, ...]:
    """Letters the catalogue does not stock, present in the table and marked as such."""
    return TO_ORDER_SIZE_LETTERS


def resizing_section_text(corpus: KnowledgeCorpus) -> str:
    """The text of the one section that states which rings can be resized."""
    document = corpus.document(RING_SIZE_DOCUMENT)
    section = document.section(RESIZING_SECTION) if document else None
    if section is None:
        raise KnowledgeCorpusError(
            "el documento de tallas de anillo no dice qué aro se puede ajustar y cuál no",
            path=f"{RING_SIZE_DOCUMENT}.md",
            section=RESIZING_SECTION,
        )
    return section.body
