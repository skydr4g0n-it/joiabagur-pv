namespace JoiabagurPV.Application.DTOs.Sales;

public class BulkSaleLineRequest
{
    public Guid ProductId { get; set; }
    public int Quantity { get; set; }
    public decimal? Price { get; set; }
    public string? PhotoBase64 { get; set; }
    public string? PhotoFileName { get; set; }
}

public class CreateBulkSalesRequest
{
    public Guid PointOfSaleId { get; set; }
    public Guid PaymentMethodId { get; set; }
    public string? Notes { get; set; }
    public List<BulkSaleLineRequest> Lines { get; set; } = new();
    public List<string> GiftCardCodes { get; set; } = new();
}
