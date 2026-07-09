namespace JoiabagurPV.Application.DTOs.Inventory;

public class InventoryMovementReportFilterRequest
{
    public string? OutputModel { get; set; }
    public DateTime? StartDate { get; set; }
    public DateTime? EndDate { get; set; }
    public Guid? PointOfSaleId { get; set; }
    public string? ProductSearch { get; set; }
    public int Page { get; set; } = 1;
    public int PageSize { get; set; } = 20;
    public string? SortBy { get; set; }
    public string? SortDirection { get; set; }
}
