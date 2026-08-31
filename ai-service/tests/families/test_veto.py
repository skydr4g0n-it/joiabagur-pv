"""Relative embedding veto over formed candidates. Delivered by C18a.

The veto is comparative on purpose. These tests pin the two properties that an
earlier implementation got wrong: it compares **between** proposed families rather
than against a group's own centre, and it **marks** rather than removes.
"""

from __future__ import annotations

import uuid

from jbg_ai.families.grouping import FamilyProposal, ProposedMember
from jbg_ai.families.veto import VETO_REASON, MemberSimilarity, apply_relative_veto

MARGIN = 0.05


def _member(sku: str, position: int) -> ProposedMember:
    return ProposedMember(
        product_id=uuid.uuid4(),
        sku=sku,
        name=f"Anillo {sku}",
        variant_label=None,
        position=position,
    )


def _proposal(*skus: str) -> FamilyProposal:
    return FamilyProposal(
        root="anillo erizo de mar",
        piece_type="anillo",
        members=tuple(_member(sku, index) for index, sku in enumerate(skus)),
    )


def test_veto_flags_member_without_removing_it() -> None:
    proposal = _proposal("A", "B", "C")
    similarities = {
        "A": MemberSimilarity(worst_sibling=0.90, best_stranger=0.80),
        "B": MemberSimilarity(worst_sibling=0.90, best_stranger=0.80),
        "C": MemberSimilarity(worst_sibling=0.79, best_stranger=0.95, stranger_family="otra"),
    }

    result = apply_relative_veto(proposal, similarities, margin=MARGIN)

    assert len(result.members) == 3, "a flagged member is marked, never dropped"
    flagged = [member for member in result.members if member.flagged_for_review]
    assert [member.sku for member in flagged] == ["C"]
    assert flagged[0].review_reason == VETO_REASON
    assert flagged[0].distance == 0.16


def test_a_stranger_inside_the_margin_does_not_flag() -> None:
    """Beating the worst sibling by a hair is noise, not evidence."""
    proposal = _proposal("A", "B")
    similarities = {
        "A": MemberSimilarity(worst_sibling=0.90, best_stranger=0.91),
        "B": MemberSimilarity(worst_sibling=0.90, best_stranger=0.80),
    }

    result = apply_relative_veto(proposal, similarities, margin=MARGIN)

    assert not any(member.flagged_for_review for member in result.members)


def test_no_global_threshold_decides_membership() -> None:
    """Every member sits at a low absolute similarity, yet none is flagged.

    An absolute cutoff would reject the whole family. The veto only cares whether
    something else is closer.
    """
    proposal = _proposal("A", "B", "C")
    similarities = {
        sku: MemberSimilarity(worst_sibling=0.62, best_stranger=0.40) for sku in ("A", "B", "C")
    }

    result = apply_relative_veto(proposal, similarities, margin=MARGIN)

    assert not any(member.flagged_for_review for member in result.members)


def test_a_member_without_similarities_is_left_alone() -> None:
    """A missing vector is an indexing gap, not evidence against the membership."""
    proposal = _proposal("A", "B")
    similarities = {"A": MemberSimilarity(worst_sibling=None, best_stranger=None)}

    result = apply_relative_veto(proposal, similarities, margin=MARGIN)

    assert not any(member.flagged_for_review for member in result.members)


def test_margin_is_honoured_as_given() -> None:
    """The same data flags or not depending only on the configured margin."""
    proposal = _proposal("A", "B")
    similarities = {
        "A": MemberSimilarity(worst_sibling=0.80, best_stranger=0.86),
        "B": MemberSimilarity(worst_sibling=0.90, best_stranger=0.70),
    }

    lenient = apply_relative_veto(proposal, similarities, margin=0.10)
    strict = apply_relative_veto(proposal, similarities, margin=0.02)

    assert not any(member.flagged_for_review for member in lenient.members)
    assert [member.sku for member in strict.members if member.flagged_for_review] == ["A"]


def test_margin_is_read_from_configuration_not_hard_coded() -> None:
    """Fails if anyone inlines the threshold: the sweep of C24 depends on this."""
    from jbg_ai.config.settings import Settings

    settings = Settings(
        app_env="development",
        service_version="test",
        jwt_secret="x" * 32,
        jpv_family_veto_margin=0.42,
    )
    assert settings.jpv_family_veto_margin == 0.42

    proposal = _proposal("A", "B")
    similarities = {
        "A": MemberSimilarity(worst_sibling=0.50, best_stranger=0.80),
        "B": MemberSimilarity(worst_sibling=0.90, best_stranger=0.70),
    }
    result = apply_relative_veto(
        proposal, similarities, margin=settings.jpv_family_veto_margin
    )
    assert not any(member.flagged_for_review for member in result.members), (
        "a 0.30 gap must not flag under a 0.42 margin"
    )


def test_membership_order_and_labels_survive_the_veto() -> None:
    proposal = _proposal("A", "B", "C")
    similarities = {
        "B": MemberSimilarity(worst_sibling=0.70, best_stranger=0.95, stranger_family="otra")
    }

    result = apply_relative_veto(proposal, similarities, margin=MARGIN)

    assert [member.sku for member in result.members] == ["A", "B", "C"]
    assert [member.position for member in result.members] == [0, 1, 2]
