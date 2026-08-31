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
