"""Wires the family suggestion pipeline to its contract. Delivered by C18a.

Four steps, in this order and for these reasons: read the active index, group by
root, ask the vectors whether they support what the roots produced, and translate.
The veto runs **after** grouping and never decides membership — its query needs to
know which products ended up competing with which, which is only knowable once the
groups exist.
"""

from __future__ import annotations

from jbg_ai.api.schemas.families import (
    ExcludedProductModel,
    FamilyProposalModel,
    FamilySuggestRequest,
    FamilySuggestResponse,
    ProposedFamilyMember,
    RejectedGroupModel,
)
from jbg_ai.config.settings import Settings
from jbg_ai.families.errors import InvalidPieceTypeError
from jbg_ai.families.grouping import FamilyProposal, build_candidate_groups
from jbg_ai.families.repository import load_candidates, load_member_similarities
from jbg_ai.families.veto import apply_relative_veto
from jbg_ai.families.vocabulary import load_family_vocabulary

__all__ = ["suggest_families", "validated_piece_type"]


async def suggest_families(
    request: FamilySuggestRequest, settings: Settings, *, trace_id: str
) -> FamilySuggestResponse:
    """Produce family proposals plus everything the run refused to propose."""
    vocabulary = load_family_vocabulary()

    piece_type = validated_piece_type(request.piece_type, vocabulary)
    candidates = await load_candidates(settings, piece_type)
    outcome = build_candidate_groups(candidates, vocabulary)

    # Keyed by piece type *and* root, which is how the grouper keys a proposal. Two
    # families of different piece types can share a root, and collapsing them here
    # would make each other's members look like siblings and cancel the veto between
    # them.
    membership = {
        member.sku: (proposal.piece_type, proposal.root)
        for proposal in outcome.proposals
        for member in proposal.members
    }
    similarities = await load_member_similarities(settings, membership)
    vetoed = [
        apply_relative_veto(proposal, similarities, margin=settings.jpv_family_veto_margin)
        for proposal in outcome.proposals
    ]

    return FamilySuggestResponse(
        # Only proposals are capped. Refusals are never truncated: a cap that hides
        # a catalogue problem is worse than a long list.
        proposals=[_proposal_model(p) for p in vetoed[: request.max_proposals]],
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
        already_in_family_count=outcome.already_in_family_count,
        trace_id=trace_id,
    )


def validated_piece_type(raw: str | None, vocabulary: object) -> str | None:
    """Reject an unknown piece type instead of silently returning nothing.

    A typo would otherwise narrow the query to zero candidates and answer with an
    empty, entirely plausible-looking result.
    """
    if raw is None:
        return None
    canonical = getattr(vocabulary, "piece_type_tokens", {})
    from jbg_ai.enrichment.vocab import fold

    resolved = canonical.get(fold(raw))
    if resolved is None:
        raise InvalidPieceTypeError(raw)
    return resolved


def _proposal_model(proposal: FamilyProposal) -> FamilyProposalModel:
    return FamilyProposalModel(
        root=proposal.root,
        suggested_name=proposal.suggested_name,
        piece_type=proposal.piece_type,
        members=[
            ProposedFamilyMember(
                product_id=str(member.product_id),
                sku=member.sku,
                name=member.name,
                variant_label=member.variant_label,
                position=member.position,
                flagged_for_review=member.flagged_for_review,
                review_reason=member.review_reason,
                margin=member.distance,
            )
            for member in proposal.members
        ],
    )
