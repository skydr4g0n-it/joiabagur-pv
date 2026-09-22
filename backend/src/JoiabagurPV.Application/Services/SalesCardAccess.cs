using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Interfaces.Repositories;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// The checks both sale card routes run before calling the AI service: the point of sale, the
/// caller's right to it, and whether it carries the anchored product.
/// </summary>
/// <remarks>
/// <para>
/// The point-of-sale rule is assisted search's (C15), replicated rather than extracted: that
/// check is private to <see cref="AssistedSearchService"/> and returns its own result type, and
/// moving it would touch a route this change promises to leave exactly as it was. An inactive
/// point of sale is refused for every role; an administrator may use any active one, because
/// administrators hold no assignments; an operator needs an active assignment.
/// </para>
/// <para>
/// The product check is one hydration of the anchored product alone. Empty means the product is
/// unknown, inactive, or has no active inventory record at that point of sale — refused as not
/// found for every role, because an inventory assignment is what makes a product belong to a
/// point of sale. A quantity of zero is not a refusal: a product the shop carries and has run
/// out of is still the shop's product. The row found is reused as the anchor.
/// </para>
/// </remarks>
internal static class SalesCardAccess
{
    public static async Task<(SalesCardAccessOutcome Outcome, AssistedSearchRow? Anchor)> ResolveAsync(
        IAssistedSearchRepository repository,
        IUserPointOfSaleService userPointOfSaleService,
        Guid productId,
        Guid pointOfSaleId,
        Guid userId,
        bool isAdmin,
        CancellationToken cancellationToken)
    {
        if (!await repository.IsPointOfSaleActiveAsync(pointOfSaleId, cancellationToken))
        {
            return (SalesCardAccessOutcome.PointOfSaleUnavailable, null);
        }

        if (!isAdmin && !await userPointOfSaleService.HasAccessAsync(userId, pointOfSaleId))
        {
            return (SalesCardAccessOutcome.PointOfSaleForbidden, null);
        }

        var rows = await repository.HydrateAsync([productId], pointOfSaleId, cancellationToken);
        var anchor = rows.FirstOrDefault(row => row.ProductId == productId);

        return anchor is null
            ? (SalesCardAccessOutcome.ProductNotFound, null)
            : (SalesCardAccessOutcome.Success, anchor);
    }
}
