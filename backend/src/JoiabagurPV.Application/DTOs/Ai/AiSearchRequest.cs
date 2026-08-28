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
    /// <summary>
    /// Largest page size the frozen contract accepts.
    /// </summary>
    /// <remarks>
    /// Declared here because this is the model of the frozen contract, and a caller sizing its
    /// over-retrieval window needs the ceiling without reaching for the schema file. A constant
    /// is invisible to the contract snapshot test, which inspects instance properties.
    /// </remarks>
    public const int MaxTopK = 50;

    /// <summary>Longest query the frozen contract accepts.</summary>
    public const int MaxQueryLength = 500;

    /// <summary>
    /// Candidates the retriever produces for a requested page size: <c>min(topK × 3, 60)</c>.
    /// </summary>
    /// <remarks>
    /// Mirrors the service's own over-retrieval helper. The caller needs it to know when asking
    /// for a larger window would return anything new — and, with the cap at 60, when it would
    /// not.
    /// </remarks>
    public static int OverRetrievalCount(int topK) => Math.Min(topK * 3, OverRetrievalCap);

    /// <summary>Hard ceiling on candidates, whatever the requested page size.</summary>
    public const int OverRetrievalCap = 60;

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
