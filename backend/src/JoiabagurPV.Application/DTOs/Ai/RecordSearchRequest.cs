using JoiabagurPV.Domain.Enums;

namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// Everything the server knows about a search it has just served.
/// </summary>
/// <remarks>
/// Deliberately built from the types the gateway contract already froze —
/// <see cref="AiSearchFilters"/> and <see cref="AiSearchResult"/> — rather than from a shape
/// invented here. The caller has those objects in hand at the moment it calls, so projecting
/// them costs a few lines; a parallel shape would have to be kept in step with the contract
/// forever, and would drift within a week.
/// </remarks>
public sealed record RecordSearchRequest
{
    /// <summary>Already validated caller identity and point of sale.</summary>
    public required AiCallScope Scope { get; init; }

    /// <summary>The natural-language query the operator typed.</summary>
    public required string Query { get; init; }

    /// <summary>The filters actually sent to retrieval, not the UI state.</summary>
    public required AiSearchFilters Filters { get; init; }

    /// <summary>
    /// The results as displayed to the operator, in display order — not the raw candidate set
    /// produced by over-retrieval, whose positions the operator never saw.
    /// </summary>
    public required IReadOnlyList<AiSearchResult> DisplayedResults { get; init; }

    /// <summary>Whether these results came from the AI service or the degraded lexical path.</summary>
    public required SearchOrigin Origin { get; init; }

    /// <summary>
    /// Identifier of the search episode, supplied by the client so that the reformulations of
    /// one session group together. The server generates one when it is absent, so the column is
    /// never empty.
    /// </summary>
    public Guid? SearchSessionId { get; init; }

    /// <summary>Correlation identifier of the hop into the AI service, when there was one.</summary>
    public string? TraceId { get; init; }

    /// <summary>Milliseconds spent obtaining the candidates, whatever their source.</summary>
    public int? RetrievalMs { get; init; }

    /// <summary>Milliseconds from receiving the request to having the final list ready.</summary>
    public int? TotalMs { get; init; }
}
