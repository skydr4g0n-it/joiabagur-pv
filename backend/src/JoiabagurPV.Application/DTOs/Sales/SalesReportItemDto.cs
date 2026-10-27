namespace JoiabagurPV.Application.DTOs.Sales;

public class SalesReportItemDto
{
    public Guid Id { get; set; }
    public DateTime SaleDate { get; set; }
    public string ProductName { get; set; } = string.Empty;
    public string ProductSku { get; set; } = string.Empty;
    public string? CollectionName { get; set; }
    public string PointOfSaleName { get; set; } = string.Empty;
    public int Quantity { get; set; }
    public decimal Price { get; set; }
    public decimal Total { get; set; }
    public decimal? OriginalProductPrice { get; set; }
    public bool PriceWasOverridden { get; set; }
    public string PaymentMethodName { get; set; } = string.Empty;
    public string OperatorName { get; set; } = string.Empty;
    public string? Notes { get; set; }
    public bool HasPhoto { get; set; }
    public bool HasReturn { get; set; }
}
