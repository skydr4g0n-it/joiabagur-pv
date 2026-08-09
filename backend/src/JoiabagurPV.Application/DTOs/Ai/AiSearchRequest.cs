namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// Catalog retrieval request sent to jbg-ai.
/// </summary>
/// <remarks>
/// The frozen contract accepts an optional <c>pos_id</c> in the body and ignores it,
/// because scope comes from the service token. This model deliberately omits it:
/// serializing a value the service discards would suggest the body carries authority.
/// </remarks>
public class AiSearchRequest
{
    /// <summary>Natural-language query typed by the operator.</summary>
    public required string Query { get; set; }

    /// <summary>
    /// Page size the caller wants <em>after</em> hydrating and filtering on the .NET side.
    /// The service over-fetches and reports what it produced in
    /// <see cref="AiSearchResponse.CandidatesReturned"/>.
    /// </summary>
    public int TopK { get; set; } = 10;

    /// <summary>Catalog-side filters.</summary>
    public AiSearchFilters Filters { get; set; } = new();

    /// <summary>Retrieval strategy.</summary>
    public AiRetrievalMode Mode { get; set; } = AiRetrievalMode.Hybrid;
}
