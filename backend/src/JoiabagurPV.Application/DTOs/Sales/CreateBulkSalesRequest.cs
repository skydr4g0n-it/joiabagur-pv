namespace JoiabagurPV.Application.DTOs.Sales;

public class BulkSaleLineRequest
{
    public Guid ProductId { get; set; }
    public int Quantity { get; set; }
    public decimal? Price { get; set; }
    public string? PhotoBase64 { get; set; }
    public string? PhotoFileName { get; set; }

    /// <summary>
    /// Optional assisted search this line originated from.
    /// </summary>
    /// <remarks>
    /// Per line rather than per operation: each line of a checkout may come from a different
    /// search, or from none. An identifier that is unknown, or that belongs to a different user,
    /// degrades the attribution to none — it never fails the line and never fails the checkout.
    /// </remarks>
    public Guid? SearchEventId { get; set; }
}

public class CreateBulkSalesRequest
{
    public Guid PointOfSaleId { get; set; }
    public Guid PaymentMethodId { get; set; }
    public string? Notes { get; set; }
    public List<BulkSaleLineRequest> Lines { get; set; } = new();
}
