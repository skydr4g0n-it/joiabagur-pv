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
