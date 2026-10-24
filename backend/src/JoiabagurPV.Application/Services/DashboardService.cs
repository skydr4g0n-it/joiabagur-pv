using JoiabagurPV.Application.DTOs.Dashboard;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Caching.Memory;

namespace JoiabagurPV.Application.Services;

public class DashboardService : IDashboardService
{
    private readonly ISaleRepository _saleRepository;
    private readonly IReturnRepository _returnRepository;
    private readonly IInventoryRepository _inventoryRepository;
    private readonly IUserPointOfSaleRepository _userPointOfSaleRepository;
    private readonly IPosCommissionReportService _commissionReportService;
    private readonly IMemoryCache _cache;

    private const string PaymentDistributionCacheKeyPrefix = "dashboard:payment-distribution";
    private const string ReturnCategoryCacheKeyPrefix = "dashboard:return-category-distribution";
    private static readonly TimeSpan CacheDuration = TimeSpan.FromHours(1);

    private static string PaymentDistributionCacheKey(DateTime monthStart) =>
        $"{PaymentDistributionCacheKeyPrefix}:{monthStart:yyyy-MM}";

    private static string ReturnCategoryCacheKey(DateTime monthStart) =>
        $"{ReturnCategoryCacheKeyPrefix}:{monthStart:yyyy-MM}";

    public DashboardService(
        ISaleRepository saleRepository,
        IReturnRepository returnRepository,
        IInventoryRepository inventoryRepository,
        IUserPointOfSaleRepository userPointOfSaleRepository,
        IPosCommissionReportService commissionReportService,
        IMemoryCache cache)
    {
        _saleRepository = saleRepository ?? throw new ArgumentNullException(nameof(saleRepository));
        _returnRepository = returnRepository ?? throw new ArgumentNullException(nameof(returnRepository));
        _inventoryRepository = inventoryRepository ?? throw new ArgumentNullException(nameof(inventoryRepository));
        _userPointOfSaleRepository = userPointOfSaleRepository ?? throw new ArgumentNullException(nameof(userPointOfSaleRepository));
        _commissionReportService = commissionReportService ?? throw new ArgumentNullException(nameof(commissionReportService));
        _cache = cache ?? throw new ArgumentNullException(nameof(cache));
    }

    public async Task<DashboardStatsDto> GetGlobalStatsAsync()
    {
        var now = DateTime.UtcNow;
        var todayStart = now.Date;
        var monthStart = new DateTime(now.Year, now.Month, 1, 0, 0, 0, DateTimeKind.Utc);
        var monthEnd = new DateTime(now.Year, now.Month,
            DateTime.DaysInMonth(now.Year, now.Month),
            23, 59, 59, DateTimeKind.Utc);
        var previousYearMonthStart = monthStart.AddYears(-1);
        var previousYearMonthEnd = new DateTime(previousYearMonthStart.Year, previousYearMonthStart.Month,
            DateTime.DaysInMonth(previousYearMonthStart.Year, previousYearMonthStart.Month),
            23, 59, 59, DateTimeKind.Utc);

        var salesQuery = _saleRepository.GetAll();
        var returnsQuery = _returnRepository.GetAll();

        var todaySales = await salesQuery
            .Where(s => s.SaleDate >= todayStart && !s.ReturnSales.Any())
            .GroupBy(_ => 1)
            .Select(g => new { Count = g.Count(), Total = g.Sum(s => s.Price * s.Quantity) })
            .FirstOrDefaultAsync();

        var monthlySalesGross = await salesQuery
            .Where(s => s.SaleDate >= monthStart && s.SaleDate <= monthEnd)
            .SumAsync(s => s.Price * s.Quantity);

        decimal? previousYearRevenue = null;
        var prevYearCount = await salesQuery
            .CountAsync(s => s.SaleDate >= previousYearMonthStart && s.SaleDate <= previousYearMonthEnd);
        if (prevYearCount > 0)
        {
            previousYearRevenue = await salesQuery
                .Where(s => s.SaleDate >= previousYearMonthStart && s.SaleDate <= previousYearMonthEnd)
                .SumAsync(s => s.Price * s.Quantity);
        }

        var monthlyReturns = await returnsQuery
            .Include(r => r.ReturnSales)
            .Where(r => r.ReturnDate >= monthStart && r.ReturnDate <= monthEnd)
            .GroupBy(_ => 1)
            .Select(g => new
            {
                Count = g.Count(),
                Total = g.SelectMany(r => r.ReturnSales).Sum(rs => rs.Quantity * rs.UnitPrice)
            })
            .FirstOrDefaultAsync();

        var monthlyReturnsTotal = monthlyReturns?.Total ?? 0m;
        var monthlyRevenue = monthlySalesGross - monthlyReturnsTotal;

        var monthlySaleLines = await _saleRepository.GetSaleLinesForCommissionReportAsync(
            pointOfSaleIds: null,
            startDate: monthStart,
            endDate: monthEnd);

        var monthlyCommission = await _commissionReportService.ComputeCommissionForSalesAsync(
            monthlySaleLines.Select(l => new SaleCommissionLine(l.SaleId, l.PointOfSaleId, l.SaleDateUtc, l.Amount)));

        var paymentDistribution = await GetPaymentMethodDistributionAsync(monthStart, monthEnd);
        var returnCategoryDistribution = await GetReturnCategoryDistributionAsync(monthStart, monthEnd);

        return new DashboardStatsDto
        {
            SalesTodayCount = todaySales?.Count ?? 0,
            SalesTodayTotal = todaySales?.Total ?? 0m,
            MonthlyRevenue = monthlyRevenue,
            MonthlyRevenueNet = monthlyRevenue - monthlyCommission,
            PreviousYearMonthlyRevenue = previousYearRevenue,
            MonthlyReturnsCount = monthlyReturns?.Count ?? 0,
            MonthlyReturnsTotal = monthlyReturnsTotal,
            PaymentMethodDistribution = paymentDistribution,
            ReturnCategoryDistribution = returnCategoryDistribution
        };
    }

    public async Task<DashboardStatsDto> GetPosStatsAsync(Guid posId, Guid userId, bool isAdmin = false)
    {
        if (!isAdmin)
        {
            var hasAccess = await _userPointOfSaleRepository.HasAccessAsync(userId, posId);
            if (!hasAccess)
                throw new UnauthorizedAccessException("No tiene acceso a este punto de venta");
        }

        var now = DateTime.UtcNow;
        var todayStart = now.Date;

        var dayOfWeek = now.DayOfWeek;
        var daysFromMonday = dayOfWeek == DayOfWeek.Sunday ? 6 : (int)dayOfWeek - 1;
        var weekStart = todayStart.AddDays(-daysFromMonday);
        weekStart = DateTime.SpecifyKind(weekStart, DateTimeKind.Utc);

        var salesQuery = _saleRepository.GetAll().Where(s => s.PointOfSaleId == posId);
        var returnsQuery = _returnRepository.GetAll().Where(r => r.PointOfSaleId == posId);

        var todaySales = await salesQuery
            .Where(s => s.SaleDate >= todayStart && !s.ReturnSales.Any())
            .GroupBy(_ => 1)
            .Select(g => new { Count = g.Count(), Total = g.Sum(s => s.Price * s.Quantity) })
            .FirstOrDefaultAsync();

        var weeklyRevenue = await salesQuery
            .Where(s => s.SaleDate >= weekStart && !s.ReturnSales.Any())
            .SumAsync(s => s.Price * s.Quantity);

        var monthStart = new DateTime(now.Year, now.Month, 1, 0, 0, 0, DateTimeKind.Utc);
        var monthEnd = new DateTime(now.Year, now.Month,
            DateTime.DaysInMonth(now.Year, now.Month),
            23, 59, 59, DateTimeKind.Utc);

        var monthlySalesGross = await salesQuery
            .Where(s => s.SaleDate >= monthStart && s.SaleDate <= monthEnd)
            .SumAsync(s => s.Price * s.Quantity);

        var monthlyReturnsTotal = await returnsQuery
            .Where(r => r.ReturnDate >= monthStart && r.ReturnDate <= monthEnd)
            .SelectMany(r => r.ReturnSales)
            .SumAsync(rs => rs.Quantity * rs.UnitPrice);

        var monthlyRevenue = monthlySalesGross - monthlyReturnsTotal;

        var monthlySaleLines = await _saleRepository.GetSaleLinesForCommissionReportAsync(
            pointOfSaleIds: new[] { posId },
            startDate: monthStart,
            endDate: monthEnd,
            pointOfSaleId: posId);

        var monthlyCommission = await _commissionReportService.ComputeCommissionForSalesAsync(
            monthlySaleLines.Select(l => new SaleCommissionLine(l.SaleId, l.PointOfSaleId, l.SaleDateUtc, l.Amount)));

        var returnsTodayCount = await returnsQuery
            .CountAsync(r => r.ReturnDate >= todayStart);

        return new DashboardStatsDto
        {
            SalesTodayCount = todaySales?.Count ?? 0,
            SalesTodayTotal = todaySales?.Total ?? 0m,
            WeeklyRevenue = weeklyRevenue,
            MonthlyRevenue = monthlyRevenue,
            MonthlyRevenueNet = monthlyRevenue - monthlyCommission,
            ReturnsTodayCount = returnsTodayCount
        };
    }

    public void InvalidateDashboardCache()
    {
        var now = DateTime.UtcNow;
        var monthStart = new DateTime(now.Year, now.Month, 1, 0, 0, 0, DateTimeKind.Utc);
        _cache.Remove(PaymentDistributionCacheKey(monthStart));
        _cache.Remove(ReturnCategoryCacheKey(monthStart));
    }

    private async Task<List<PaymentMethodDistributionDto>> GetPaymentMethodDistributionAsync(DateTime monthStart, DateTime monthEnd)
    {
        var cacheKey = PaymentDistributionCacheKey(monthStart);
        if (_cache.TryGetValue(cacheKey, out List<PaymentMethodDistributionDto>? cached) && cached != null)
            return cached;

        var result = await _saleRepository.GetAll()
            .Where(s => s.SaleDate >= monthStart && s.SaleDate <= monthEnd
                && !s.ReturnSales.Any())
            .GroupBy(s => new { s.PaymentMethodId, s.PaymentMethod.Name })
            .Select(g => new PaymentMethodDistributionDto
            {
                MethodName = g.Key.Name,
                Amount = g.Sum(s => s.Price * s.Quantity),
                Count = g.Count()
            })
            .OrderByDescending(d => d.Amount)
            .ToListAsync();

        _cache.Set(cacheKey, result, new MemoryCacheEntryOptions
        {
            AbsoluteExpirationRelativeToNow = CacheDuration
        });

        return result;
    }

    private async Task<List<ReturnCategoryDistributionDto>> GetReturnCategoryDistributionAsync(DateTime monthStart, DateTime monthEnd)
    {
        var cacheKey = ReturnCategoryCacheKey(monthStart);
        if (_cache.TryGetValue(cacheKey, out List<ReturnCategoryDistributionDto>? cached) && cached != null)
            return cached;

        var result = await _returnRepository.GetAll()
            .Where(r => r.ReturnDate >= monthStart && r.ReturnDate <= monthEnd)
            .GroupBy(r => r.Category)
            .Select(g => new ReturnCategoryDistributionDto
            {
                Category = g.Key.ToString(),
                Count = g.Count()
            })
            .OrderByDescending(d => d.Count)
            .ToListAsync();

        _cache.Set(cacheKey, result, new MemoryCacheEntryOptions
        {
            AbsoluteExpirationRelativeToNow = CacheDuration
        });

        return result;
    }

    public async Task<PaginatedLowStockResult> GetLowStockAsync(int page, int pageSize, int maxQuantity = 2)
    {
        var query = _inventoryRepository.GetAll()
            .Include(i => i.Product)
            .Include(i => i.PointOfSale)
            .Where(i => i.IsActive && i.Quantity <= maxQuantity)
            .OrderBy(i => i.Quantity)
            .ThenBy(i => i.Product.Name);

        var totalCount = await query.CountAsync();

        var items = await query
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .Select(i => new LowStockItemDto
            {
                ProductName = i.Product.Name,
                Sku = i.Product.SKU,
                PointOfSaleName = i.PointOfSale.Name,
                Stock = i.Quantity
            })
            .ToListAsync();

        return new PaginatedLowStockResult
        {
            Items = items,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize,
            TotalPages = (int)Math.Ceiling((double)totalCount / pageSize)
        };
    }
}
