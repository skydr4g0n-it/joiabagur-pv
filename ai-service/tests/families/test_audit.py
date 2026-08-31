"""Audit over persisted families. Delivered by C18b.

These tests pin the two properties the design argued for with measurement, because
both are the kind that get "simplified" back into the mistake they replaced:

* the flagged queue is recomputed over the families that **exist**, since suggestion
  converges by excluding their members and the original flags were never persisted;
* orphans are nominated by a **relative margin** and never by neighbourhood purity,
  which over this corpus fires on 55 synthetic products against 19 real ones.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from jbg_ai.api.schemas.families import FamilyAuditRequest, JudgedPair
from jbg_ai.families import audit as audit_module
from jbg_ai.families.audit import audit_families
from jbg_ai.families.grouping import CandidateProduct
from jbg_ai.families.repository import OrphanCandidate, PersistedMember
from jbg_ai.families.veto import MemberSimilarity

FAMILY_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
FAMILY_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
MARGIN = 0.05


class _Settings:
    """Only what the orchestrator reads. Never touches a database or a provider."""

    jpv_family_veto_margin = MARGIN
    jpv_family_orphan_margin = 0.0


def _member(sku: str, family_id: uuid.UUID, *, piece_type: str = "anillo") -> PersistedMember:
    return PersistedMember(
        product_id=uuid.uuid4(),
        sku=sku,
        name=f"Anillo {sku}",
        piece_type=piece_type,
        family_id=family_id,
        family_name="Anillo erizo de mar",
        variant_label=sku,
    )


def _orphan(
    sku: str,
    *,
    family_id: uuid.UUID = FAMILY_A,
    margin: float = 0.06,
    purity: int = 0,
    piece_type: str = "anillo",
    data_origin: str = "real",
) -> OrphanCandidate:
    return OrphanCandidate(
        product_id=uuid.uuid4(),
        sku=sku,
        name=f"Anillo {sku}",
        piece_type=piece_type,
        data_origin=data_origin,
        family_id=family_id,
        family_name="Anillo erizo de mar",
        similarity=0.90 + margin,
        worst_sibling=0.90,
        margin=margin,
        purity=purity,
    )


@pytest.fixture
def wiring(monkeypatch: pytest.MonkeyPatch):
    """Replace every repository call, so nothing here reaches PostgreSQL."""

    state: dict[str, object] = {
        "members": [],
        "similarities": {},
        "orphans": [],
        "candidates": [],
        "orphan_margin_seen": None,
    }

    async def fake_members(settings):  # noqa: ANN001, ANN202
        return list(state["members"])  # type: ignore[arg-type]

    async def fake_similarities(settings, membership):  # noqa: ANN001, ANN202
        state["membership_seen"] = dict(membership)
        return dict(state["similarities"])  # type: ignore[arg-type]

    async def fake_orphans(settings, *, margin):  # noqa: ANN001, ANN202
        state["orphan_margin_seen"] = margin
        return [o for o in state["orphans"] if o.margin > margin]  # type: ignore[union-attr]

    async def fake_candidates(settings, piece_type=None):  # noqa: ANN001, ANN202
        return list(state["candidates"])  # type: ignore[arg-type]

    monkeypatch.setattr(audit_module, "load_family_memberships", fake_members)
    monkeypatch.setattr(audit_module, "load_member_similarities", fake_similarities)
    monkeypatch.setattr(audit_module, "load_orphan_candidates", fake_orphans)
    monkeypatch.setattr(audit_module, "load_candidates", fake_candidates)
    return state


def _run(state, request: FamilyAuditRequest | None = None):  # noqa: ANN001, ANN202
    """Same shape as `tests/retrieval/test_orchestrator._run`.

    The suite has no async pytest plugin and does not need one: every coroutine here
    is driven from a synchronous test, which keeps the dependency set as it is.
    """
    return asyncio.run(
        audit_families(
            request or FamilyAuditRequest(),
            _Settings(),  # type: ignore[arg-type]
            trace_id="test",
        )
    )



def test_audit_flags_member_when_stranger_beats_worst_sibling(wiring) -> None:  # noqa: ANN001
    """The C18a veto, run over rows instead of candidates."""
    wiring["members"] = [_member("A", FAMILY_A), _member("B", FAMILY_A)]
    wiring["similarities"] = {
        "A": MemberSimilarity(worst_sibling=0.90, best_stranger=0.80),
        "B": MemberSimilarity(
            worst_sibling=0.80, best_stranger=0.95, stranger_family=str(FAMILY_B)
        ),
    }

    response = _run(wiring)

    assert [flag.sku for flag in response.flagged_members] == ["B"]
    assert response.flagged_members[0].margin == pytest.approx(0.15)
    assert response.flagged_members[0].family_id == str(FAMILY_A)
    assert response.flagged_members[0].stranger_family_id == str(FAMILY_B)
    assert response.members_examined_count == 2
    assert response.families_reviewed_count == 1



def test_flag_is_produced_for_products_suggestion_can_no_longer_see(wiring) -> None:  # noqa: ANN001
    """The point of the whole route.

    Every member here belongs to a family, so `suggest` would exclude all of them by
    the convergence rule and return nothing. The audit still answers.
    """
    wiring["members"] = [_member("A", FAMILY_A), _member("B", FAMILY_A)]
    wiring["similarities"] = {
        "B": MemberSimilarity(
            worst_sibling=0.80, best_stranger=0.95, stranger_family=str(FAMILY_B)
        )
    }
    wiring["candidates"] = []  # nothing groupable is left, exactly as today

    response = _run(wiring)

    assert response.flagged_members
    assert not response.rejected_groups



def test_a_member_without_similarity_is_not_flagged(wiring) -> None:  # noqa: ANN001
    """A missing vector is an indexing gap, not evidence against a membership."""
    wiring["members"] = [_member("A", FAMILY_A)]
    wiring["similarities"] = {}

    assert not (_run(wiring)).flagged_members



def test_orphan_detection_lists_unassigned_similar_products(wiring) -> None:  # noqa: ANN001
    wiring["orphans"] = [_orphan("X", margin=0.09), _orphan("Y", margin=0.02)]

    candidates = (_run(wiring)).orphan_candidates

    assert [c.sku for c in candidates] == ["X", "Y"]
    assert candidates[0].margin == pytest.approx(0.09)
    assert candidates[0].worst_sibling == pytest.approx(0.90)
    assert candidates[0].data_origin == "real"



def test_purity_does_not_nominate(wiring) -> None:  # noqa: ANN001
    """Purity travels as a ranking signal and must never select.

    A product with four of five neighbours in one family but no margin over that
    family's worst sibling is exactly the synthetic `vN` case: a family built to be
    distinct, which purity reads as a member gone missing.
    """
    wiring["orphans"] = [_orphan("PURE", margin=0.0, purity=4, data_origin="synthetic")]

    assert not (_run(wiring)).orphan_candidates



def test_orphan_margin_comes_from_configuration(wiring) -> None:  # noqa: ANN001
    wiring["orphans"] = [_orphan("X", margin=0.03)]

    assert (_run(wiring)).orphan_candidates
    tightened = _run(wiring, FamilyAuditRequest(orphan_margin=0.05))
    assert not tightened.orphan_candidates
    assert wiring["orphan_margin_seen"] == 0.05



def test_orphan_nomination_never_crosses_piece_type(wiring) -> None:  # noqa: ANN001
    wiring["members"] = [_member("A", FAMILY_A, piece_type="anillo")]
    wiring["orphans"] = [
        _orphan("RING", piece_type="anillo"),
        _orphan("NECK", piece_type="collar"),
    ]

    narrowed = _run(wiring, FamilyAuditRequest(piece_type="anillo"))

    assert [c.sku for c in narrowed.orphan_candidates] == ["RING"]



def test_judged_pairs_are_omitted_from_both_lists(wiring) -> None:  # noqa: ANN001
    """A dismissal is remembered, and the caller is the one that remembers it."""
    member = _member("B", FAMILY_A)
    orphan = _orphan("X")
    wiring["members"] = [member]
    wiring["similarities"] = {
        "B": MemberSimilarity(worst_sibling=0.80, best_stranger=0.95)
    }
    wiring["orphans"] = [orphan]

    judged = FamilyAuditRequest(
        judged_pairs=[
            JudgedPair(product_id=str(member.product_id), family_id=str(FAMILY_A)),
            JudgedPair(product_id=str(orphan.product_id), family_id=str(FAMILY_A)),
        ]
    )
    response = _run(wiring, judged)

    assert not response.flagged_members
    assert not response.orphan_candidates
    # And without them the same audit reports both again: nothing was persisted.
    again = _run(wiring)
    assert again.flagged_members and again.orphan_candidates



def test_judged_pairs_match_regardless_of_guid_case(wiring) -> None:  # noqa: ANN001
    """.NET serialises GUIDs upper-cased and PostgreSQL returns them lower-cased.

    Comparing them raw would let every dismissal silently fail to apply, and the
    symptom — the same candidate returning forever — looks like a persistence bug.
    """
    orphan = _orphan("X")
    wiring["orphans"] = [orphan]

    response = _run(
        wiring,
        FamilyAuditRequest(
            judged_pairs=[
                JudgedPair(
                    product_id=str(orphan.product_id).upper(),
                    family_id=str(FAMILY_A).upper(),
                )
            ]
        ),
    )

    assert not response.orphan_candidates



def test_the_candidate_cap_never_truncates_a_refusal(wiring) -> None:  # noqa: ANN001
    wiring["orphans"] = [_orphan(f"X{i}", margin=0.1 - i / 100) for i in range(4)]
    wiring["candidates"] = [
        CandidateProduct(
            product_id=uuid.uuid4(),
            sku="SKU-NO-TYPE",
            name="Diadema perlas",
            piece_type=None,
        )
    ]

    response = _run(wiring, FamilyAuditRequest(max_orphans=2))

    assert len(response.orphan_candidates) == 2
    assert len(response.excluded_products) == 1



def test_audit_is_deterministic(wiring) -> None:  # noqa: ANN001
    wiring["members"] = [_member("A", FAMILY_A), _member("B", FAMILY_A)]
    wiring["similarities"] = {
        "B": MemberSimilarity(worst_sibling=0.80, best_stranger=0.95)
    }
    wiring["orphans"] = [_orphan("X", margin=0.09), _orphan("Y", margin=0.07)]

    first, second = _run(wiring), _run(wiring)

    assert first.model_dump() == second.model_dump()



def test_the_veto_universe_is_keyed_by_the_family_a_product_belongs_to(
    wiring,  # noqa: ANN001
) -> None:
    """Two members of different families must be able to veto each other.

    `load_member_similarities` decides "sibling or stranger" by comparing the values
    of this mapping, so keying it on anything shared between families would make every
    stranger look like a sibling and cancel the whole queue.
    """
    wiring["members"] = [_member("A", FAMILY_A), _member("B", FAMILY_B)]

    _run(wiring)

    seen = wiring["membership_seen"]
    assert seen["A"] != seen["B"]
    assert seen["A"][1] == str(FAMILY_A)
