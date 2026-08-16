using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>
/// Produces and persists AI profiles for catalog products.
/// </summary>
/// <remarks>
/// One operation, on purpose. Reading profiles, approving them and measuring the review are the
/// review capability's job, and the indexing feed is the feed's: a capability that grows a read
/// route "just for a counter" is how a write-only surface ends up with three.
/// </remarks>
public interface IProductAiProfileService
{
    /// <summary>
    /// Enriches a batch of products and persists the resulting profiles.
    /// </summary>
    /// <param name="request">Products, review mode and whether to ignore the input hash.</param>
    /// <param name="userId">Administrator on whose behalf the call is made.</param>
    /// <param name="role">Role of that user, carried into the service token.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Counters and the per-product outcome.</returns>
    /// <exception cref="Exceptions.AiUnavailableException">The AI service could not answer.</exception>
    /// <exception cref="Exceptions.AiNotImplementedException">The enrichment route has no implementation yet.</exception>
    Task<EnrichBatchResponse> EnrichBatchAsync(
        EnrichBatchRequest request,
        Guid userId,
        string role,
        CancellationToken cancellationToken = default);
}
