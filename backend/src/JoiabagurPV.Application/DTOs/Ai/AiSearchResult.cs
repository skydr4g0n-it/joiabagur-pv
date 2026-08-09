namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// One candidate returned by jbg-ai. Carries identifiers, a score and the reasons
/// behind the match — never a price or a stock figure, which .NET owns.
/// </summary>
public class AiSearchResult
{
    /// <summary>Identifier of the candidate product in the business database.</summary>
    public required string ProductId { get; set; }

    /// <summary>Product SKU as indexed.</summary>
    public required string Sku { get; set; }

    /// <summary>Relevance score in the range 0 to 1.</summary>
    public double Score { get; set; }

    /// <summary>Signals that matched, for explaining the result to the operator.</summary>
    public List<string> MatchReasons { get; set; } = [];

    /// <summary>Materials of the piece, as a list.</summary>
    public List<string> Materials { get; set; } = [];

    /// <summary>
    /// Family the product belongs to. The contract guarantees an explicit null when the
    /// family is unknown, so this must stay nullable rather than default to a placeholder.
    /// </summary>
    public string? FamilyId { get; set; }

    /// <summary>
    /// Variant label within the family. Null when unknown, for the same reason as
    /// <see cref="FamilyId"/>.
    /// </summary>
    public string? VariantLabel { get; set; }

    /// <summary>Optional retrieval diagnostics.</summary>
    public AiDebugInfo? Debug { get; set; }
}
