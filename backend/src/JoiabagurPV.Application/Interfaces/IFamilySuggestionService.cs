using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>
/// Assisted family grouping: jbg-ai proposes, this side persists.
/// </summary>
public interface IFamilySuggestionService
{
    /// <summary>
    /// Asks jbg-ai for family proposals. Writes nothing.
    /// </summary>
    /// <param name="request">Optional narrowing by piece type.</param>
    /// <param name="userId">Administrator making the request.</param>
    /// <param name="role">Their role, for the internal service token.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>
    /// Proposals plus the two kinds of omission — groups a guard refused and products the
    /// piece-type gate excluded — all three as the service produced them.
    /// </returns>
    /// <exception cref="Exceptions.AiUnavailableException">The service is unreachable.</exception>
    /// <exception cref="Exceptions.AiNotImplementedException">The route has no implementation.</exception>
    Task<AiFamilySuggestResponse> SuggestAsync(
        FamilySuggestionsRequest request,
        Guid userId,
        string role,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Creates the families an administrator accepted, recording the approval.
    /// </summary>
    /// <param name="request">The accepted subset, returned by the caller.</param>
    /// <param name="approvedByUserId">Administrator approving the batch.</param>
    /// <returns>Counts of what was created, and the families a conflict skipped.</returns>
    /// <remarks>
    /// Persists through <see cref="IProductFamilyService"/> and never by direct SQL, so that
    /// <c>Product.UpdatedAt</c> is stamped on entering products and the incremental catalog feed
    /// can see them. A conflict skips its family whole and is reported; it never fails the batch.
    /// </remarks>
    Task<ApplyFamilySuggestionsResponse> ApplyAsync(
        ApplyFamilySuggestionsRequest request,
        Guid approvedByUserId);
}
