"""Name root, variant label and size ordering. Delivered by C18a.

Pure text work: no I/O, no vectors, no database. The folding itself comes from
`enrichment.vocab.fold`, so a family root and an enrichment value normalise
identically and cannot drift apart.

Two rules here are measured decisions, not preferences:

* **Only the size suffix leaves the root.** Removing material tokens globally
  collapses `Anillo plata S/M/L/XL` onto the bare piece type `anillo`, which
  would then absorb every other "Anillo <material>". Material is handled by
  *merging* already-formed groups (see `grouping`), never by stripping.
* **The size label is the substring the catalogue wrote.** `ClosedVocab.resolve`
  canonicalises `pequeña` to `pequeno`; persisting that would contradict the
  requirement that the label stays verbatim. Detection uses the vocabulary —
  so the synonym is recognised — and storage keeps what the shop typed.

The material axis is deliberately **not** symmetrical with that last rule, and
`grouping._distinguishing_labels` is where it shows: a material reaches a label as
its *canonical* term. Two spellings of one material (`Oro` and `18k`, `plata` and
`925`) would otherwise read as two distinct variants and slip past the duplicate
label guard, presenting the same product twice over. The size scales cannot cause
that — `mini` and `XS` are different sizes, not two spellings of one — so there
the verbatim rule is free of consequences and applies.
"""

from __future__ import annotations

from dataclasses import dataclass

from jbg_ai.enrichment.vocab import fold
from jbg_ai.families.vocabulary import FamilyVocabulary

__all__ = ["ParsedName", "parse_name"]


@dataclass(frozen=True)
class ParsedName:
    """A product name split into the part that groups and the part that varies."""

    #: Folded name with the size removed, from wherever it sat. Groups products.
    root: str
    #: Size token exactly as the catalogue wrote it, or None for the base piece.
    size_label: str | None
    #: Canonical size term behind `size_label`, used only for ordering.
    canonical_size: str | None
    #: Canonical material terms found in the name, deduplicated, order preserved.
    canonical_materials: tuple[str, ...]

    @property
    def root_tokens(self) -> tuple[str, ...]:
        return tuple(self.root.split())


def parse_name(name: str, vocabulary: FamilyVocabulary) -> ParsedName:
    """Split a product name into grouping root, size variant and material tokens.

    The size token is removed from **any** position, not only the last one, and
    only the first one found is removed. Restricting it to the suffix passes the
    synthetic corpus — built entirely of `<name> <SIZE>` — and fails the real one
    twice: `Anillo lapislázuli mediano oro` hides its size behind a material, and
    `Anillo mini conchiglie` would never join `Anillo conchiglie`.

    Stripping from any position is safe because of an asymmetry: when a size word
    is genuinely part of the model name, *every* member carries it, so removing it
    leaves all their roots equally shortened and they still group together. It
    only changes the outcome when some members have it and others do not — which
    is precisely the case where it *is* the variant axis.

    A name that is nothing but a size keeps it: emptying the root would group
    every such product together.

    Sizes and materials are matched as **phrases**, longest first, because several
    vocabulary entries span more than one word (`extra mini`, `baño de oro`). A
    single-token scan sees only their last word, which strands `extra` in the root
    and truncates the label to `mini` — silently, and only for the names that carry
    one. No product name in today's catalogue does; the scan is what keeps the next
    one from breaking quietly.
    """
    folded = fold(name)
    if not folded:
        return ParsedName("", None, None, ())

    tokens = folded.split()
    size_label: str | None = None
    canonical_size: str | None = None

    index = 0
    while index < len(tokens):
        found = vocabulary.size_at(tokens, index)
        if found is None:
            index += 1
            continue
        length, canonical = found
        if length == len(tokens):
            break  # the whole name is a size; keep it as the root
        # Recover the surface form from the original string rather than from the
        # folded one, so the label keeps its accent: `pequeña`, never `pequena`.
        size_label = _surface_form(name, " ".join(tokens[index : index + length]))
        canonical_size = canonical
        tokens = tokens[:index] + tokens[index + length :]
        break

    canonical_materials: list[str] = []
    index = 0
    while index < len(tokens):
        found = vocabulary.material_at(tokens, index)
        if found is None:
            index += 1
            continue
        length, canonical = found
        if canonical not in canonical_materials:
            canonical_materials.append(canonical)
        index += length

    return ParsedName(
        root=" ".join(tokens),
        size_label=size_label,
        canonical_size=canonical_size,
        canonical_materials=tuple(canonical_materials),
    )


def _surface_form(name: str, folded_phrase: str) -> str:
    """The stretch of the original name that folds to `folded_phrase`.

    Matched by folding rather than by index, because folding turns punctuation into
    whitespace and the two token streams need not line up: `extra-mini` is one chunk
    of the name and two folded tokens. Widening windows handle both directions.
    Keeps the catalogue's spelling — accent and capitalisation included — which is
    what the operator reads on the label.
    """
    chunks = [chunk.strip("()+.,;:") for chunk in name.strip().split()]
    for start in range(len(chunks)):
        for end in range(start + 1, len(chunks) + 1):
            window = " ".join(chunks[start:end])
            if fold(window) == folded_phrase:
                return window
    return folded_phrase
