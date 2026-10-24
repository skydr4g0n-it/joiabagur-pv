namespace JoiabagurPV.Application.DTOs.PointOfSales;

public class CommissionTierDto
{
    public Guid Id { get; set; }
    public decimal MinAmountInclusive { get; set; }
    public decimal? MaxAmountInclusive { get; set; }
    public decimal CommissionPercent { get; set; }
}

public class ReplaceCommissionTiersRequest
{
    public List<CommissionTierInputDto> Tiers { get; set; } = new();
}

public class CommissionTierInputDto
{
    public decimal MinAmountInclusive { get; set; }
    public decimal? MaxAmountInclusive { get; set; }
    public decimal CommissionPercent { get; set; }
}
