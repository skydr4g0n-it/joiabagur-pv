using JoiabagurPV.Domain.GiftCards;
using JoiabagurPV.Domain.Commission;
using JoiabagurPV.Domain.Common;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.EntityFrameworkCore;

namespace JoiabagurPV.Infrastructure.Data.Repositories;

/// <summary>
/// Repository implementation for Sale entity operations.
/// </summary>
public class SaleRepository : Repository<Sale>, ISaleRepository
{
    private readonly ApplicationDbContext _context;

    public SaleRepository(ApplicationDbContext context) : base(context)
    {
        _context = context;
    }

    /// <inheritdoc/>
    public async Task<Sale?> GetByIdWithDetailsAsync(Guid id)
    {
        return await _context.Sales
            .Include(s => s.Product)
            .Include(s => s.PointOfSale)
            .Include(s => s.User)
            .Include(s => s.PaymentMethod)
            .Include(s => s.Photo)
            .Include(s => s.InventoryMovement)
            .FirstOrDefaultAsync(s => s.Id == id);
    }

    /// <inheritdoc/>
    public async Task<(List<Sale> Sales, int TotalCount)> GetByPointOfSaleAsync(
        Guid pointOfSaleId,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? productId = null,
        Guid? userId = null,
        Guid? paymentMethodId = null,
        int skip = 0,
        int take = 50)
    {
        var query = _context.Sales
            .Include(s => s.Product)
            .Include(s => s.User)
            .Include(s => s.PaymentMethod)
            .Include(s => s.Photo)
            .Include(s => s.ReturnSales)
            .Where(s => s.PointOfSaleId == pointOfSaleId);

        query = ApplyFilters(query, startDate, endDate, productId, userId, paymentMethodId);

        var totalCount = await query.CountAsync();

        var sales = await query
            .OrderByDescending(s => s.SaleDate)
            .ThenByDescending(s => s.CreatedAt)
            .Skip(skip)
            .Take(Math.Min(take, PaginationConstants.MaxPageSize))
            .ToListAsync();

        return (sales, totalCount);
    }

    /// <inheritdoc/>
    public async Task<(List<Sale> Sales, int TotalCount)> GetAllSalesAsync(
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? pointOfSaleId = null,
        Guid? productId = null,
        Guid? userId = null,
        Guid? paymentMethodId = null,
        int skip = 0,
        int take = 50)
    {
        var query = _context.Sales
            .Include(s => s.Product)
            .Include(s => s.PointOfSale)
            .Include(s => s.User)
            .Include(s => s.PaymentMethod)
            .Include(s => s.Photo)
            .Include(s => s.ReturnSales)
            .AsQueryable();

        if (pointOfSaleId.HasValue)
        {
            query = query.Where(s => s.PointOfSaleId == pointOfSaleId.Value);
        }

        query = ApplyFilters(query, startDate, endDate, productId, userId, paymentMethodId);

        var totalCount = await query.CountAsync();

        var sales = await query
            .OrderByDescending(s => s.SaleDate)
            .ThenByDescending(s => s.CreatedAt)
            .Skip(skip)
            .Take(Math.Min(take, PaginationConstants.MaxPageSize))
            .ToListAsync();

        return (sales, totalCount);
    }

    /// <inheritdoc/>
    public async Task<(List<Sale> Sales, int TotalCount)> GetByPointOfSalesAsync(
        IEnumerable<Guid> pointOfSaleIds,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? productId = null,
        Guid? userId = null,
        Guid? paymentMethodId = null,
        int skip = 0,
        int take = 50)
    {
        var posIds = pointOfSaleIds.ToList();
        
        var query = _context.Sales
            .Include(s => s.Product)
            .Include(s => s.PointOfSale)
            .Include(s => s.User)
            .Include(s => s.PaymentMethod)
            .Include(s => s.Photo)
            .Include(s => s.ReturnSales)
            .Where(s => posIds.Contains(s.PointOfSaleId));

        query = ApplyFilters(query, startDate, endDate, productId, userId, paymentMethodId);

        var totalCount = await query.CountAsync();

        var sales = await query
            .OrderByDescending(s => s.SaleDate)
            .ThenByDescending(s => s.CreatedAt)
            .Skip(skip)
            .Take(Math.Min(take, PaginationConstants.MaxPageSize))
            .ToListAsync();

        return (sales, totalCount);
    }

    /// <inheritdoc/>
    public async Task<(List<Sale> Sales, int TotalCount)> GetSalesForReportAsync(
        IEnumerable<Guid>? pointOfSaleIds,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? pointOfSaleId = null,
        Guid? productId = null,
        Guid? userId = null,
        Guid? paymentMethodId = null,
        string? search = null,
        decimal? amountMin = null,
        decimal? amountMax = null,
        bool? hasPhoto = null,
        bool? priceWasOverridden = null,
        int skip = 0,
        int take = 20)
    {
        var query = BuildReportQuery(pointOfSaleIds, startDate, endDate, pointOfSaleId,
            productId, userId, paymentMethodId, search, amountMin, amountMax, hasPhoto, priceWasOverridden);

        var totalCount = await query.CountAsync();

        var sales = await query
            .OrderByDescending(s => s.SaleDate)
            .ThenByDescending(s => s.CreatedAt)
            .Skip(skip)
            .Take(take)
            .ToListAsync();

        return (sales, totalCount);
    }

    /// <inheritdoc/>
    public async Task<(int TotalCount, int TotalQuantity, decimal TotalAmount)> GetSalesReportAggregatesAsync(
        IEnumerable<Guid>? pointOfSaleIds,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? pointOfSaleId = null,
        Guid? productId = null,
        Guid? userId = null,
        Guid? paymentMethodId = null,
        string? search = null,
        decimal? amountMin = null,
        decimal? amountMax = null,
        bool? hasPhoto = null,
        bool? priceWasOverridden = null)
    {
        var query = BuildReportQuery(pointOfSaleIds, startDate, endDate, pointOfSaleId,
            productId, userId, paymentMethodId, search, amountMin, amountMax, hasPhoto, priceWasOverridden);

        var result = await query
            .GroupBy(_ => 1)
            .Select(g => new
            {
                TotalCount = g.Count(),
                TotalQuantity = g.Sum(s => s.Quantity),
                TotalAmount = g.Sum(s => s.Price * s.Quantity)
            })
            .FirstOrDefaultAsync();

        if (result == null)
            return (0, 0, 0m);

        return (result.TotalCount, result.TotalQuantity, result.TotalAmount);
    }

    private IQueryable<Sale> BuildReportQuery(
        IEnumerable<Guid>? pointOfSaleIds,
        DateTime? startDate,
        DateTime? endDate,
        Guid? pointOfSaleId,
        Guid? productId,
        Guid? userId,
        Guid? paymentMethodId,
        string? search,
        decimal? amountMin,
        decimal? amountMax,
        bool? hasPhoto,
        bool? priceWasOverridden)
    {
        var query = _context.Sales
            .Include(s => s.Product)
                .ThenInclude(p => p.Collection)
            .Include(s => s.PointOfSale)
            .Include(s => s.User)
            .Include(s => s.PaymentMethod)
            .Include(s => s.Photo)
            .Include(s => s.ReturnSales)
            .AsQueryable();

        if (pointOfSaleIds != null)
        {
            var posIds = pointOfSaleIds.ToList();
            query = query.Where(s => posIds.Contains(s.PointOfSaleId));
        }

        if (pointOfSaleId.HasValue)
        {
            query = query.Where(s => s.PointOfSaleId == pointOfSaleId.Value);
        }

        query = ApplyFilters(query, startDate, endDate, productId, userId, paymentMethodId);

        if (!string.IsNullOrWhiteSpace(search))
        {
            var searchLower = search.ToLower();
            query = query.Where(s =>
                s.Product.SKU.ToLower().Contains(searchLower) ||
                s.Product.Name.ToLower().Contains(searchLower));
        }

        if (amountMin.HasValue)
        {
            query = query.Where(s => s.Price * s.Quantity >= amountMin.Value);
        }

        if (amountMax.HasValue)
        {
            query = query.Where(s => s.Price * s.Quantity <= amountMax.Value);
        }

        if (hasPhoto.HasValue)
        {
            query = hasPhoto.Value
                ? query.Where(s => s.Photo != null)
                : query.Where(s => s.Photo == null);
        }

        if (priceWasOverridden.HasValue)
        {
            query = query.Where(s => s.PriceWasOverridden == priceWasOverridden.Value);
        }

        return query;
    }

    private static IQueryable<Sale> ApplyFilters(
        IQueryable<Sale> query,
        DateTime? startDate,
        DateTime? endDate,
        Guid? productId,
        Guid? userId,
        Guid? paymentMethodId)
    {
        if (startDate.HasValue)
        {
            query = query.Where(s => s.SaleDate >= startDate.Value);
        }

        if (endDate.HasValue)
        {
            query = query.Where(s => s.SaleDate <= endDate.Value);
        }

        if (productId.HasValue)
        {
            query = query.Where(s => s.ProductId == productId.Value);
        }

        if (userId.HasValue)
        {
            query = query.Where(s => s.UserId == userId.Value);
        }

        if (paymentMethodId.HasValue)
        {
            query = query.Where(s => s.PaymentMethodId == paymentMethodId.Value);
        }

        return query;
    }

    public async Task<List<SaleReportLine>> GetSaleLinesForCommissionReportAsync(
        IEnumerable<Guid>? pointOfSaleIds,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? pointOfSaleId = null,
        Guid? productId = null,
        Guid? userId = null,
        Guid? paymentMethodId = null,
        string? search = null,
        decimal? amountMin = null,
        decimal? amountMax = null,
        bool? hasPhoto = null,
        bool? priceWasOverridden = null)
    {
        var query = BuildReportQuery(pointOfSaleIds, startDate, endDate, pointOfSaleId,
            productId, userId, paymentMethodId, search, amountMin, amountMax, hasPhoto, priceWasOverridden);

        var sales = await query
            .Select(s => new { s.Id, s.PointOfSaleId, s.SaleDate, Gross = s.Price * s.Quantity })
            .ToListAsync();

        return await MapEconomicSaleReportLinesAsync(sales.Select(s => (s.Id, s.PointOfSaleId, s.SaleDate, s.Gross)).ToList());
    }

    public async Task<List<SaleYtdEvent>> GetSaleYtdEventsForPosYearAsync(
        Guid pointOfSaleId,
        DateTime yearStartUtc,
        DateTime yearEndUtc)
    {
        var sales = await _context.Sales
            .Where(s => s.PointOfSaleId == pointOfSaleId
                && s.SaleDate >= yearStartUtc
                && s.SaleDate <= yearEndUtc)
            .Select(s => new { s.Id, s.SaleDate, s.CreatedAt, Gross = s.Price * s.Quantity })
            .ToListAsync();

        var lines = await MapEconomicSaleReportLinesAsync(
            sales.Select(s => (s.Id, pointOfSaleId, s.SaleDate, s.Gross)).ToList());

        return sales.Select(s =>
        {
            var amount = lines.First(l => l.SaleId == s.Id).Amount;
            return new SaleYtdEvent(s.Id, s.SaleDate, s.CreatedAt, amount);
        }).ToList();
    }

    private async Task<List<SaleReportLine>> MapEconomicSaleReportLinesAsync(
        List<(Guid SaleId, Guid PointOfSaleId, DateTime SaleDate, decimal Gross)> sales)
    {
        if (sales.Count == 0)
            return new List<SaleReportLine>();

        var saleIds = sales.Select(s => s.SaleId).ToList();
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
        var coverageMap = coverageRows.ToDictionary(
            r => r.SaleId,
            r => r.Apply - r.Release);

        var issuanceIds = await _context.GiftCards
            .Where(g => saleIds.Contains(g.IssuanceSaleId))
            .Select(g => g.IssuanceSaleId)
            .ToListAsync();
        var issuanceSet = issuanceIds.ToHashSet();

        return sales.Select(s =>
        {
            var netCoverage = coverageMap.GetValueOrDefault(s.SaleId, 0m);
            var amount = GiftCardEconomics.GetEconomicSaleAmount(
                s.Gross,
                netCoverage,
                issuanceSet.Contains(s.SaleId));
            return new SaleReportLine(s.SaleId, s.PointOfSaleId, s.SaleDate, amount);
        }).ToList();
    }
}
