namespace JoiabagurPV.Application.DTOs.Sales;

public class SalesReportResponse
{
    public List<SalesReportItemDto> Items { get; set; } = new();
    public int TotalCount { get; set; }
    public int Page { get; set; }
    public int PageSize { get; set; }
    public int TotalPages { get; set; }
    public int TotalSalesCount { get; set; }
    public int TotalQuantity { get; set; }
    public decimal TotalAmount { get; set; }
    public decimal TotalCommission { get; set; }
    public decimal TotalAmountNet { get; set; }
    public List<SalesReportPosAggregateDto>? AggregatesByPointOfSale { get; set; }
}
