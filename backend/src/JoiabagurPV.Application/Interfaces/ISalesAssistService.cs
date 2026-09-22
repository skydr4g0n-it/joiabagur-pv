using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>
/// The sale assistance of one product at one point of sale (C34): the card's group, warnings,
/// citations and argument.
/// </summary>
public interface ISalesAssistService
{
    /// <summary>
    /// Serves the sale assistance of a product on behalf of a user.
    /// </summary>
    /// <param name="productId">The anchored product.</param>
    /// <param name="request">Point of sale and optional question, already validated.</param>
    /// <param name="userId">Who is asking.</param>
    /// <param name="role">Their role, carried into the service token.</param>
    /// <param name="isAdmin">Whether the caller may use a point of sale they hold no assignment for.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <remarks>
    /// Authorisation and the check that the point of sale carries the product both happen before
    /// the AI service is called: a request this side is about to refuse never costs a paid call.
    /// This method does not throw on an AI failure — every failure mode degrades to the card read
    /// from the catalog, reported through <see cref="SalesAssistResponse.AiAvailable"/>.
    /// </remarks>
    Task<SalesAssistResult> AssistAsync(
        Guid productId,
        SalesAssistRequest request,
        Guid userId,
        string role,
        bool isAdmin,
        CancellationToken cancellationToken = default);
}

/// <summary>
/// The substitutes of one product that one point of sale can sell today (C34).
/// </summary>
public interface ISubstitutesService
{
    /// <summary>
    /// Serves the substitutes of a product on behalf of a user.
    /// </summary>
    /// <remarks>
    /// Same authorisation and product check as the sale assistance, before any call. Never throws
    /// on an AI failure: the outcome says which of four things happened.
    /// </remarks>
    Task<SubstitutesResult> GetSubstitutesAsync(
        Guid productId,
        SubstitutesRequest request,
        Guid userId,
        string role,
        bool isAdmin,
        CancellationToken cancellationToken = default);
}
