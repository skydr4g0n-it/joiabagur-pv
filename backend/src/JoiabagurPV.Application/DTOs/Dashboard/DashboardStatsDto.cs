namespace JoiabagurPV.Application.DTOs.Dashboard;

public class DashboardStatsDto
{
    public int SalesTodayCount { get; set; }
    public decimal SalesTodayTotal { get; set; }
    public decimal MonthlyRevenue { get; set; }
    public decimal MonthlyRevenueNet { get; set; }
    public decimal? PreviousYearMonthlyRevenue { get; set; }
    public int MonthlyReturnsCount { get; set; }
    public decimal MonthlyReturnsTotal { get; set; }
    public decimal? WeeklyRevenue { get; set; }
    public int? ReturnsTodayCount { get; set; }
    public List<PaymentMethodDistributionDto>? PaymentMethodDistribution { get; set; }
    public List<ReturnCategoryDistributionDto>? ReturnCategoryDistribution { get; set; }
}

public class PaymentMethodDistributionDto
{
    public string MethodName { get; set; } = string.Empty;
    public decimal Amount { get; set; }
    public int Count { get; set; }
}

public class ReturnCategoryDistributionDto
{
    public string Category { get; set; } = string.Empty;
    public int Count { get; set; }
}

public class LowStockItemDto
{
    public string ProductName { get; set; } = string.Empty;
    public string Sku { get; set; } = string.Empty;
    public string PointOfSaleName { get; set; } = string.Empty;
    public int Stock { get; set; }
}

public class PaginatedLowStockResult
{
    public List<LowStockItemDto> Items { get; set; } = new();
    public int TotalCount { get; set; }
    public int Page { get; set; }
    public int PageSize { get; set; }
    public int TotalPages { get; set; }
}
