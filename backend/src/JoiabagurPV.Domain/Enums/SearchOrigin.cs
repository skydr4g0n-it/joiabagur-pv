namespace JoiabagurPV.Domain.Enums;

/// <summary>
/// Where the results shown to the operator actually came from.
/// </summary>
/// <remarks>
/// Values are explicit and stable because this column is read by hand in SQL: the mapping
/// is part of the contract with whoever writes those queries, not an implementation detail
/// that may shift when a member is reordered.
///
/// This is NOT the same concept as the retrieval mode the gateway client requests from
/// <c>jbg-ai</c>. That one describes the strategy used inside the AI service; this one
/// describes whether the AI service answered at all. Conflating them would poison the
/// analysis: a week of open circuit breakers would read as the AI ranking worse, when the
/// AI never ran.
/// </remarks>
public enum SearchOrigin
{
    /// <summary>
    /// Results produced by the AI service.
    /// </summary>
    Assisted = 1,

    /// <summary>
    /// Results produced by the existing lexical searcher, because the AI service was
    /// unavailable and the circuit breaker degraded the request.
    /// </summary>
    LexicalFallback = 2
}
