"""Root grouping, material fusion and the degenerate-root guard. Delivered by C18a.

Every product name here is real: they are the cases from the Joia Bagur catalogue
that broke an earlier version of this algorithm, kept as tests so they cannot break
it again silently.
"""

from __future__ import annotations

import uuid

from jbg_ai.families.grouping import CandidateProduct, build_candidate_groups
from jbg_ai.families.vocabulary import load_family_vocabulary

VOCAB = load_family_vocabulary()


def _product(
    name: str,
    piece_type: str | None = "anillo",
    *,
    sku: str | None = None,
    family_id: uuid.UUID | None = None,
) -> CandidateProduct:
    return CandidateProduct(
        product_id=uuid.uuid4(),
        sku=sku or f"SKU-{name}",
        name=name,
        piece_type=piece_type,
        family_id=family_id,
    )


def _roots(products: list[CandidateProduct]) -> set[str]:
    return {proposal.root for proposal in build_candidate_groups(products, VOCAB).proposals}


def _only(products: list[CandidateProduct]):
    outcome = build_candidate_groups(products, VOCAB)
    assert len(outcome.proposals) == 1, [p.root for p in outcome.proposals]
    return outcome.proposals[0]


def test_groups_products_differing_only_in_size_suffix() -> None:
    proposal = _only(
        [
            _product("Colgante hoja roble pequeña", "colgante"),
            _product("Colgante hoja roble mediana", "colgante"),
            _product("Colgante hoja roble grande", "colgante"),
        ]
    )
    assert proposal.root == "colgante hoja roble"
    assert len(proposal.members) == 3


def test_inconsistent_capitalisation_does_not_split_family() -> None:
    """The real catalogue writes `Erizo` in one member of four and `erizo` in three."""
    proposal = _only(
        [
            _product("Anillo erizo de mar S"),
            _product("Anillo erizo de mar M"),
            _product("Anillo erizo de mar L"),
            _product("Anillo Erizo de mar XL"),
        ]
    )
    assert proposal.root == "anillo erizo de mar"
    assert len(proposal.members) == 4


def test_lowercase_size_suffix_is_recognised() -> None:
    """`Anillo oreja de mar Xs` exists in the catalogue with a lowercase scale token."""
    proposal = _only(
        [
            _product("Anillo oreja de mar Xs"),
            _product("Anillo oreja de mar S"),
            _product("Anillo oreja de mar M"),
        ]
    )
    assert proposal.root == "anillo oreja de mar"
    assert [member.variant_label for member in proposal.members] == ["Xs", "S", "M"]


def test_does_not_group_across_piece_types() -> None:
    outcome = build_candidate_groups(
        [
            _product("Anillo erizo de mar M", "anillo"),
            _product("Colgante erizo de mar M", "colgante"),
        ],
        VOCAB,
    )
    assert outcome.proposals == ()


def test_null_piece_type_groups_with_nobody() -> None:
    outcome = build_candidate_groups(
        [
            _product("Anillo erizo de mar S", "anillo"),
            _product("Anillo erizo de mar M", "anillo"),
            _product("Anillo erizo de mar L", None, sku="SKU-null"),
        ],
        VOCAB,
    )
    assert len(outcome.proposals) == 1
    assert len(outcome.proposals[0].members) == 2
    assert [excluded.sku for excluded in outcome.excluded] == ["SKU-null"]
    assert outcome.excluded[0].reason == "no_piece_type"


def test_products_already_in_a_family_are_counted_not_listed() -> None:
    outcome = build_candidate_groups(
        [
            _product("Anillo erizo de mar S", family_id=uuid.uuid4()),
            _product("Anillo erizo de mar M", family_id=uuid.uuid4()),
        ],
        VOCAB,
    )
    assert outcome.already_in_family_count == 2
    assert outcome.excluded == ()
    assert outcome.proposals == ()


def test_merges_groups_differing_in_one_material_token() -> None:
    proposal = _only(
        [
            _product("Colgante conchiglie", "colgante"),
            _product("Colgante conchiglie Oro", "colgante"),
            _product("Colgante mini conchiglie", "colgante"),
            _product("Colgante mini conchiglie Oro", "colgante"),
        ]
    )
    assert proposal.root == "colgante conchiglie"
    assert len(proposal.members) == 4


def test_material_in_root_is_not_stripped() -> None:
    """`Anillo plata S/M/L/XL` degenerates to the bare piece type under global stripping.

    Its reduced root *is* `anillo`, but nothing exists to fuse it with, so it keeps
    its own root and the guard never judges it.
    """
    proposal = _only(
        [
            _product("Anillo plata S"),
            _product("Anillo plata M"),
            _product("Anillo plata L"),
            _product("Anillo plata XL"),
        ]
    )
    assert proposal.root == "anillo plata"
    assert len(proposal.members) == 4


def test_degenerate_root_is_rejected_and_reported() -> None:
    """Workshop services live in the catalogue; the guard is what surfaces them."""
    outcome = build_candidate_groups(
        [
            _product("Encargos plata", "collar"),
            _product("Encargos Oro", "collar"),
        ],
        VOCAB,
    )
    assert outcome.proposals == ()
    assert len(outcome.rejected) == 1
    rejected = outcome.rejected[0]
    assert rejected.root == "encargos"
    assert rejected.reason == "root_too_short"
    assert set(rejected.product_names) == {"Encargos plata", "Encargos Oro"}


def test_bare_piece_type_root_is_rejected() -> None:
    outcome = build_candidate_groups(
        [
            _product("Cadena oro", "cadena"),
            _product("Cadena plata", "cadena"),
        ],
        VOCAB,
    )
    assert outcome.proposals == ()
    assert [group.reason for group in outcome.rejected] == ["root_is_bare_piece_type"]


def test_size_is_removed_from_any_position_not_only_the_suffix() -> None:
    """`Anillo lapislázuli mediano oro` hides its size behind a material token."""
    proposal = _only(
        [
            _product("Anillo lapislázuli pequeño"),
            _product("Anillo lapislázuli mediano"),
            _product("Anillo lapislázuli pequeño oro"),
            _product("Anillo lapislázuli mediano oro"),
        ]
    )
    assert proposal.root == "anillo lapislazuli"
    assert len(proposal.members) == 4


def test_variant_label_is_verbatim_not_translated() -> None:
    """`mini` is the workshop's word. Recording it as `XS` would invent a scale."""
    proposal = _only(
        [
            _product("Anillo mini conchiglie"),
            _product("Anillo conchiglie"),
        ]
    )
    labels = [member.variant_label for member in proposal.members]
    assert "mini" in labels
    assert "XS" not in labels


def test_accented_label_keeps_its_spelling() -> None:
    proposal = _only(
        [
            _product("Colgante hoja roble pequeña", "colgante"),
            _product("Colgante hoja roble grande", "colgante"),
        ]
    )
    assert "pequeña" in [member.variant_label for member in proposal.members]


def test_base_member_has_null_variant_label() -> None:
    proposal = _only(
        [
            _product("Anillo mini conchiglie"),
            _product("Anillo conchiglie"),
        ]
    )
    assert None in [member.variant_label for member in proposal.members]


def test_members_ordered_by_canonical_rank_not_alphabetically() -> None:
    proposal = _only(
        [
            _product("Anillo erizo de mar XL"),
            _product("Anillo erizo de mar S"),
            _product("Anillo erizo de mar L"),
            _product("Anillo erizo de mar M"),
        ]
    )
    assert [member.variant_label for member in proposal.members] == ["S", "M", "L", "XL"]
    assert [member.position for member in proposal.members] == [0, 1, 2, 3]


def test_two_axis_family_labels_stay_unique() -> None:
    proposal = _only(
        [
            _product("Anillo lapislázuli pequeño"),
            _product("Anillo lapislázuli mediano"),
            _product("Anillo lapislázuli pequeño oro"),
            _product("Anillo lapislázuli mediano oro"),
        ]
    )
    labels = [member.variant_label for member in proposal.members]
    assert len(set(labels)) == len(labels)
    assert any(label and "oro" in label for label in labels)


def test_a_material_every_member_shares_is_not_a_label() -> None:
    """`oro` on both members distinguishes nothing, so only the size may label."""
    proposal = _only(
        [
            _product("Colgante conchiglie Oro", "colgante"),
            _product("Colgante mini conchiglie Oro", "colgante"),
        ]
    )
    labels = [member.variant_label for member in proposal.members]
    assert labels == ["mini", None]


def test_a_single_product_is_not_a_family() -> None:
    outcome = build_candidate_groups([_product("Anillo erizo de mar S")], VOCAB)
    assert outcome.proposals == ()


def test_grouping_is_deterministic_for_the_same_catalogue() -> None:
    products = [
        _product("Anillo erizo de mar S"),
        _product("Anillo erizo de mar M"),
        _product("Anillo plata S"),
        _product("Anillo plata M"),
    ]
    first = build_candidate_groups(products, VOCAB)
    second = build_candidate_groups(products, VOCAB)
    assert [p.root for p in first.proposals] == [p.root for p in second.proposals]
    assert [
        [m.variant_label for m in p.members] for p in first.proposals
    ] == [[m.variant_label for m in p.members] for p in second.proposals]


def test_roots_never_collapse_unrelated_products() -> None:
    """Two `Ses Salines` rings differ by `piedra`, so removing `grande` keeps them apart."""
    assert _roots(
        [
            _product("Anillo grande Ses Salines plata"),
            _product("Anillo grande Ses Salines plata piedra"),
        ]
    ) == set()


def test_two_indistinguishable_products_are_rejected_not_proposed() -> None:
    """A duplicate label would be refused by the family service's uniqueness index.

    Emitting it turns an actionable review item into a database constraint error,
    so the group is reported instead. The real catalogue has no duplicate names
    today; a generated one found this, and nothing stops one appearing tomorrow.
    """
    outcome = build_candidate_groups(
        [
            _product("Anillo rama oro grande", sku="SKU-A"),
            _product("Anillo rama oro grande", sku="SKU-B"),
            _product("Anillo rama mediana"),
        ],
        VOCAB,
    )
    assert outcome.proposals == ()
    assert [group.reason for group in outcome.rejected] == ["duplicate_variant_labels"]
