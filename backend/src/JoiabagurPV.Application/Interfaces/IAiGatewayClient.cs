using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>
/// Outbound integration with the jbg-ai service.
/// </summary>
/// <remarks>
/// The surface is deliberately one operation. Every other contracted endpoint is added by the
/// change that first calls it: adding a method here is a small diff, whereas the wire contract
/// it consumes is frozen and expensive to renegotiate.
/// </remarks>
public interface IAiGatewayClient
{
    /// <summary>
    /// Runs a catalog retrieval against jbg-ai.
    /// </summary>
    /// <param name="request">Query, page size and catalog-side filters.</param>
    /// <param name="scope">Caller identity and point-of-sale scope, already authorised.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>
    /// Every candidate the service produced — more than the requested page size by design.
    /// Truncating belongs to the caller, which hydrates and discards first.
    /// </returns>
    /// <exception cref="Exceptions.AiUnavailableException">
    /// Timeout, transport failure, open circuit, or a server error other than 501.
    /// </exception>
    /// <exception cref="Exceptions.AiNotImplementedException">
    /// The route is contracted but has no implementation yet.
    /// </exception>
    /// <exception cref="Exceptions.AiGatewayConfigurationException">
    /// The service rejected the credentials.
    /// </exception>
    Task<AiSearchResponse> SearchAsync(
        AiSearchRequest request,
        AiCallScope scope,
        CancellationToken cancellationToken = default);
}
