using JoiabagurPV.Domain.Enums;

namespace JoiabagurPV.Domain.Entities;

/// <summary>
/// Append-only ledger row for gift card coverage applied to or released from a sale.
/// </summary>
public class GiftCardCoverageEntry : BaseEntity
{
    public Guid GiftCardId { get; set; }

    /// <summary>
    /// Product sale receiving Apply, or sale whose coverage is released.
    /// </summary>
    public Guid SaleId { get; set; }

    public GiftCardCoverageEntryType EntryType { get; set; }

    public decimal Amount { get; set; }

    /// <summary>
    /// Economic date of the apply or release (redemption or exchange day).
    /// </summary>
    public DateTime EntryDate { get; set; }

    public virtual GiftCard GiftCard { get; set; } = null!;
    public virtual Sale Sale { get; set; } = null!;
}
