namespace JoiabagurPV.Domain.Entities;

/// <summary>
/// Audit record when an admin moves a gift card to another point of sale.
/// </summary>
public class GiftCardReassignment : BaseEntity
{
    public Guid GiftCardId { get; set; }
    public Guid FromPointOfSaleId { get; set; }
    public Guid ToPointOfSaleId { get; set; }
    public Guid UserId { get; set; }
    public DateTime OccurredAt { get; set; }

    public virtual GiftCard GiftCard { get; set; } = null!;
    public virtual PointOfSale FromPointOfSale { get; set; } = null!;
    public virtual PointOfSale ToPointOfSale { get; set; } = null!;
    public virtual User User { get; set; } = null!;
}
