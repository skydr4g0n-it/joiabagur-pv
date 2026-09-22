namespace JoiabagurPV.Application.Configuration;

/// <summary>
/// Configuration for the sale card routes (C34): sale assistance and substitutes. Bound from the
/// "AiSalesAssist" section, read through <c>IOptionsMonitor</c> and validated at start-up.
/// </summary>
/// <remarks>
/// Its own section rather than more keys under <see cref="AiSearchOptions"/>: the card is a
/// different feature, switched on per point of sale on its own schedule, and its generative route
/// has a cost profile search does not. Nothing here is a secret.
/// </remarks>
public class AiSalesAssistOptions
{
    /// <summary>Configuration section name.</summary>
    public const string SectionName = "AiSalesAssist";

    /// <summary>
    /// Whether points of sale absent from <see cref="EnabledPointOfSaleIds"/> call the AI service.
    /// Defaults to false, like assisted search: enabling a shop is an explicit act.
    /// </summary>
    /// <remarks>
    /// The switch governs <strong>both</strong> routes, because the card is one. Off, the sale
    /// assistance answers with its degraded card and substitutes with the AI-unavailable outcome,
    /// without calling the AI service — and the log records that the switch did it.
    /// </remarks>
    public bool EnabledByDefault { get; set; }

    /// <summary>Points of sale where the card calls the AI service, by identifier.</summary>
    public List<Guid> EnabledPointOfSaleIds { get; set; } = [];

    /// <summary>
    /// Highest quantity of the anchored product that still raises <c>stock_critical</c>. Zero
    /// never does: it is a state of the member, not a warning.
    /// </summary>
    /// <remarks>
    /// Two, the <c>1-2</c> bucket C32a names <c>ultimas_unidades</c> and the default of the
    /// dashboard's low-stock panel. It fires on 4.2 % of stocked rows of the shops, against 14.4 %
    /// for "five or fewer", over a median of 12 units. The sales rule <c>max(10 %, 5)</c> measures
    /// something else: what remains <em>after</em> selling.
    /// </remarks>
    public int StockCriticalThreshold { get; set; } = 2;

    /// <summary>
    /// <c>top_k</c> sent to the substitutes route: the over-retrieval dial, not a page size.
    /// </summary>
    /// <remarks>
    /// The service returns <c>min(3 × top_k, 60)</c> candidates, so 20 obtains the largest window
    /// the frozen contract can return, in one call. Measured at Fornells: with a window of 15,
    /// 71.1 % of pieces do not fill a page of five substitutes in stock; with 60, 7.1 %.
    /// </remarks>
    public int SubstitutesCandidateWindow { get; set; } = 20;

    /// <summary>Substitutes returned when the caller does not ask for a page size.</summary>
    public int SubstitutesDefaultPageSize { get; set; } = 5;

    /// <summary>Largest substitutes page a caller may ask for.</summary>
    public int SubstitutesMaxPageSize { get; set; } = 20;

    /// <summary>
    /// Sale assistance requests one user may issue inside <see cref="RateLimitWindowSeconds"/>.
    /// </summary>
    /// <remarks>
    /// The generative route's own limit, separate from search's: each request can cost two paid
    /// provider calls, and the organisation's tokens-per-minute quota is what several operators
    /// hit first. Substitutes call no model and use the search policy.
    /// </remarks>
    public int RateLimitPermitLimit { get; set; } = 10;

    /// <summary>Length of the rate-limiting window, in seconds.</summary>
    public int RateLimitWindowSeconds { get; set; } = 60;

    /// <summary>Whether the card calls the AI service for a given point of sale.</summary>
    public bool IsEnabledFor(Guid pointOfSaleId) =>
        EnabledByDefault || EnabledPointOfSaleIds.Contains(pointOfSaleId);
}
