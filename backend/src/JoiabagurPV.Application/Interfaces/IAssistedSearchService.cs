using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>
/// Serves assisted catalog search: retrieval, authoritative hydration, degradation and
/// telemetry.
/// </summary>
public interface IAssistedSearchService
{
    /// <summary>
    /// Runs one assisted search on behalf of a user.
    /// </summary>
    /// <param name="request">Query, point of sale, page size and quick filters.</param>
    /// <param name="userId">Who is searching.</param>
    /// <param name="role">Their role, carried into the service token.</param>
    /// <param name="isAdmin">
    /// Whether the caller may search on a point of sale they hold no assignment for. Passed in
    /// rather than derived here, following the pattern the sales module already uses.
    /// </param>
    /// <remarks>
    /// This method does not throw on an AI failure. Every failure mode of the gateway — an open
    /// circuit, an exhausted budget, a transport error, a route with no implementation, rejected
    /// credentials — degrades to the lexical searcher and is reported through
    /// <see cref="AssistedSearchResponse.AiAvailable"/>. The system never falls over because of
    /// the AI.
    /// </remarks>
    Task<AssistedSearchResult> SearchAsync(
        AssistedSearchRequest request,
        Guid userId,
        string role,
        bool isAdmin,
        CancellationToken cancellationToken = default);
}

/// <summary>
/// Short-lived store of the candidates the AI service returned, so a repeated query does not pay
/// for a second embedding.
/// </summary>
public interface IAssistedSearchCandidateCache
{
    /// <summary>
    /// Builds the cache key. Always includes the point of sale, even while retrieval ignores it.
    /// </summary>
    string BuildKey(Guid pointOfSaleId, string query, AiSearchFilters filters, int window);

    /// <summary>Reads a cached candidate set.</summary>
    bool TryGet(string key, out AiSearchResponse? candidates);

    /// <summary>Stores a candidate set for the configured lifetime.</summary>
    void Set(string key, AiSearchResponse candidates);
}
