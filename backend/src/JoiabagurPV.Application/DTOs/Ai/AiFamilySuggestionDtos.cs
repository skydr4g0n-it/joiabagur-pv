namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// Narrowing for a family suggestion run. An empty body proposes over the whole active index.
/// </summary>
public class AiFamilySuggestRequest
{
    /// <summary>
    /// Largest number of proposals the frozen contract returns in one call.
    /// </summary>
    /// <remarks>
    /// Mirrored from <c>MAX_PROPOSALS</c> on the Python side rather than picked here, for the
    /// same reason as the enrichment batch size: rejecting an out-of-range value before the
    /// round trip turns a validation error into an immediate, explainable answer.
    /// </remarks>
    public const int MaxProposalsLimit = 500;

    /// <summary>Restrict to one closed-vocabulary piece type; null proposes over all of them.</summary>
    public string? PieceType { get; set; }

    /// <summary>Upper bound on returned proposals. Refusals are never truncated.</summary>
    public int MaxProposals { get; set; } = MaxProposalsLimit;
}

/// <summary>
/// One product inside a proposal, with the label that tells it from its siblings.
/// </summary>
public class AiProposedFamilyMember
{
    /// <summary>Identifier of the product in the business database.</summary>
    public required string ProductId { get; set; }

    /// <summary>Product SKU.</summary>
    public required string Sku { get; set; }

    /// <summary>Product name as the catalog holds it.</summary>
    public required string Name { get; set; }

    /// <summary>
    /// Size, colour or finish that distinguishes this member, exactly as the catalog wrote it.
    /// </summary>
    /// <remarks>
    /// Nullable on purpose, and the distinction carries meaning: null is the <em>base</em> piece
    /// of the family — a legitimate variant value, not a missing one. The contract guarantees an
    /// explicit null rather than an absent field, so mapping it to an empty string would erase
    /// the difference between "this is the plain one" and "nobody has decided yet".
    /// </remarks>
    public string? VariantLabel { get; set; }

    /// <summary>Order within the family, gap-free from zero, by canonical size rank.</summary>
    public int Position { get; set; }

    /// <summary>A product of another proposed family sits closer than this member's worst sibling.</summary>
    public bool FlaggedForReview { get; set; }

    /// <summary>Why the member was flagged, when it was.</summary>
    public string? ReviewReason { get; set; }

    /// <summary>How far the nearest stranger beat the worst sibling. Null when not flagged.</summary>
    public double? Margin { get; set; }
}

/// <summary>
/// A candidate family: one piece type, one normalized root, two or more members.
/// </summary>
public class AiFamilyProposal
{
    /// <summary>Normalized grouping root.</summary>
    public required string Root { get; set; }

    /// <summary>Name proposed for the family, derived from the root.</summary>
    public required string SuggestedName { get; set; }

    /// <summary>Closed-vocabulary piece type shared by every member.</summary>
    public required string PieceType { get; set; }

    /// <summary>Members in their proposed order.</summary>
    public List<AiProposedFamilyMember> Members { get; set; } = [];
}

/// <summary>
/// A group a guard refused to propose, reported so a person can look at it.
/// </summary>
/// <remarks>
/// Not an error and not noise. On the real catalog this list is what surfaced the workshop
/// services filed among the jewellery — <c>Encargos</c>, <c>Arreglos</c>, <c>Presión</c> — which
/// the enrichment had classified as necklaces and rings because its closed vocabulary has no way
/// to say "this is not a piece".
/// </remarks>
public class AiRejectedFamilyGroup
{
    /// <summary>Root the group would have had.</summary>
    public required string Root { get; set; }

    /// <summary>Piece type of the group, when it had one.</summary>
    public string? PieceType { get; set; }

    /// <summary>
    /// Why it was refused: <c>root_too_short</c>, <c>root_is_bare_piece_type</c>,
    /// <c>empty_root</c> or <c>duplicate_variant_labels</c>.
    /// </summary>
    public required string Reason { get; set; }

    /// <summary>Names of the products that would have formed the group.</summary>
    public List<string> ProductNames { get; set; } = [];
}

/// <summary>
/// A product the piece-type gate removed before grouping.
/// </summary>
public class AiExcludedProduct
{
    /// <summary>Identifier of the product in the business database.</summary>
    public required string ProductId { get; set; }

    /// <summary>Product SKU.</summary>
    public required string Sku { get; set; }

    /// <summary>Product name as the catalog holds it.</summary>
    public required string Name { get; set; }

    /// <summary>Why it was excluded. Today only <c>no_piece_type</c>.</summary>
    public required string Reason { get; set; }
}

/// <summary>
/// Everything one suggestion run produced, including what it declined to propose.
/// </summary>
public class AiFamilySuggestResponse
{
    /// <summary>Candidate families, in the order the service produced them.</summary>
    public List<AiFamilyProposal> Proposals { get; set; } = [];

    /// <summary>Groups a guard refused, with the reason.</summary>
    public List<AiRejectedFamilyGroup> RejectedGroups { get; set; } = [];

    /// <summary>Products the piece-type gate removed, with the reason.</summary>
    public List<AiExcludedProduct> ExcludedProducts { get; set; } = [];

    /// <summary>
    /// Products skipped for already belonging to a family.
    /// </summary>
    /// <remarks>
    /// A count and not a list: after the first approved batch they are hundreds, and their
    /// exclusion is the convergence rule working rather than something to read.
    /// </remarks>
    public int AlreadyInFamilyCount { get; set; }

    /// <summary>Correlation id echoed by the service.</summary>
    public string? TraceId { get; set; }
}

// ──────────────────────────────────────────────────────────────────────────────────────────────
// C18b — the audit contract: the same comparison, read from both sides of membership
// ──────────────────────────────────────────────────────────────────────────────────────────────

/// <summary>
/// A <c>(product, family)</c> pair a person has already ruled on.
/// </summary>
/// <remarks>
/// Travels in the request because the AI service holds no verdict of its own and must not: the
/// catalog's truth lives here, and a store of judgements beside the index would be state nothing
/// invalidates. Assembling this set from <c>FamilyReviewVerdicts</c> is this side's work.
/// </remarks>
public class AiJudgedPair
{
    /// <summary>Identifier of the product.</summary>
    public required string ProductId { get; set; }

    /// <summary>Identifier of the family.</summary>
    public required string FamilyId { get; set; }
}

/// <summary>
/// Narrowing, thresholds and prior judgements for one audit run.
/// </summary>
public class AiFamilyAuditRequest
{
    /// <summary>Largest number of orphan candidates the frozen contract returns in one call.</summary>
    /// <remarks>
    /// Mirrored from <c>MAX_ORPHAN_CANDIDATES</c> on the Python side rather than picked here, for
    /// the same reason as the suggestion cap: rejecting an out-of-range value before the round trip
    /// turns a validation error into an immediate, explainable answer.
    /// </remarks>
    public const int MaxOrphansLimit = 500;

    /// <summary>Restrict to one closed-vocabulary piece type; null audits all of them.</summary>
    public string? PieceType { get; set; }

    /// <summary>Overrides the service's configured veto margin for this run. Null uses it.</summary>
    public double? VetoMargin { get; set; }

    /// <summary>Overrides the service's configured orphan margin for this run. Null uses it.</summary>
    public double? OrphanMargin { get; set; }

    /// <summary>Upper bound on returned candidates. Refusals are never truncated.</summary>
    public int MaxOrphans { get; set; } = MaxOrphansLimit;

    /// <summary>Pairs already ruled on, omitted from both lists of the response.</summary>
    public List<AiJudgedPair> JudgedPairs { get; set; } = [];
}

/// <summary>
/// A member of an existing family that the vectors do not support.
/// </summary>
/// <remarks>
/// This queue exists only because it is recomputed. Suggestion converges by excluding products
/// that already belong somewhere, and C18a persisted no proposals, so the members it flagged at
/// approval time are unreachable by every later suggestion: the flags lived in one response and
/// the products are now inside families.
/// </remarks>
public class AiFlaggedFamilyMember
{
    /// <summary>Identifier of the product in the business database.</summary>
    public required string ProductId { get; set; }

    /// <summary>Product SKU.</summary>
    public required string Sku { get; set; }

    /// <summary>Product name as the catalog holds it.</summary>
    public required string Name { get; set; }

    /// <summary>Label that tells this member from its siblings. Null is the base piece.</summary>
    public string? VariantLabel { get; set; }

    /// <summary>Identifier of the family the product currently belongs to.</summary>
    public required string FamilyId { get; set; }

    /// <summary>Name of that family.</summary>
    public string? FamilyName { get; set; }

    /// <summary>How far the nearest stranger beat this member's own worst sibling.</summary>
    public double Margin { get; set; }

    /// <summary>Family of the product that beat the worst sibling.</summary>
    public string? StrangerFamilyId { get; set; }

    /// <summary>Why the member was flagged. Today only <c>closer_to_another_family</c>.</summary>
    public string Reason { get; set; } = "closer_to_another_family";
}

/// <summary>
/// A product belonging to no family that looks like it belongs to one.
/// </summary>
public class AiOrphanCandidate
{
    /// <summary>Identifier of the product in the business database.</summary>
    public required string ProductId { get; set; }

    /// <summary>Product SKU.</summary>
    public required string Sku { get; set; }

    /// <summary>Product name as the catalog holds it.</summary>
    public required string Name { get; set; }

    /// <summary>Closed-vocabulary piece type shared with the target family.</summary>
    public required string PieceType { get; set; }

    /// <summary>
    /// <c>real</c> or <c>synthetic</c>.
    /// </summary>
    /// <remarks>
    /// Carried because the two populations behave very differently here and every figure derived
    /// from this list has to be able to separate them, the same discipline C24 applies.
    /// </remarks>
    public required string DataOrigin { get; set; }

    /// <summary>Identifier of the family it is nominated for.</summary>
    public required string FamilyId { get; set; }

    /// <summary>Name of that family.</summary>
    public string? FamilyName { get; set; }

    /// <summary>Similarity to that family's members.</summary>
    public double Similarity { get; set; }

    /// <summary>Lowest similarity observed inside that family.</summary>
    public double WorstSibling { get; set; }

    /// <summary>
    /// <c>Similarity - WorstSibling</c>. This is the nomination criterion.
    /// </summary>
    public double Margin { get; set; }

    /// <summary>
    /// Of the five nearest neighbours of the same piece type, how many belong to this family.
    /// </summary>
    /// <remarks>
    /// <strong>A ranking signal only, never the criterion.</strong> Measured over this corpus,
    /// purity nominates 55 synthetic products against 19 real ones, because the deliberate
    /// <c>vN</c> families it cannot separate from a missing member are synthetic by construction.
    /// Filtering on it here would silently adopt the mistake the margin exists to avoid.
    /// </remarks>
    public int Purity { get; set; }
}

/// <summary>
/// Everything one audit run produced: both sides of the membership line, and both refusals.
/// </summary>
public class AiFamilyAuditResponse
{
    /// <summary>Members of existing families the vectors do not support.</summary>
    public List<AiFlaggedFamilyMember> FlaggedMembers { get; set; } = [];

    /// <summary>Unassigned products nominated as candidates, ordered by margin.</summary>
    public List<AiOrphanCandidate> OrphanCandidates { get; set; } = [];

    /// <summary>Groups a guard refused, recomputed over the current catalog state.</summary>
    public List<AiRejectedFamilyGroup> RejectedGroups { get; set; } = [];

    /// <summary>Products the piece-type gate removed, recomputed likewise.</summary>
    public List<AiExcludedProduct> ExcludedProducts { get; set; } = [];

    /// <summary>Families the audit examined, so an empty flag list is readable.</summary>
    public int FamiliesReviewedCount { get; set; }

    /// <summary>Memberships the audit examined, for the same reason.</summary>
    public int MembersExaminedCount { get; set; }

    /// <summary>Correlation id echoed by the service.</summary>
    public string? TraceId { get; set; }
}
