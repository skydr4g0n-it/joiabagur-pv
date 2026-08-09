namespace JoiabagurPV.Application.Exceptions;

/// <summary>
/// The AI service rejected the credentials. On this side that means misconfiguration.
/// </summary>
/// <remarks>
/// jbg-ai is required to reject an invalid token with a 401 that discloses neither the secret
/// nor which validation step failed, so the response carries no diagnosis. The likely causes
/// are a shared secret that does not match, a token carrying claims the validator does not
/// expect, or clock drift between the two containers. Retrying changes none of them, which is
/// why this never triggers a retry and is logged at error level.
/// </remarks>
public class AiGatewayConfigurationException : AiGatewayException
{
    public AiGatewayConfigurationException(string message) : base(message)
    {
    }
}
