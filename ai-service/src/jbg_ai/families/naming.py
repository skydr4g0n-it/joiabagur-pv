"""Name root, variant label and size ordering. Delivered by C18a.

Pure text work: no I/O, no vectors, no database. The folding itself comes from
`enrichment.vocab.fold`, so a family root and an enrichment value normalise
identically and cannot drift apart.

Two rules here are measured decisions, not preferences:

* **Only the size suffix leaves the root.** Removing material tokens globally
  collapses `Anillo plata S/M/L/XL` onto the bare piece type `anillo`, which
  would then absorb every other "Anillo <material>". Material is handled by
  *merging* already-formed groups (see `grouping`), never by stripping.
* **The label is the substring the catalogue wrote.** `ClosedVocab.resolve`
  canonicalises `pequeña` to `pequeno`; persisting that would contradict the
  requirement that the label stays verbatim. Detection uses the vocabulary —
  so the synonym is recognised — and storage keeps what the shop typed.
"""

from __future__ import annotations

from dataclasses import dataclass

from jbg_ai.enrichment.vocab import fold
from jbg_ai.families.vocabulary import FamilyVocabulary

__all__ = ["ParsedName", "parse_name"]


@dataclass(frozen=True)
class ParsedName:
    """A product name split into the part that groups and the part that varies."""

    #: Folded name with the trailing size token removed. Groups products.
    root: str
    #: Size token exactly as the catalogue wrote it, or None for the base piece.
    size_label: str | None
    #: Canonical size term behind `size_label`, used only for ordering.
    canonical_size: str | None
    #: Folded material tokens present anywhere in the name, in order of appearance.
    materials: tuple[str, ...]
    #: Canonical material terms behind `materials`, deduplicated, order preserved.
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
    """
    folded = fold(name)
    if not folded:
        return ParsedName("", None, None, (), ())

    tokens = folded.split()
    size_label: str | None = None
    canonical_size: str | None = None

    for index, token in enumerate(tokens):
        candidate = vocabulary.canonical_size(token)
        if candidate is None:
            continue
        if len(tokens) == 1:
            break  # the whole name is a size token; keep it as the root
        # Recover the surface form from the original string rather than from the
        # folded one, so the label keeps its accent: `pequeña`, never `pequena`.
        size_label = _surface_form(name, token)
        canonical_size = candidate
        tokens = tokens[:index] + tokens[index + 1 :]
        break

    materials: list[str] = []
    canonical_materials: list[str] = []
    for token in tokens:
        canonical_material = vocabulary.canonical_material(token)
        if canonical_material is not None:
            materials.append(token)
            if canonical_material not in canonical_materials:
                canonical_materials.append(canonical_material)

    return ParsedName(
        root=" ".join(tokens),
        size_label=size_label,
        canonical_size=canonical_size,
        materials=tuple(materials),
        canonical_materials=tuple(canonical_materials),
    )


def _surface_form(name: str, folded_token: str) -> str:
    """The chunk of the original name that folds to `folded_token`.

    Matched by folding rather than by index, because folding turns punctuation
    into whitespace and the two token streams need not line up. Keeps the
    catalogue's spelling — accent and capitalisation included — which is what
    the operator reads on the label.
    """
    for chunk in name.strip().split():
        trimmed = chunk.strip("()+.,;:")
        if fold(trimmed) == folded_token:
            return trimmed
    return folded_token
