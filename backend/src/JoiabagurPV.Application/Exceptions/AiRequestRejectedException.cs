namespace JoiabagurPV.Application.Exceptions;

/// <summary>
/// The AI service answered, and refused to process what the request named.
/// </summary>
/// <remarks>
/// <para>
/// Raised only by the sale assistance and substitutes operations, for HTTP 422. jbg-ai answers
/// it there for a product it cannot process — absent from its index, inactive, or without an
/// embedding — which is a state of the catalog that the next synchronisation fixes, not an
/// outage. Reading it as <see cref="AiUnavailableException"/> would present a product created
/// after the last synchronisation as a failure of the service.
/// </para>
/// <para>
/// The other operations of the client keep translating a 422 as unavailability. The status
/// translation is shared by the whole client and narrowing it for them is not this exception's
/// business: their routes do not produce a 422 about a product.
/// </para>
/// <para>
/// Never retried and never counted by a circuit breaker: the service is answering correctly.
/// </para>
/// </remarks>
public class AiRequestRejectedException : AiGatewayException
{
    public AiRequestRejectedException(int statusCode, string message) : base(message)
    {
        StatusCode = statusCode;
    }

    /// <summary>The HTTP status the service answered with.</summary>
    public int StatusCode { get; }
}
