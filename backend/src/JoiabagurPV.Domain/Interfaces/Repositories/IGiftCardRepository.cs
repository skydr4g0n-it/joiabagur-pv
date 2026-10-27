using JoiabagurPV.Domain.Commission;
using JoiabagurPV.Domain.Entities;

namespace JoiabagurPV.Domain.Interfaces.Repositories;

/// <summary>
/// Repository for gift cards and coverage ledger operations.
/// </summary>
public interface IGiftCardRepository : IRepository<GiftCard>
{
    Task<GiftCard?> GetByIdWithDetailsAsync(Guid id);

    Task<GiftCard?> GetByCodeAsync(string code);

    Task<GiftCard?> GetByIssuanceIdempotencyKeyAsync(string idempotencyKey);

    /// <summary>
    /// Locks gift card rows for the given codes (PostgreSQL FOR UPDATE) within the current transaction.
    /// </summary>
    Task<List<GiftCard>> LockByCodesAsync(IEnumerable<string> codes);

    Task<(List<GiftCard> Items, int TotalCount)> ListAsync(
        IEnumerable<Guid>? pointOfSaleIds,
        int skip,
        int take);

    Task<decimal> GetAccountedRemainderAsync(Guid giftCardId);

    Task<decimal> GetNetCoverageOnSaleAsync(Guid saleId);

    Task<Dictionary<Guid, decimal>> GetNetCoverageBySaleIdsAsync(IEnumerable<Guid> saleIds);

    Task<HashSet<Guid>> GetIssuanceSaleIdsAsync(IEnumerable<Guid> saleIds);

    Task<bool> IsIssuanceSaleAsync(Guid saleId);

    Task<bool> SaleHasGiftCardCoverageAsync(Guid saleId);

    Task<decimal> GetCoverageNetInWindowAsync(
        IEnumerable<Guid>? pointOfSaleIds,
        DateTime? startDate,
        DateTime? endDate,
        Guid? pointOfSaleId = null);

    Task<List<GiftCardCoverageYtdEvent>> GetCoverageReleaseYtdEventsForPosYearAsync(
        Guid pointOfSaleId,
        DateTime yearStartUtc,
        DateTime yearEndUtc);

    Task AddCoverageEntryAsync(GiftCardCoverageEntry entry);

    Task AddReassignmentAsync(GiftCardReassignment reassignment);

    Task<GiftCardExchangeOperation?> GetExchangeByIdempotencyKeyAsync(Guid giftCardId, string idempotencyKey);

    Task AddExchangeOperationAsync(GiftCardExchangeOperation operation);
}
