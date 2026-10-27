using JoiabagurPV.Domain.Commission;
using JoiabagurPV.Domain.Common;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.GiftCards;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.EntityFrameworkCore;

namespace JoiabagurPV.Infrastructure.Data.Repositories;

/// <summary>
/// Repository implementation for Return entity operations.
/// </summary>
public class ReturnRepository : Repository<Return>, IReturnRepository
{
    private readonly ApplicationDbContext _context;

    public ReturnRepository(ApplicationDbContext context) : base(context)
    {
        _context = context;
    }

    /// <inheritdoc/>
    public async Task<Return?> GetByIdWithDetailsAsync(Guid id)
    {
        return await _context.Returns
            .Include(r => r.Product)
            .Include(r => r.PointOfSale)
            .Include(r => r.User)
            .Include(r => r.Photo)
            .Include(r => r.ReturnSales)
                .ThenInclude(rs => rs.Sale)
                    .ThenInclude(s => s.PaymentMethod)
            .Include(r => r.InventoryMovement)
            .FirstOrDefaultAsync(r => r.Id == id);
    }

    /// <inheritdoc/>
    public async Task<(List<Return> Returns, int TotalCount)> GetByPointOfSaleAsync(
        Guid pointOfSaleId,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? productId = null,
        int skip = 0,
        int take = 50)
    {
        var query = _context.Returns
            .Include(r => r.Product)
            .Include(r => r.User)
            .Include(r => r.Photo)
            .Include(r => r.ReturnSales)
                .ThenInclude(rs => rs.Sale)
            .Where(r => r.PointOfSaleId == pointOfSaleId);

        query = ApplyFilters(query, startDate, endDate, productId);

        var totalCount = await query.CountAsync();

        var returns = await query
            .OrderByDescending(r => r.ReturnDate)
            .ThenByDescending(r => r.CreatedAt)
            .Skip(skip)
            .Take(Math.Min(take, PaginationConstants.MaxPageSize))
            .ToListAsync();

        return (returns, totalCount);
    }

    /// <inheritdoc/>
    public async Task<(List<Return> Returns, int TotalCount)> GetAllReturnsAsync(
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? pointOfSaleId = null,
        Guid? productId = null,
        int skip = 0,
        int take = 50)
    {
        var query = _context.Returns
            .Include(r => r.Product)
            .Include(r => r.PointOfSale)
            .Include(r => r.User)
            .Include(r => r.Photo)
            .Include(r => r.ReturnSales)
                .ThenInclude(rs => rs.Sale)
            .AsQueryable();

        if (pointOfSaleId.HasValue)
        {
            query = query.Where(r => r.PointOfSaleId == pointOfSaleId.Value);
        }

        query = ApplyFilters(query, startDate, endDate, productId);

        var totalCount = await query.CountAsync();

        var returns = await query
            .OrderByDescending(r => r.ReturnDate)
            .ThenByDescending(r => r.CreatedAt)
            .Skip(skip)
            .Take(Math.Min(take, PaginationConstants.MaxPageSize))
            .ToListAsync();

        return (returns, totalCount);
    }

    /// <inheritdoc/>
    public async Task<(List<Return> Returns, int TotalCount)> GetByPointOfSalesAsync(
        IEnumerable<Guid> pointOfSaleIds,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? productId = null,
        int skip = 0,
        int take = 50)
    {
        var posIds = pointOfSaleIds.ToList();

        var query = _context.Returns
            .Include(r => r.Product)
            .Include(r => r.PointOfSale)
            .Include(r => r.User)
            .Include(r => r.Photo)
            .Include(r => r.ReturnSales)
                .ThenInclude(rs => rs.Sale)
            .Where(r => posIds.Contains(r.PointOfSaleId));

        query = ApplyFilters(query, startDate, endDate, productId);

        var totalCount = await query.CountAsync();

        var returns = await query
            .OrderByDescending(r => r.ReturnDate)
            .ThenByDescending(r => r.CreatedAt)
            .Skip(skip)
            .Take(Math.Min(take, PaginationConstants.MaxPageSize))
            .ToListAsync();

        return (returns, totalCount);
    }

    /// <summary>
    /// Applies common filters to a return query.
    /// </summary>
    private static IQueryable<Return> ApplyFilters(
        IQueryable<Return> query,
        DateTime? startDate,
        DateTime? endDate,
        Guid? productId)
    {
        if (startDate.HasValue)
        {
            query = query.Where(r => r.ReturnDate >= startDate.Value);
        }

        if (endDate.HasValue)
        {
            query = query.Where(r => r.ReturnDate <= endDate.Value);
        }

        if (productId.HasValue)
        {
            query = query.Where(r => r.ProductId == productId.Value);
        }

        return query;
    }

    public async Task<decimal> GetReturnAmountTotalInWindowAsync(
        IEnumerable<Guid>? pointOfSaleIds,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? pointOfSaleId = null)
    {
        var query = _context.Returns
            .Include(r => r.ReturnSales)
            .AsQueryable();

        if (pointOfSaleIds != null)
        {
            var posIds = pointOfSaleIds.ToList();
            query = query.Where(r => posIds.Contains(r.PointOfSaleId));
        }

        if (pointOfSaleId.HasValue)
            query = query.Where(r => r.PointOfSaleId == pointOfSaleId.Value);

        if (startDate.HasValue)
            query = query.Where(r => r.ReturnDate >= startDate.Value);

        if (endDate.HasValue)
            query = query.Where(r => r.ReturnDate <= endDate.Value);

        var returnSales = await query
            .SelectMany(r => r.ReturnSales)
            .Select(rs => new { rs.SaleId, rs.Quantity, rs.UnitPrice, SaleQuantity = rs.Sale.Quantity })
            .ToListAsync();

        if (returnSales.Count == 0)
            return 0m;

        var saleIds = returnSales.Select(rs => rs.SaleId).Distinct().ToList();
        var coverageRows = await _context.GiftCardCoverageEntries
            .Where(e => saleIds.Contains(e.SaleId))
            .GroupBy(e => e.SaleId)
            .Select(g => new
            {
                SaleId = g.Key,
                Apply = g.Where(e => e.EntryType == GiftCardCoverageEntryType.Apply).Sum(e => e.Amount),
                Release = g.Where(e => e.EntryType == GiftCardCoverageEntryType.Release).Sum(e => e.Amount)
            })
            .ToListAsync();
        var coverageMap = coverageRows.ToDictionary(r => r.SaleId, r => r.Apply - r.Release);

        return returnSales.Sum(rs =>
        {
            var netCoverage = coverageMap.GetValueOrDefault(rs.SaleId, 0m);
            if (netCoverage <= 0 || rs.SaleQuantity <= 0)
                return rs.Quantity * rs.UnitPrice;

            var coverageShare = netCoverage * rs.Quantity / rs.SaleQuantity;
            return rs.Quantity * rs.UnitPrice - coverageShare;
        });
    }

    public async Task<List<ReturnYtdEvent>> GetReturnYtdEventsForPosYearAsync(
        Guid pointOfSaleId,
        DateTime yearStartUtc,
        DateTime yearEndUtc)
    {
        var returns = await _context.Returns
            .Include(r => r.ReturnSales)
                .ThenInclude(rs => rs.Sale)
            .Where(r => r.PointOfSaleId == pointOfSaleId
                && r.ReturnDate >= yearStartUtc
                && r.ReturnDate <= yearEndUtc)
            .ToListAsync();

        var saleIds = returns.SelectMany(r => r.ReturnSales).Select(rs => rs.SaleId).Distinct().ToList();
        var coverageRows = await _context.GiftCardCoverageEntries
            .Where(e => saleIds.Contains(e.SaleId))
            .GroupBy(e => e.SaleId)
            .Select(g => new
            {
                SaleId = g.Key,
                Apply = g.Where(e => e.EntryType == GiftCardCoverageEntryType.Apply).Sum(e => e.Amount),
                Release = g.Where(e => e.EntryType == GiftCardCoverageEntryType.Release).Sum(e => e.Amount)
            })
            .ToListAsync();
        var coverageMap = coverageRows.ToDictionary(r => r.SaleId, r => r.Apply - r.Release);

        return returns.Select(r =>
        {
            var amount = r.ReturnSales.Sum(rs =>
            {
                var sale = rs.Sale;
                var netCoverage = coverageMap.GetValueOrDefault(rs.SaleId, 0m);
                return GiftCardEconomics.GetReturnEconomicAmount(sale, netCoverage, rs.Quantity);
            });
            return new ReturnYtdEvent(r.Id, r.ReturnDate, r.CreatedAt, amount);
        }).ToList();
    }
}
