"""Size and material vocabularies for grouping. Delivered by C18a.

The point of this file is a regression guard, not coverage. D12 was revised while
implementing: the closed vocabularies already live in `enrichment/vocabularies.yaml`
and this package must **reuse** them. Declaring a list inside `families/` would
recreate, one border further in, the very duplication that decision set out to
avoid — and it would fail silently, because a drifted term matches nothing rather
than raising.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from jbg_ai.enrichment.vocab import fold, load_vocabularies
from jbg_ai.families import naming, vocabulary
from jbg_ai.families.vocabulary import UNRANKED_SIZE, load_family_vocabulary

VOCAB = load_family_vocabulary()


def test_family_vocabulary_reuses_enrichment_terms() -> None:
    """Every term the grouper knows comes from the committed closed vocabularies."""
    source = load_vocabularies()

    for term in source.materials.canonical:
        assert VOCAB.canonical_material(fold(term)) == term
    for term in source.size_label.canonical:
        assert VOCAB.canonical_size(fold(term)) == term
    for term in source.piece_type.canonical:
        assert VOCAB.is_piece_type(fold(term))


def test_no_term_list_is_declared_inside_the_families_package() -> None:
    """Fails if someone re-declares materials or sizes here instead of reusing them.

    Checks the sources of the two modules that could plausibly grow a list. The
    canonical size rank is exempt: it is an ordering, not a vocabulary, and the
    closed vocabulary cannot express it.
    """
    forbidden = {"plata", "oro", "laton", "acero", "resina", "cuero", "perla"}

    for module in (naming, vocabulary):
        text = Path(inspect.getfile(module)).read_text(encoding="utf-8")
        code = "\n".join(
            line for line in text.splitlines() if not line.strip().startswith(("#", '"', "*"))
        )
        for term in forbidden:
            assert f'"{term}"' not in code, (
                f"{module.__name__} declares the material {term!r}; reuse "
                "enrichment/vocabularies.yaml instead"
            )


def test_synonyms_of_both_size_scales_resolve() -> None:
    """The real catalogue writes `pequeña`, `mediana`, `grandes` and a lowercase `Xs`."""
    assert VOCAB.canonical_size(fold("pequeña")) == "pequeno"
    assert VOCAB.canonical_size(fold("mediana")) == "mediano"
    assert VOCAB.canonical_size(fold("grandes")) == "grande"
    assert VOCAB.canonical_size(fold("Xs")) == "XS"


def test_canonical_rank_orders_across_both_scales() -> None:
    """The vocabulary groups by scale; only the rank knows `mini` precedes `grande`."""
    ordered = ["mini", "XS", "pequeno", "S", "M", "mediano", "L", "grande", "XL"]
    ranks = [VOCAB.size_rank(term) for term in ordered]
    assert ranks == sorted(ranks), ranks
    assert len(set(ranks)) == len(ranks), "two size terms must not share a rank"


def test_unknown_size_sorts_last_and_does_not_raise() -> None:
    """An unnamed size is a review item, never a crash."""
    assert VOCAB.size_rank("talla-42") == UNRANKED_SIZE
    assert VOCAB.size_rank(None) == UNRANKED_SIZE
    assert UNRANKED_SIZE > VOCAB.size_rank("XL")


def test_a_multi_word_piece_type_is_not_mistaken_for_a_bare_one() -> None:
    assert VOCAB.is_piece_type("anillo")
    assert not VOCAB.is_piece_type("anillo plata")
    assert not VOCAB.is_piece_type("")
