namespace JoiabagurPV.Application.DTOs.Sales;

/// <summary>
/// Request DTO for creating a sale.
/// </summary>
public class CreateSaleRequest
{
    /// <summary>
    /// The product being sold.
    /// </summary>
    public Guid ProductId { get; set; }

    /// <summary>
    /// The point of sale where the transaction occurred.
    /// </summary>
    public Guid PointOfSaleId { get; set; }

    /// <summary>
    /// The payment method used for the transaction.
    /// </summary>
    public Guid PaymentMethodId { get; set; }

    /// <summary>
    /// Quantity of units sold. Must be greater than zero.
    /// </summary>
    public int Quantity { get; set; }

    /// <summary>
    /// Optional manual price override. Only accepted when the selected POS has AllowManualPriceEdit enabled.
    /// When null, the official product price is used.
    /// </summary>
    public decimal? Price { get; set; }

    /// <summary>
    /// Optional notes or comments about the sale.
    /// Max 500 characters.
    /// </summary>
    public string? Notes { get; set; }

    /// <summary>
    /// Optional photo data (for image recognition or manual upload).
    /// Base64 encoded string or null if no photo.
    /// </summary>
    public string? PhotoBase64 { get; set; }

    /// <summary>
    /// Original file name for the photo.
    /// </summary>
    public string? PhotoFileName { get; set; }

    /// <summary>
    /// Optional assisted search this sale originated from.
    /// </summary>
    /// <remarks>
    /// Optional on purpose: a sale started by scanning or by SKU search has no search behind it
    /// and stays perfectly valid. An identifier that is unknown, or that belongs to a different
    /// user, degrades the attribution to none — it is never a validation error and never fails
    /// the sale. Attribution is analytics; refusing a sale over it would turn a measurement into
    /// a till outage.
    /// </remarks>
    public Guid? SearchEventId { get; set; }
}
