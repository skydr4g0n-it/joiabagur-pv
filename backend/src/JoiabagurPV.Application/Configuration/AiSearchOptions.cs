namespace JoiabagurPV.Application.Configuration;

/// <summary>
/// Configuration for the assisted search endpoint. Bound from the "AiSearch" section and
/// validated during application start-up.
/// </summary>
/// <remarks>
/// <para>
/// The per-point-of-sale switch lives here rather than in a column on purpose. A column would
/// open a seventh EF Core migration in a change that has no schema of its own and sits on the
/// critical path; configuration reloaded through <c>IOptionsMonitor</c> covers the operational
/// need — switch a shop on, switch it off — without that cost.
/// </para>
/// <para>
/// Nothing here is a secret: the gateway credentials belong to <see cref="AiGatewayOptions"/>.
/// </para>
/// </remarks>
public class AiSearchOptions
{
    /// <summary>Configuration section name.</summary>
    public const string SectionName = "AiSearch";

    /// <summary>
    /// Points of sale where the assisted path is used, by identifier.
    /// </summary>
    /// <remarks>
    /// Read through <c>IOptionsMonitor</c> so a shop can be switched on or off without a
    /// redeploy. Combined with <see cref="EnabledByDefault"/>: when that is false — the default —
    /// this list is an allow-list; when it is true, the list is ignored and every point of sale
    /// is enabled.
    /// </remarks>
    public List<Guid> EnabledPointOfSaleIds { get; set; } = [];

    /// <summary>
    /// Whether points of sale absent from <see cref="EnabledPointOfSaleIds"/> use the assisted
    /// path. Defaults to false, so enabling a shop is an explicit act.
    /// </summary>
    public bool EnabledByDefault { get; set; }

    /// <summary>
    /// Page size requested from the AI service, which is the over-retrieval dial rather than a
    /// page size in the usual sense.
    /// </summary>
    /// <remarks>
    /// The retriever produces <c>min(window × 3, 60)</c> candidates, so 20 saturates its cap and
    /// obtains the largest candidate set the frozen contract can ever return — in a single call.
    /// Asking for more buys nothing; asking for less leaves the hydrator without margin at the
    /// points of sale that stock a small share of the catalog.
    /// </remarks>
    public int CandidateWindow { get; set; } = 20;

    /// <summary>Page size used when the caller does not ask for one.</summary>
    public int DefaultPageSize { get; set; } = 10;

    /// <summary>Largest page a caller may ask for.</summary>
    public int MaxPageSize { get; set; } = 50;

    /// <summary>How long retrieved candidates stay cached, in seconds.</summary>
    /// <remarks>
    /// Short on purpose. The cache exists to absorb a repeated query — a key held down, a filter
    /// corrected and re-sent — not to serve a stale ranking. Only identifiers and scores are
    /// cached; hydration runs again on every hit.
    /// </remarks>
    public int CandidateCacheTtlSeconds { get; set; } = 60;

    /// <summary>Maximum number of cached candidate sets.</summary>
    public int CandidateCacheSize { get; set; } = 200;

    /// <summary>Requests one user may issue inside <see cref="RateLimitWindowSeconds"/>.</summary>
    public int RateLimitPermitLimit { get; set; } = 30;

    /// <summary>Length of the rate-limiting window, in seconds.</summary>
    public int RateLimitWindowSeconds { get; set; } = 60;

    /// <summary>
    /// Whether a given point of sale uses the assisted path.
    /// </summary>
    public bool IsEnabledFor(Guid pointOfSaleId) =>
        EnabledByDefault || EnabledPointOfSaleIds.Contains(pointOfSaleId);
}
