namespace JoiabagurPV.Domain.Entities;

/// <summary>
/// Annual sales commission tier for a point of sale (YTD amount brackets).
/// </summary>
public class PointOfSaleCommissionTier : BaseEntity
{
    public Guid PointOfSaleId { get; set; }

    public decimal MinAmountInclusive { get; set; }

    public decimal? MaxAmountInclusive { get; set; }

    public decimal CommissionPercent { get; set; }

    public PointOfSale PointOfSale { get; set; } = null!;
}
