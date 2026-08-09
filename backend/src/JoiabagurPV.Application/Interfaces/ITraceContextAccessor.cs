namespace JoiabagurPV.Application.Interfaces;

/// <summary>
/// Supplies the correlation identifier of the request currently being served, so an
/// outbound call can be attributed to the inbound request that caused it.
/// </summary>
/// <remarks>
/// Implemented in the API layer because the value comes from the ambient request context,
/// following the same split as <see cref="ICurrentUserService"/>.
/// </remarks>
public interface ITraceContextAccessor
{
    /// <summary>
    /// Correlation identifier for the current request. Never null or blank: when no
    /// ambient context exists, the implementation supplies a fresh identifier rather
    /// than an empty string, because jbg-ai requires the claim to be present.
    /// </summary>
    string CurrentTraceId { get; }
}
