namespace JoiabagurPV.Application.Exceptions;

/// <summary>
/// Base for every failure of the jbg-ai integration. Callers catch the derived types to
/// decide whether to degrade, to surface a configuration fault or to stop.
/// </summary>
public abstract class AiGatewayException : Exception
{
    protected AiGatewayException(string message) : base(message)
    {
    }

    protected AiGatewayException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}
