"""Size and material vocabularies for family grouping. Delivered by C18a.

**Nothing here declares a term.** The closed vocabularies already live in
`jbg_ai/enrichment/vocabularies.yaml` (C09) and `enrichment.vocab.fold` already
does the folding this package needs. Declaring a second list in Python would
create the exact drift the frontend's `materials-vocabulary.test.ts` exists to
catch, one border further in.

What *is* new here is the **canonical size rank**. The vocabulary knows which
tokens are sizes; it does not know that `mini` comes before `grande`, because
its `terms` list is grouped by scale and not ordered by magnitude. Ordering is
what `ProductFamilyMember.Position` needs, and design decision 6 keeps it
strictly separate from the label: the rank orders, the label stays verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass

from jbg_ai.enrichment.vocab import ClosedVocab, fold, load_vocabularies

__all__ = [
    "FamilyVocabulary",
    "UNRANKED_SIZE",
    "load_family_vocabulary",
]

# Magnitude order across BOTH scales, smallest first. Absent from the closed
# vocabulary on purpose: it is a fact about jewellery sizes, not about the
# extraction contract. A token the catalogue uses but this rank does not name
# sorts last (see UNRANKED_SIZE) rather than raising: an unknown size is a
# review item, never a crash.
_CANONICAL_SIZE_RANK: tuple[str, ...] = (
    "extramini",
    "mini",
    "XXS",
    "XS",
    "pequeno",
    "S",
    "M",
    "mediano",
    "L",
    "grande",
    "XL",
    "XXL",
)

#: Rank given to a size token the canonical order does not name. Sorts last.
UNRANKED_SIZE = len(_CANONICAL_SIZE_RANK)


@dataclass(frozen=True)
class FamilyVocabulary:
    """Folded lookup tables for grouping. Built from the C09 closed vocabularies."""

    #: folded size token (canonical form and every synonym) -> canonical term
    size_tokens: dict[str, str]
    #: folded material token (canonical form and every synonym) -> canonical term
    material_tokens: dict[str, str]
    #: folded piece-type token -> canonical term, used by the degenerate-root guard
    piece_type_tokens: dict[str, str]

    def size_rank(self, canonical: str | None) -> int:
        """Magnitude rank of a canonical size term; unknown tokens sort last."""
        if canonical is None:
            return UNRANKED_SIZE
        try:
            return _CANONICAL_SIZE_RANK.index(canonical)
        except ValueError:
            return UNRANKED_SIZE

    def canonical_size(self, token: str) -> str | None:
        """Canonical size term for a folded token, or None when it is not a size."""
        return self.size_tokens.get(token)

    def canonical_material(self, token: str) -> str | None:
        """Canonical material term for a folded token, or None when it is not one."""
        return self.material_tokens.get(token)

    def is_piece_type(self, folded_text: str) -> bool:
        """Whether the whole folded text is nothing but a piece-type term."""
        return folded_text in self.piece_type_tokens


def _folded_lookup(vocab: ClosedVocab) -> dict[str, str]:
    """Map every folded surface form — canonical and synonym — onto its canonical term.

    Multi-word terms are included: `baño de oro` folds to `bano de oro` and is
    matched as a phrase before single tokens, so `oro` never steals it.
    """
    lookup = {fold(term): term for term in vocab.canonical}
    for folded_synonym, canonical in vocab.synonyms.items():
        lookup.setdefault(folded_synonym, canonical)
    return lookup


def load_family_vocabulary() -> FamilyVocabulary:
    """Build the grouping vocabulary from the committed closed vocabularies."""
    vocabularies = load_vocabularies()
    return FamilyVocabulary(
        size_tokens=_folded_lookup(vocabularies.size_label),
        material_tokens=_folded_lookup(vocabularies.materials),
        piece_type_tokens=_folded_lookup(vocabularies.piece_type),
    )
