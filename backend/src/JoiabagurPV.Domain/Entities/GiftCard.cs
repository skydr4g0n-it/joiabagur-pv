using JoiabagurPV.Domain.Enums;

namespace JoiabagurPV.Domain.Entities;

/// <summary>
/// A gift card sold at a point of sale and redeemable once for spendable balance.
/// </summary>
public class GiftCard : BaseEntity
{
    /// <summary>
    /// Unique code starting with GC-.
    /// </summary>
    public required string Code { get; set; }

    /// <summary>
    /// Current point of sale where the card can be redeemed.
    /// </summary>
    public Guid PointOfSaleId { get; set; }

    /// <summary>
    /// Optional holder name (max 100 characters).
    /// </summary>
    public string? HolderName { get; set; }

    /// <summary>
    /// Face value at issuance; immutable.
    /// </summary>
    public decimal NominalAmount { get; set; }

    /// <summary>
    /// Amount still spendable on checkout; set to zero after first apply.
    /// </summary>
    public decimal SpendableBalance { get; set; }

    /// <summary>
    /// Last valid UTC calendar day for redemption.
    /// </summary>
    public DateOnly ExpiryDate { get; set; }

    /// <summary>
    /// Sale of the system product at issuance.
    /// </summary>
    public Guid IssuanceSaleId { get; set; }

    /// <summary>
    /// Operator or admin who issued the card.
    /// </summary>
    public Guid IssuedByUserId { get; set; }

    /// <summary>
    /// Optional idempotency key from POST /api/gift-cards.
    /// </summary>
    public string? IssuanceIdempotencyKey { get; set; }

    public virtual PointOfSale PointOfSale { get; set; } = null!;
    public virtual Sale IssuanceSale { get; set; } = null!;
    public virtual User IssuedByUser { get; set; } = null!;
    public virtual ICollection<GiftCardCoverageEntry> CoverageEntries { get; set; } = new List<GiftCardCoverageEntry>();
    public virtual ICollection<GiftCardReassignment> Reassignments { get; set; } = new List<GiftCardReassignment>();
}
