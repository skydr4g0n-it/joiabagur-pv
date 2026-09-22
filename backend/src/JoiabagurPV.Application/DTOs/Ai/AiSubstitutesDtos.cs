namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// Substitutes request sent to jbg-ai (<c>POST /v1/retrieval/substitutes</c>).
/// </summary>
/// <remarks>
/// Omits <c>pos_id</c> for the same reason <see cref="AiSearchRequest"/> does: the scope travels
/// in the token and the service ignores the body value.
/// </remarks>
public class AiSubstitutesRequest
{
    /// <summary>
    /// Largest page size the frozen contract accepts. <see cref="AiSearchRequest.OverRetrievalCount"/>
    /// applies here too: the service returns <c>min(3 × top_k, 60)</c> candidates.
    /// </summary>
    public const int MaxTopK = 50;

    /// <summary>The product a substitute is wanted for.</summary>
    public required string ProductId { get; set; }

    /// <summary>
    /// The over-retrieval dial rather than a page size: the service returns the whole window and
    /// the caller hydrates, filters by stock and truncates.
    /// </summary>
    public int TopK { get; set; } = 10;

    /// <summary>Why a substitute is needed, as log data for the service. Null when unstated.</summary>
    public string? Reason { get; set; }

    /// <summary>Catalog-side filters. Empty by default.</summary>
    public AiSearchFilters Filters { get; set; } = new();
}

/// <summary>
/// Substitutes response from jbg-ai.
/// </summary>
/// <remarks>
/// <see cref="Results"/> holds the whole over-retrieval window, larger than the requested page
/// on purpose. Excluding what the point of sale cannot sell today, and truncating, belong to the
/// hydrating caller.
/// </remarks>
public class AiSubstitutesResponse
{
    /// <summary>Candidates in the order the service ranked them.</summary>
    public List<AiSubstituteResult> Results { get; set; } = [];

    /// <summary>How many candidates the service produced.</summary>
    public int CandidatesReturned { get; set; }

    /// <summary>Whether nothing cleared the service's confidence rule.</summary>
    public bool LowConfidence { get; set; }

    /// <summary>Correlation identifier echoed by the service.</summary>
    public string TraceId { get; set; } = string.Empty;

    /// <summary>Point-of-sale scope the service applied: always the token claim.</summary>
    public string EffectivePosId { get; set; } = string.Empty;
}

/// <summary>
/// One substitute candidate. Identifiers, a score and similarity signals — never a price or a
/// stock figure.
/// </summary>
public class AiSubstituteResult
{
    /// <summary>Identifier of the candidate product in the business database.</summary>
    public required string ProductId { get; set; }

    /// <summary>SKU as indexed.</summary>
    public required string Sku { get; set; }

    /// <summary>Relevance score in the range 0 to 1.</summary>
    public double Score { get; set; }

    /// <summary>Signals that matched.</summary>
    public List<string> MatchReasons { get; set; } = [];

    /// <summary>Materials of the piece, as indexed.</summary>
    public List<string> Materials { get; set; } = [];

    /// <summary>Family of the candidate, or null when unknown.</summary>
    public string? FamilyId { get; set; }

    /// <summary>Variant label, or null when unknown.</summary>
    public string? VariantLabel { get; set; }

    /// <summary>Why the two products are considered interchangeable.</summary>
    public AiSimilaritySignals SimilaritySignals { get; set; } = new();

    /// <summary>Optional diagnostics; the projection age travels in its notes.</summary>
    public AiDebugInfo? Debug { get; set; }
}

/// <summary>
/// Why two products are considered interchangeable. No price signal, by design of the contract.
/// </summary>
public class AiSimilaritySignals
{
    /// <summary>Whether the candidate belongs to the same family.</summary>
    public bool FamilyMatch { get; set; }

    /// <summary>Share of materials in common, 0 to 1.</summary>
    public double MaterialOverlap { get; set; }

    /// <summary>Style similarity, 0 to 1.</summary>
    public double StyleSimilarity { get; set; }

    /// <summary>Visual similarity, 0 to 1, or null when not computed.</summary>
    public double? VisualSimilarity { get; set; }
}
