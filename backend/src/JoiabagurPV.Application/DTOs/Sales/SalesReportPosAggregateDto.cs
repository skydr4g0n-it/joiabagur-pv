namespace JoiabagurPV.Application.DTOs.Sales;

public class SalesReportPosAggregateDto
{
    public Guid PointOfSaleId { get; set; }
    public decimal TotalAmount { get; set; }
    public decimal TotalCommission { get; set; }
    public decimal TotalAmountNet { get; set; }
}
