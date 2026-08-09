using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>
/// Issues the internal service token the .NET API presents to jbg-ai.
/// </summary>
public interface IAiServiceTokenFactory
{
    /// <summary>
    /// Signs a short-lived HS256 token carrying the four claims jbg-ai requires.
    /// </summary>
    /// <param name="scope">Caller identity and point-of-sale scope.</param>
    /// <param name="traceId">Correlation identifier for this call.</param>
    /// <returns>The encoded token, to be presented as a bearer credential.</returns>
    string Create(AiCallScope scope, string traceId);
}
