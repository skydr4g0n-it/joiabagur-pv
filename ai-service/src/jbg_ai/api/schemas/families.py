"""Family suggestion contracts. Delivered by C18a.

The response carries **three** lists, not one. Proposals are the answer; the groups
a guard refused and the products the gate excluded are the other half of it. An
omission nobody can see is indistinguishable from a product that simply had no
siblings, and both refusals turn out to name real catalogue problems — workshop
services filed as jewellery, pieces the closed vocabulary cannot classify.

Nothing here writes. Applying an accepted subset is a .NET operation, because the
catalogue's truth lives there and only its family service stamps the watermark an
incremental index pull depends on.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from jbg_ai.api.schemas.common import TracedResponse

MAX_PROPOSALS = 500


class FamilySuggestRequest(BaseModel):
    """Optional narrowing. An empty body proposes over the whole active index."""

    piece_type: str | None = Field(
        default=None,
        description="Restrict to one closed-vocabulary piece type; null means all",
    )
    max_proposals: int = Field(
        default=MAX_PROPOSALS,
        ge=1,
        le=MAX_PROPOSALS,
        description="Upper bound on returned proposals; refusals are never truncated",
    )


class ProposedFamilyMember(BaseModel):
    """One product inside a proposal, with what tells it from its siblings."""

    product_id: str
    sku: str
    name: str
    variant_label: str | None = Field(
        default=None,
        description="Null for the base piece, which is a variant value and not a gap",
    )
    position: int = Field(..., ge=0, description="Order by canonical size rank, gap-free")
    flagged_for_review: bool = Field(
        default=False,
        description="A product of another proposed family sits closer than this member's worst sibling",
    )
    review_reason: str | None = None
    margin: float | None = Field(
        default=None,
        description="How far the nearest stranger beat the worst sibling; null when not flagged",
    )


class FamilyProposalModel(BaseModel):
    """A candidate family: one piece type, one root, two or more members."""

    root: str
    suggested_name: str
    piece_type: str
    members: list[ProposedFamilyMember] = Field(..., min_length=2)


class RejectedGroupModel(BaseModel):
    """A group a guard refused, reported so a person can look at it."""

    root: str
    piece_type: str | None = None
    reason: str = Field(
        ...,
        description="root_too_short | root_is_bare_piece_type | empty_root | duplicate_variant_labels",
    )
    product_names: list[str] = Field(default_factory=list)


class ExcludedProductModel(BaseModel):
    """A product the piece-type gate removed before grouping."""

    product_id: str
    sku: str
    name: str
    reason: str = Field(..., description="no_piece_type")


class FamilySuggestResponse(TracedResponse):
    proposals: list[FamilyProposalModel] = Field(default_factory=list)
    rejected_groups: list[RejectedGroupModel] = Field(default_factory=list)
    excluded_products: list[ExcludedProductModel] = Field(default_factory=list)
    already_in_family_count: int = Field(
        default=0,
        ge=0,
        description=(
            "Products skipped for already belonging to a family. Counted rather than "
            "listed: after the first approved batch they are hundreds, and their "
            "exclusion is the convergence rule working, not a finding"
        ),
    )


# --------------------------------------------------------------------------------------
# C18b — the audit contract: the same comparison, read from both sides of membership
# --------------------------------------------------------------------------------------

MAX_ORPHAN_CANDIDATES = 500


class JudgedPair(BaseModel):
    """A `(product, family)` pair a person has already ruled on.

    Travels **in the request**. The service holds no verdict of its own and must not:
    the catalogue's truth is .NET's, and a store of judgements beside the index would
    be state nothing invalidates. The caller brings what it knows, exactly as `apply`
    brings back the proposals it accepted.
    """

    product_id: str
    family_id: str


class FamilyAuditRequest(BaseModel):
    """Optional narrowing and thresholds. An empty body audits the whole active index."""

    piece_type: str | None = Field(
        default=None,
        description="Restrict to one closed-vocabulary piece type; null means all",
    )
    veto_margin: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Overrides JPV_FAMILY_VETO_MARGIN for this run; null uses configuration",
    )
    orphan_margin: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Overrides JPV_FAMILY_ORPHAN_MARGIN for this run; null uses configuration",
    )
    max_orphans: int = Field(
        default=MAX_ORPHAN_CANDIDATES,
        ge=1,
        le=MAX_ORPHAN_CANDIDATES,
        description="Upper bound on returned candidates; refusals are never truncated",
    )
    judged_pairs: list[JudgedPair] = Field(
        default_factory=list,
        description="Pairs already ruled on, omitted from both lists of this response",
    )


class FlaggedMemberModel(BaseModel):
    """A member of an existing family that the vectors do not support."""

    product_id: str
    sku: str
    name: str
    variant_label: str | None = Field(
        default=None,
        description="Null is the base piece, a legitimate variant value and not a gap",
    )
    family_id: str
    family_name: str | None = None
    margin: float = Field(
        ...,
        description="How far the nearest stranger beat this member's own worst sibling",
    )
    stranger_family_id: str | None = Field(
        default=None,
        description="Family of the product that beat the worst sibling",
    )
    reason: str = Field(default="closer_to_another_family")


class OrphanCandidateModel(BaseModel):
    """A product belonging to no family that looks like it belongs to one."""

    product_id: str
    sku: str
    name: str
    piece_type: str
    data_origin: str = Field(
        ...,
        description=(
            "`real` or `synthetic`. Reported because the two populations behave very "
            "differently here and every metric must be able to separate them"
        ),
    )
    family_id: str
    family_name: str | None = None
    similarity: float
    worst_sibling: float = Field(
        ..., description="Lowest similarity observed inside the target family"
    )
    margin: float = Field(
        ..., description="similarity - worst_sibling. This is the nomination criterion"
    )
    purity: int = Field(
        ...,
        ge=0,
        le=5,
        description=(
            "Of the five nearest neighbours of the same piece type, how many belong to "
            "this family. A **ranking signal only**: purity nominates 55 synthetic "
            "against 19 real over this corpus, because the deliberate vN families it "
            "cannot separate from a missing member are synthetic by construction"
        ),
    )


class FamilyAuditResponse(TracedResponse):
    """Both sides of the membership line, plus what the run still refuses to propose."""

    flagged_members: list[FlaggedMemberModel] = Field(default_factory=list)
    orphan_candidates: list[OrphanCandidateModel] = Field(default_factory=list)
    rejected_groups: list[RejectedGroupModel] = Field(default_factory=list)
    excluded_products: list[ExcludedProductModel] = Field(default_factory=list)
    families_reviewed_count: int = Field(
        default=0,
        ge=0,
        description="Families the audit examined, so an empty flag list is readable",
    )
    members_examined_count: int = Field(
        default=0,
        ge=0,
        description="Memberships the audit examined, for the same reason",
    )
