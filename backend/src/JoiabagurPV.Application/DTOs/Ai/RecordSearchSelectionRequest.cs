namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// What the browser reports when the operator picks a result.
/// </summary>
/// <remarks>
/// One field, and that is the point. Everything else about the event — the rank, the timings,
/// the origin, the result list — the server either already stored or derives itself, so asking
/// the client for it would be asking it to repeat, or invent, what it cannot observe. The event
/// identifier travels in the route, and the user comes from the token.
/// </remarks>
public class RecordSearchSelectionRequest
{
    /// <summary>
    /// The product the operator selected from the displayed results.
    /// </summary>
    public Guid ProductId { get; set; }
}
