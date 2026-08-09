namespace JoiabagurPV.Application.Exceptions;

/// <summary>
/// The route exists and is contracted, but its real logic is delivered by a later change.
/// </summary>
/// <remarks>
/// jbg-ai answers 501 rather than 503 for this case precisely so a resilient client does not
/// insist: retrying a route that has no implementation spends the request budget with no
/// possibility of success. Distinct from <see cref="AiUnavailableException"/> because the
/// caller's reaction differs — there is nothing to wait for.
/// </remarks>
public class AiNotImplementedException : AiGatewayException
{
    public AiNotImplementedException(string message) : base(message)
    {
    }
}
