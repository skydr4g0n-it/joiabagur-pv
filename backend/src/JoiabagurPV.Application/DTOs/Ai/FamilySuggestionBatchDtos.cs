using JoiabagurPV.Application.DTOs.Products;

namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// What the administrator asks for when requesting family suggestions.
/// </summary>
public class FamilySuggestionsRequest
{
    /// <summary>Restrict to one closed-vocabulary piece type; null proposes over all of them.</summary>
    public string? PieceType { get; set; }
}

/// <summary>
/// One member of a family the administrator accepts.
/// </summary>
public class ApprovedFamilyMemberRequest
{
    /// <summary>Product to make a member.</summary>
    public Guid ProductId { get; set; }

    /// <summary>Label that tells this member from its siblings. Null for the base piece.</summary>
    public string? VariantLabel { get; set; }
}

/// <summary>
/// One family the administrator accepts, as returned by the suggestion call.
/// </summary>
public class ApprovedFamilyRequest
{
    /// <summary>Name to give the family.</summary>
    public string Name { get; set; } = string.Empty;

    /// <summary>Optional description.</summary>
    public string? Description { get; set; }

    /// <summary>Members in the order they should hold.</summary>
    public List<ApprovedFamilyMemberRequest> Members { get; set; } = [];
}

/// <summary>
/// The subset of proposals an administrator accepts.
/// </summary>
/// <remarks>
/// The client returns what it accepts rather than referring to a stored proposal by identifier.
/// That is what lets the whole flow work without persisting suggestions anywhere: there is no
/// table to keep in step with the catalog and nothing that can go stale between the two calls.
/// The price is that a rejection is not remembered — a discarded proposal reappears on the next
/// run — which is acceptable while approval happens in batches and is C18b's to solve.
/// </remarks>
public class ApplyFamilySuggestionsRequest
{
    /// <summary>Largest batch accepted in one call.</summary>
    public const int MaxFamilies = 500;

    /// <summary>Families to create.</summary>
    public List<ApprovedFamilyRequest> Families { get; set; } = [];
}

/// <summary>
/// A family that could not be created because one of its products was taken.
/// </summary>
public class FamilyApplyConflictDto
{
    /// <summary>Name of the family that was not created.</summary>
    public required string FamilyName { get; set; }

    /// <summary>Products that already belong elsewhere, and where.</summary>
    public List<ProductFamilyConflictDto> Conflicts { get; set; } = [];
}

/// <summary>
/// Outcome of applying a batch of approved families.
/// </summary>
public class ApplyFamilySuggestionsResponse
{
    /// <summary>Families created.</summary>
    public int FamiliesCreated { get; set; }

    /// <summary>Members created across those families.</summary>
    public int MembersCreated { get; set; }

    /// <summary>
    /// Families skipped because a product of theirs already belonged to another family.
    /// </summary>
    /// <remarks>
    /// Reported per family rather than failing the batch: one contested product should not cost
    /// the administrator the other hundred and fifty approvals. Each entry names the products and
    /// the family holding them, which is what the caller needs to decide what to do next.
    /// </remarks>
    public List<FamilyApplyConflictDto> Conflicts { get; set; } = [];
}

// ──────────────────────────────────────────────────────────────────────────────────────────────
// C18b — auditing existing families, and recording what a person decided about them
// ──────────────────────────────────────────────────────────────────────────────────────────────

/// <summary>
/// What the administrator asks for when auditing the families that exist.
/// </summary>
public class FamilyAuditQueryRequest
{
    /// <summary>Restrict to one closed-vocabulary piece type; null audits all of them.</summary>
    public string? PieceType { get; set; }

    /// <summary>Overrides the service's configured veto margin for this run.</summary>
    public double? VetoMargin { get; set; }

    /// <summary>Overrides the service's configured orphan margin for this run.</summary>
    public double? OrphanMargin { get; set; }

    /// <summary>Upper bound on returned candidates. Refusals are never truncated.</summary>
    public int MaxOrphans { get; set; } = AiFamilyAuditRequest.MaxOrphansLimit;
}

/// <summary>
/// One judgement a person made about a product and a family.
/// </summary>
public class FamilyVerdictRequest
{
    /// <summary>The product the judgement is about.</summary>
    public Guid ProductId { get; set; }

    /// <summary>The family the judgement is about.</summary>
    public Guid FamilyId { get; set; }

    /// <summary>Whether the product belongs with the family.</summary>
    /// <remarks>
    /// Read as text so an unrecognised value is refused rather than defaulting to the first
    /// member of the enum: an integer body that means "confirmed" by accident is exactly the kind
    /// of mistake this record exists to prevent.
    /// </remarks>
    public string Outcome { get; set; } = string.Empty;

    /// <summary>The margin the audit reported at the moment of the decision, when it came from one.</summary>
    public double? MarginAtReview { get; set; }

    /// <summary>
    /// How long the reviewer spent on this item, in seconds.
    /// </summary>
    /// <remarks>
    /// Sent per judgement rather than derived from a session total: the checklist asks for an
    /// average review time, and a number that lives only in component state disappears when the
    /// tab closes -- which is how the first session's timings were lost.
    /// </remarks>
    public double? ReviewSeconds { get; set; }

    /// <summary>Free-form note about why. Optional.</summary>
    public string? Note { get; set; }
}

/// <summary>
/// A batch of judgements, so a reviewer working through a queue writes once rather than per item.
/// </summary>
public class RecordFamilyVerdictsRequest
{
    /// <summary>Largest batch accepted in one call.</summary>
    public const int MaxVerdicts = 500;

    /// <summary>The judgements.</summary>
    public List<FamilyVerdictRequest> Verdicts { get; set; } = [];
}

/// <summary>
/// Outcome of recording a batch of judgements.
/// </summary>
public class RecordFamilyVerdictsResponse
{
    /// <summary>Judgements recorded for the first time.</summary>
    public int Created { get; set; }

    /// <summary>Judgements that replaced an existing one for the same pair.</summary>
    /// <remarks>
    /// Reported separately because the two mean different things to whoever is reviewing: a
    /// correction is a person changing their mind, and a queue that reports only a total hides
    /// how much of a session was spent revisiting.
    /// </remarks>
    public int Updated { get; set; }
}

/// <summary>
/// A recorded judgement, and the membership change the catalog would need to honour it.
/// </summary>
/// <remarks>
/// Recording a verdict says what a person concluded; it does not move a membership. This DTO is
/// what lets a screen show the gap between the two, which is otherwise invisible: the audit omits
/// judged pairs on purpose — that is what makes a dismissal stick — so a decision nobody acted on
/// disappears from every list and looks like work already done.
/// </remarks>
public class FamilyVerdictDto
{
    /// <summary>Identifier of the product judged.</summary>
    public Guid ProductId { get; set; }

    /// <summary>Product SKU.</summary>
    public required string Sku { get; set; }

    /// <summary>Product name.</summary>
    public required string ProductName { get; set; }

    /// <summary>Identifier of the family judged against.</summary>
    public Guid FamilyId { get; set; }

    /// <summary>That family's name.</summary>
    public required string FamilyName { get; set; }

    /// <summary>What the reviewer decided: <c>Confirmed</c> or <c>Rejected</c>.</summary>
    public required string Outcome { get; set; }

    /// <summary>Whether the product belongs to that family right now.</summary>
    public bool IsCurrentMember { get; set; }

    /// <summary>
    /// What the catalog would have to change: <c>add</c>, <c>remove</c>, or <c>none</c>.
    /// </summary>
    /// <remarks>
    /// Computed here rather than left to the client, because only this side knows the membership.
    /// A rejected current member is a removal waiting to happen and a confirmed non-member is an
    /// addition; the other two combinations are judgements the catalog already agrees with.
    /// </remarks>
    public required string PendingAction { get; set; }

    /// <summary>The margin the audit reported when the decision was made.</summary>
    public double? MarginAtReview { get; set; }

    /// <summary>When it was decided.</summary>
    public DateTime ReviewedAt { get; set; }
}

/// <summary>
/// What the human review of the assisted grouping produced, as figures the README can cite.
/// </summary>
/// <remarks>
/// <para>
/// The delivery checklist asks for a correction rate and an average review time. Both are computed
/// here from the stored judgements rather than tallied in a screen, because a figure that lives in
/// component state is gone when the tab closes — which is precisely how the first session's
/// timings were lost.
/// </para>
/// <para>
/// The two populations are reported apart. A member the vectors questioned and an unassigned
/// product nominated as a candidate are different questions with very different base rates, and
/// one combined percentage would hide both.
/// </para>
/// </remarks>
public class FamilyReviewMetricsDto
{
    /// <summary>Judgements recorded, across both populations.</summary>
    public int TotalJudged { get; set; }

    /// <summary>Members of existing families that were judged.</summary>
    public int MembersJudged { get; set; }

    /// <summary>Of those, how many the reviewer confirmed.</summary>
    public int MembersConfirmed { get; set; }

    /// <summary>Unassigned products that were judged as candidates.</summary>
    public int CandidatesJudged { get; set; }

    /// <summary>Of those, how many the reviewer accepted.</summary>
    public int CandidatesConfirmed { get; set; }

    /// <summary>
    /// Share of questioned memberships the reviewer upheld, as a percentage.
    /// </summary>
    /// <remarks>
    /// The grouper's correction rate read from the side that matters: a high figure means the
    /// vectors flagged members that were fine, so the queue cost attention and bought little.
    /// </remarks>
    public double? MemberConfirmationRate { get; set; }

    /// <summary>Share of nominated candidates the reviewer accepted, as a percentage.</summary>
    public double? CandidateAcceptanceRate { get; set; }

    /// <summary>Judgements that carry a measured review time.</summary>
    public int TimedJudgements { get; set; }

    /// <summary>
    /// Average seconds per judgement, over the timed ones only.
    /// </summary>
    /// <remarks>
    /// Null when nothing was timed, never zero. Zero would read as "instantaneous review", which
    /// is a claim; null reads as "not measured", which is the truth.
    /// </remarks>
    public double? AverageReviewSeconds { get; set; }

    /// <summary>Judgements the catalog has not acted on yet.</summary>
    public int PendingActions { get; set; }
}
