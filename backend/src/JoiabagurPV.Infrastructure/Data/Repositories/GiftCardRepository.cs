using JoiabagurPV.Domain.Commission;
using JoiabagurPV.Domain.Common;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.EntityFrameworkCore;

namespace JoiabagurPV.Infrastructure.Data.Repositories;

public class GiftCardRepository : Repository<GiftCard>, IGiftCardRepository
{
    private readonly ApplicationDbContext _context;

    public GiftCardRepository(ApplicationDbContext context) : base(context)
    {
        _context = context;
    }

    public async Task<GiftCard?> GetByIdWithDetailsAsync(Guid id)
    {
        return await _context.GiftCards
            .Include(g => g.PointOfSale)
            .Include(g => g.IssuanceSale)
                .ThenInclude(s => s.PaymentMethod)
            .Include(g => g.IssuanceSale)
                .ThenInclude(s => s.PointOfSale)
            .Include(g => g.IssuedByUser)
            .Include(g => g.CoverageEntries)
                .ThenInclude(e => e.Sale)
                    .ThenInclude(s => s.Product)
            .Include(g => g.Reassignments)
                .ThenInclude(r => r.FromPointOfSale)
            .Include(g => g.Reassignments)
                .ThenInclude(r => r.ToPointOfSale)
            .Include(g => g.Reassignments)
                .ThenInclude(r => r.User)
            .FirstOrDefaultAsync(g => g.Id == id);
    }

    public async Task<GiftCard?> GetByCodeAsync(string code)
    {
        return await _context.GiftCards
            .Include(g => g.PointOfSale)
            .FirstOrDefaultAsync(g => g.Code == code);
    }

    public async Task<GiftCard?> GetByIssuanceIdempotencyKeyAsync(string idempotencyKey)
    {
        return await _context.GiftCards
            .Include(g => g.PointOfSale)
            .Include(g => g.IssuanceSale)
                .ThenInclude(s => s.PaymentMethod)
            .FirstOrDefaultAsync(g => g.IssuanceIdempotencyKey == idempotencyKey);
    }

    public async Task<List<GiftCard>> LockByCodesAsync(IEnumerable<string> codes)
    {
        var codeList = codes.Distinct().OrderBy(c => c).ToList();
        if (codeList.Count == 0)
            return new List<GiftCard>();

        var locked = new List<GiftCard>();
        foreach (var code in codeList)
        {
            var card = await _context.GiftCards
                .FromSqlInterpolated($"SELECT * FROM \"GiftCards\" WHERE \"Code\" = {code} FOR UPDATE")
                .Include(g => g.CoverageEntries)
                .FirstOrDefaultAsync();
            if (card != null)
                locked.Add(card);
        }

        return locked;
    }

    public async Task<(List<GiftCard> Items, int TotalCount)> ListAsync(
        IEnumerable<Guid>? pointOfSaleIds,
        int skip,
        int take)
    {
        var query = _context.GiftCards
            .Include(g => g.PointOfSale)
            .AsQueryable();

        if (pointOfSaleIds != null)
        {
            var ids = pointOfSaleIds.ToList();
            query = query.Where(g => ids.Contains(g.PointOfSaleId));
        }

        var totalCount = await query.CountAsync();
        var items = await query
            .OrderByDescending(g => g.CreatedAt)
            .Skip(skip)
            .Take(Math.Min(take, PaginationConstants.MaxPageSize))
            .ToListAsync();

        return (items, totalCount);
    }

    public async Task<decimal> GetAccountedRemainderAsync(Guid giftCardId)
    {
        var nominal = await _context.GiftCards
            .Where(g => g.Id == giftCardId)
            .Select(g => g.NominalAmount)
            .FirstOrDefaultAsync();

        var totals = await _context.GiftCardCoverageEntries
            .Where(e => e.GiftCardId == giftCardId)
            .GroupBy(_ => 1)
            .Select(g => new
            {
                Apply = g.Where(e => e.EntryType == GiftCardCoverageEntryType.Apply).Sum(e => e.Amount),
                Release = g.Where(e => e.EntryType == GiftCardCoverageEntryType.Release).Sum(e => e.Amount)
            })
            .FirstOrDefaultAsync();

        var apply = totals?.Apply ?? 0m;
        var release = totals?.Release ?? 0m;
        return nominal - (apply - release);
    }

    public async Task<decimal> GetNetCoverageOnSaleAsync(Guid saleId)
    {
        var totals = await _context.GiftCardCoverageEntries
            .Where(e => e.SaleId == saleId)
            .GroupBy(_ => 1)
            .Select(g => new
            {
                Apply = g.Where(e => e.EntryType == GiftCardCoverageEntryType.Apply).Sum(e => e.Amount),
                Release = g.Where(e => e.EntryType == GiftCardCoverageEntryType.Release).Sum(e => e.Amount)
            })
            .FirstOrDefaultAsync();

        return (totals?.Apply ?? 0m) - (totals?.Release ?? 0m);
    }

    public async Task<Dictionary<Guid, decimal>> GetNetCoverageBySaleIdsAsync(IEnumerable<Guid> saleIds)
    {
        var ids = saleIds.Distinct().ToList();
        if (ids.Count == 0)
            return new Dictionary<Guid, decimal>();

        var rows = await _context.GiftCardCoverageEntries
            .Where(e => ids.Contains(e.SaleId))
            .GroupBy(e => e.SaleId)
            .Select(g => new
            {
                SaleId = g.Key,
                Apply = g.Where(e => e.EntryType == GiftCardCoverageEntryType.Apply).Sum(e => e.Amount),
                Release = g.Where(e => e.EntryType == GiftCardCoverageEntryType.Release).Sum(e => e.Amount)
            })
            .ToListAsync();

        return rows.ToDictionary(r => r.SaleId, r => r.Apply - r.Release);
    }

    public async Task<HashSet<Guid>> GetIssuanceSaleIdsAsync(IEnumerable<Guid> saleIds)
    {
        var ids = saleIds.Distinct().ToList();
        if (ids.Count == 0)
            return new HashSet<Guid>();

        var issuanceIds = await _context.GiftCards
            .Where(g => ids.Contains(g.IssuanceSaleId))
            .Select(g => g.IssuanceSaleId)
            .ToListAsync();

        return issuanceIds.ToHashSet();
    }

    public async Task<bool> IsIssuanceSaleAsync(Guid saleId) =>
        await _context.GiftCards.AnyAsync(g => g.IssuanceSaleId == saleId);

    public async Task<bool> SaleHasGiftCardCoverageAsync(Guid saleId) =>
        await _context.GiftCardCoverageEntries.AnyAsync(e =>
            e.SaleId == saleId && e.EntryType == GiftCardCoverageEntryType.Apply);

    public async Task<decimal> GetCoverageNetInWindowAsync(
        IEnumerable<Guid>? pointOfSaleIds,
        DateTime? startDate,
        DateTime? endDate,
        Guid? pointOfSaleId = null)
    {
        var query = _context.GiftCardCoverageEntries
            .Include(e => e.Sale)
            .AsQueryable();

        if (pointOfSaleId.HasValue)
            query = query.Where(e => e.Sale.PointOfSaleId == pointOfSaleId.Value);
        else if (pointOfSaleIds != null)
        {
            var ids = pointOfSaleIds.ToList();
            query = query.Where(e => ids.Contains(e.Sale.PointOfSaleId));
        }

        if (startDate.HasValue)
            query = query.Where(e => e.EntryDate >= startDate.Value);

        if (endDate.HasValue)
            query = query.Where(e => e.EntryDate <= endDate.Value);

        var apply = await query
            .Where(e => e.EntryType == GiftCardCoverageEntryType.Apply)
            .SumAsync(e => e.Amount);

        var release = await query
            .Where(e => e.EntryType == GiftCardCoverageEntryType.Release)
            .SumAsync(e => e.Amount);

        return apply - release;
    }

    public async Task<List<GiftCardCoverageYtdEvent>> GetCoverageReleaseYtdEventsForPosYearAsync(
        Guid pointOfSaleId,
        DateTime yearStartUtc,
        DateTime yearEndUtc)
    {
        return await _context.GiftCardCoverageEntries
            .Include(e => e.Sale)
            .Where(e => e.Sale.PointOfSaleId == pointOfSaleId
                && e.EntryType == GiftCardCoverageEntryType.Release
                && e.EntryDate >= yearStartUtc
                && e.EntryDate <= yearEndUtc)
            .Select(e => new GiftCardCoverageYtdEvent(e.EntryDate, e.CreatedAt, e.Amount))
            .ToListAsync();
    }

    public async Task AddCoverageEntryAsync(GiftCardCoverageEntry entry)
    {
        await _context.GiftCardCoverageEntries.AddAsync(entry);
    }

    public async Task AddReassignmentAsync(GiftCardReassignment reassignment)
    {
        await _context.GiftCardReassignments.AddAsync(reassignment);
    }

    public async Task<GiftCardExchangeOperation?> GetExchangeByIdempotencyKeyAsync(Guid giftCardId, string idempotencyKey)
    {
        return await _context.GiftCardExchangeOperations
            .FirstOrDefaultAsync(e => e.GiftCardId == giftCardId && e.IdempotencyKey == idempotencyKey);
    }

    public async Task AddExchangeOperationAsync(GiftCardExchangeOperation operation)
    {
        await _context.GiftCardExchangeOperations.AddAsync(operation);
    }
}
