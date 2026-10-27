namespace JoiabagurPV.Application.DTOs.Sales;

/// <summary>
/// DTO for sale entity.
/// </summary>
public class SaleDto
{
    /// <summary>
    /// The sale ID.
    /// </summary>
    public Guid Id { get; set; }

    /// <summary>
    /// The product ID.
    /// </summary>
    public Guid ProductId { get; set; }

    /// <summary>
    /// The product SKU.
    /// </summary>
    public string ProductSku { get; set; } = string.Empty;

    /// <summary>
    /// The product name.
    /// </summary>
    public string ProductName { get; set; } = string.Empty;

    /// <summary>
    /// The point of sale ID.
    /// </summary>
    public Guid PointOfSaleId { get; set; }

    /// <summary>
    /// The point of sale name.
    /// </summary>
    public string PointOfSaleName { get; set; } = string.Empty;

    /// <summary>
    /// The user (operator) ID.
    /// </summary>
    public Guid UserId { get; set; }

    /// <summary>
    /// The operator's full name.
    /// </summary>
    public string UserName { get; set; } = string.Empty;

    /// <summary>
    /// The payment method ID.
    /// </summary>
    public Guid PaymentMethodId { get; set; }

    /// <summary>
    /// The payment method name.
    /// </summary>
    public string PaymentMethodName { get; set; } = string.Empty;

    /// <summary>
    /// Price at the time of sale.
    /// </summary>
    public decimal Price { get; set; }

    /// <summary>
    /// Quantity sold.
    /// </summary>
    public int Quantity { get; set; }

    /// <summary>
    /// Total amount (Price * Quantity).
    /// </summary>
    public decimal Total { get; set; }

    /// <summary>
    /// Optional notes.
    /// </summary>
    public string? Notes { get; set; }

    /// <summary>
    /// Whether the sale price was manually overridden.
    /// </summary>
    public bool PriceWasOverridden { get; set; }

    /// <summary>
    /// The official product price at the time of sale (when price was overridden).
    /// </summary>
    public decimal? OriginalProductPrice { get; set; }

    /// <summary>
    /// Whether this sale has a photo attached.
    /// </summary>
    public bool HasPhoto { get; set; }

    /// <summary>
    /// Whether this sale has an associated return.
    /// </summary>
    public bool HasReturn { get; set; }

    /// <summary>
    /// Sale date.
    /// </summary>
    public DateTime SaleDate { get; set; }

    /// <summary>
    /// Created timestamp.
    /// </summary>
    public DateTime CreatedAt { get; set; }

    /// <summary>
    /// Net gift card coverage on this sale (apply minus release).
    /// </summary>
    public decimal GiftCardCoverageAmount { get; set; }
}
