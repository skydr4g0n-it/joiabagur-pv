"""Audit of the families that already exist. Delivered by C18b.

C18a proposed and wrote; this reads back what it wrote and asks the vectors whether
they still agree. The two questions it answers are **one comparison read from either
side of the membership line**:

* a product inside a family — is a product of *another* family closer to it than its
  own worst sibling?
* a product inside none — is it closer to family F than F's own worst sibling?

The first is the C18a veto with a different universe (persisted families instead of
proposed ones) and it reuses `apply_relative_veto` rather than restating it. The
second is the same arithmetic pointed outwards.

**Why recomputing is the only route to the first list.** Suggestion converges by
excluding products that already belong somewhere, and C18a deliberately kept no
proposal store, so the members it flagged at approval time are unreachable by every
later suggestion: the flags lived in one HTTP response and the products are now
inside families. Nothing else can produce that queue.

**Why the orphan criterion is a relative margin and not neighbourhood purity.**
Measured over this corpus, purity nominates 55 synthetic products against 19 real
ones, because C06b built `v2`/`v3`/`v4`/`v5` families that are distinct by
construction and purity reads them as members that went missing. The margin
nominates 21 real against 1 synthetic. Purity is computed and returned, and it
ranks; it never selects.

Nothing here writes. Recording a verdict is a .NET operation on another route, and
that separation is what lets a test assert that the audit changed nothing.
"""

from __future__ import annotations

from jbg_ai.api.schemas.families import (
    ExcludedProductModel,
    FamilyAuditRequest,
    FamilyAuditResponse,
    FlaggedMemberModel,
    OrphanCandidateModel,
    RejectedGroupModel,
)
from jbg_ai.config.settings import Settings
from jbg_ai.families.grouping import (
    FamilyProposal,
    ProposedMember,
    build_candidate_groups,
)
from jbg_ai.families.orchestrator import validated_piece_type
from jbg_ai.families.repository import (
    OrphanCandidate,
    PersistedMember,
    load_candidates,
    load_family_memberships,
    load_member_similarities,
    load_orphan_candidates,
)
from jbg_ai.families.veto import apply_relative_veto
from jbg_ai.families.vocabulary import load_family_vocabulary

__all__ = ["audit_families"]


async def audit_families(
    request: FamilyAuditRequest, settings: Settings, *, trace_id: str
) -> FamilyAuditResponse:
    """Report unsupported memberships, orphan candidates, and what is still refused."""
    vocabulary = load_family_vocabulary()
    piece_type = validated_piece_type(request.piece_type, vocabulary)

    veto_margin = (
        request.veto_margin
        if request.veto_margin is not None
        else settings.jpv_family_veto_margin
    )
    orphan_margin = (
        request.orphan_margin
        if request.orphan_margin is not None
        else settings.jpv_family_orphan_margin
    )

    judged = {_pair(p.product_id, p.family_id) for p in request.judged_pairs}

    members = await load_family_memberships(settings)
    if piece_type is not None:
        members = [m for m in members if m.piece_type == piece_type]

    flagged = await _flag_unsupported_members(settings, members, margin=veto_margin)

    orphans = await load_orphan_candidates(settings, margin=orphan_margin)
    if piece_type is not None:
        orphans = [o for o in orphans if o.piece_type == piece_type]

    # The gate and the guards are recomputed rather than remembered: the corpus has
    # moved since C18a — 32 entries left the index — and a stale list would report
    # products that are no longer candidates for anything.
    candidates = await load_candidates(settings, piece_type)
    outcome = build_candidate_groups(candidates, vocabulary)

    return FamilyAuditResponse(
        flagged_members=[
            model
            for model in flagged
            if _pair(model.product_id, model.family_id) not in judged
        ],
        # Only candidates are capped. Refusals are never truncated, for the same
        # reason `suggest` never truncates them: a cap that hides a catalogue problem
        # is worse than a long list.
        orphan_candidates=[
            _orphan_model(orphan)
            for orphan in orphans
            if _pair(str(orphan.product_id), str(orphan.family_id)) not in judged
        ][: request.max_orphans],
        rejected_groups=[
            RejectedGroupModel(
                root=group.root,
                piece_type=group.piece_type,
                reason=group.reason,
                product_names=list(group.product_names),
            )
            for group in outcome.rejected
        ],
        excluded_products=[
            ExcludedProductModel(
                product_id=str(product.product_id),
                sku=product.sku,
                name=product.name,
                reason=product.reason,
            )
            for product in outcome.excluded
        ],
        families_reviewed_count=len({m.family_id for m in members}),
        members_examined_count=len(members),
        trace_id=trace_id,
    )


def _pair(product_id: str, family_id: str) -> tuple[str, str]:
    """Case-folded pair key: .NET serialises GUIDs upper-cased, PostgreSQL lower-cased."""
    return (product_id.lower(), family_id.lower())


async def _flag_unsupported_members(
    settings: Settings, members: list[PersistedMember], *, margin: float
) -> list[FlaggedMemberModel]:
    """Run the C18a veto over persisted families instead of proposed ones.

    The reuse is exact and deliberate. `load_member_similarities` keys a membership by
    the identity of the family a product was proposed for; here that identity is the
    family it actually belongs to, so the same query and the same marking rule answer
    the same question about rows rather than about candidates. Restating the veto would
    give the two paths room to drift, and the one thing this queue must not do is
    disagree with the one C18a produced.
    """
    if not members:
        return []

    by_sku = {member.sku: member for member in members}
    membership = {
        member.sku: (member.piece_type or "", str(member.family_id)) for member in members
    }
    similarities = await load_member_similarities(settings, membership)

    families: dict[str, list[PersistedMember]] = {}
    for member in members:
        families.setdefault(str(member.family_id), []).append(member)

    flagged: list[FlaggedMemberModel] = []
    for family_id, rows in families.items():
        # `apply_relative_veto` takes a proposal, so a persisted family is handed to it
        # as one. Root and position carry no meaning here — the marking rule reads
        # neither — and the alternative was a second copy of its marking logic.
        proposal = FamilyProposal(
            root=rows[0].family_name or "",
            piece_type=rows[0].piece_type or "",
            members=tuple(
                ProposedMember(
                    product_id=row.product_id,
                    sku=row.sku,
                    name=row.name,
                    variant_label=row.variant_label,
                    position=index,
                )
                for index, row in enumerate(rows)
            ),
        )
        for member in apply_relative_veto(proposal, similarities, margin=margin).members:
            if not member.flagged_for_review:
                continue
            row = by_sku[member.sku]
            similarity = similarities.get(member.sku)
            flagged.append(
                FlaggedMemberModel(
                    product_id=str(row.product_id),
                    sku=row.sku,
                    name=row.name,
                    variant_label=row.variant_label,
                    family_id=family_id,
                    family_name=row.family_name,
                    margin=member.distance or 0.0,
                    stranger_family_id=(
                        similarity.stranger_family if similarity is not None else None
                    ),
                )
            )

    flagged.sort(key=lambda model: (-model.margin, model.sku))
    return flagged


def _orphan_model(orphan: OrphanCandidate) -> OrphanCandidateModel:
    return OrphanCandidateModel(
        product_id=str(orphan.product_id),
        sku=orphan.sku,
        name=orphan.name,
        piece_type=orphan.piece_type,
        data_origin=orphan.data_origin,
        family_id=str(orphan.family_id),
        family_name=orphan.family_name,
        similarity=round(orphan.similarity, 6),
        worst_sibling=round(orphan.worst_sibling, 6),
        margin=round(orphan.margin, 6),
        purity=orphan.purity,
    )
