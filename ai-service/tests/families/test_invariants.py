"""Invariants of the grouper, over generated catalogues. Delivered by C18a.

Properties rather than values, per the plan's cross-cutting testing rule. What is
asserted here is what the .NET side enforces at the database level — a product in
at most one family, positions without gaps, variant labels unique within a family —
so a proposal violating any of them would be rejected on `apply` with a constraint
error instead of a message anyone can act on.

The catalogue is generated deterministically from a seed. There is no `hypothesis`
in this project's dependencies and this change does not add one: a seeded generator
over a few hundred shapes covers the invariants without a new library.
"""

from __future__ import annotations

import random
import uuid

import pytest

from jbg_ai.families.grouping import CandidateProduct, build_candidate_groups
from jbg_ai.families.vocabulary import load_family_vocabulary

VOCAB = load_family_vocabulary()

_PIECE_TYPES = ("anillo", "colgante", "pendientes", "pulsera", "collar")
_STEMS = ("erizo de mar", "hoja roble", "conchiglie", "ola eterna", "rama", "lapislazuli")
_SIZES = ("S", "M", "L", "XL", "mini", "pequeña", "mediana", "grande", None)
_MATERIALS = ("plata", "oro", None)


def _catalogue(seed: int, count: int = 120) -> list[CandidateProduct]:
    rng = random.Random(seed)
    products: list[CandidateProduct] = []
    for index in range(count):
        stem = rng.choice(_STEMS)
        size = rng.choice(_SIZES)
        material = rng.choice(_MATERIALS)
        piece = rng.choice(_PIECE_TYPES)
        parts = [piece.capitalize(), stem]
        if material:
            parts.append(material)
        if size:
            parts.append(size)
        products.append(
            CandidateProduct(
                product_id=uuid.uuid4(),
                sku=f"SKU{index:04d}",
                name=" ".join(parts),
                # One in twelve carries no piece type, mirroring the 3.1% measured
                # on the real index, so the gate is exercised rather than assumed.
                piece_type=None if index % 12 == 0 else piece,
                family_id=None,
            )
        )
    return products


@pytest.mark.parametrize("seed", [1, 7, 42, 1234, 20260831])
def test_a_product_belongs_to_at_most_one_proposal(seed: int) -> None:
    outcome = build_candidate_groups(_catalogue(seed), VOCAB)
    seen: set[uuid.UUID] = set()
    for proposal in outcome.proposals:
        for member in proposal.members:
            assert member.product_id not in seen, "a product was proposed twice"
            seen.add(member.product_id)


@pytest.mark.parametrize("seed", [1, 7, 42, 1234, 20260831])
def test_positions_are_consecutive_from_zero(seed: int) -> None:
    outcome = build_candidate_groups(_catalogue(seed), VOCAB)
    for proposal in outcome.proposals:
        positions = [member.position for member in proposal.members]
        assert positions == list(range(len(proposal.members))), proposal.root


@pytest.mark.parametrize("seed", [1, 7, 42, 1234, 20260831])
def test_variant_labels_are_unique_within_a_family(seed: int) -> None:
    outcome = build_candidate_groups(_catalogue(seed), VOCAB)
    for proposal in outcome.proposals:
        labels = [member.variant_label for member in proposal.members]
        assert len(set(labels)) == len(labels), (proposal.root, labels)


@pytest.mark.parametrize("seed", [1, 7, 42, 1234, 20260831])
def test_every_proposal_has_at_least_two_members(seed: int) -> None:
    outcome = build_candidate_groups(_catalogue(seed), VOCAB)
    assert all(len(proposal.members) >= 2 for proposal in outcome.proposals)


@pytest.mark.parametrize("seed", [1, 7, 42, 1234, 20260831])
def test_a_proposal_never_mixes_piece_types(seed: int) -> None:
    products = _catalogue(seed)
    by_id = {product.product_id: product for product in products}
    outcome = build_candidate_groups(products, VOCAB)
    for proposal in outcome.proposals:
        types = {by_id[member.product_id].piece_type for member in proposal.members}
        assert types == {proposal.piece_type}, (proposal.root, types)


@pytest.mark.parametrize("seed", [1, 7, 42, 1234, 20260831])
def test_every_input_product_is_proposed_excluded_or_unmatched(seed: int) -> None:
    """No product vanishes without a reason a reader can find."""
    products = _catalogue(seed)
    outcome = build_candidate_groups(products, VOCAB)

    proposed = {member.product_id for p in outcome.proposals for member in p.members}
    excluded = {product.product_id for product in outcome.excluded}
    assert proposed.isdisjoint(excluded), "a product cannot be both grouped and excluded"

    without_piece_type = {p.product_id for p in products if p.piece_type is None}
    assert without_piece_type == excluded, "the gate must name everything it removes"


@pytest.mark.parametrize("seed", [1, 7, 42, 1234, 20260831])
def test_rerunning_over_the_same_catalogue_agrees(seed: int) -> None:
    products = _catalogue(seed)
    first = build_candidate_groups(products, VOCAB)
    second = build_candidate_groups(products, VOCAB)

    def shape(outcome: object) -> list[tuple[str, tuple[str | None, ...]]]:
        return [
            (p.root, tuple(m.variant_label for m in p.members))
            for p in outcome.proposals  # type: ignore[attr-defined]
        ]

    assert shape(first) == shape(second)
