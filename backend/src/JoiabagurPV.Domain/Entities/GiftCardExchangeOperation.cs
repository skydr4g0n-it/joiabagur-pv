namespace JoiabagurPV.Domain.Entities;

/// <summary>
/// Idempotent record of a gift card exchange (POST /api/gift-cards/{id}/exchanges).
/// </summary>
public class GiftCardExchangeOperation : BaseEntity
{
    public Guid GiftCardId { get; set; }

    public required string IdempotencyKey { get; set; }

    public decimal CashDue { get; set; }

    /// <summary>
    /// Comma-separated sale identifiers created by the exchange.
    /// </summary>
    public required string NewSaleIdsCsv { get; set; }

    /// <summary>
    /// Comma-separated return identifiers created by the exchange.
    /// </summary>
    public required string ReturnIdsCsv { get; set; }

    public virtual GiftCard GiftCard { get; set; } = null!;
}
