namespace JoiabagurPV.Application.Exceptions;

/// <summary>
/// The AI service could not answer: timeout, transport failure, a server error other than
/// 501, or an open circuit.
/// </summary>
/// <remarks>
/// This is the signal a caller degrades on. The system must never fall over because of the
/// AI service, so the caller is expected to answer with its own fallback rather than
/// propagate this to the operator.
/// </remarks>
public class AiUnavailableException : AiGatewayException
{
    public AiUnavailableException(string message) : base(message)
    {
    }

    public AiUnavailableException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}
