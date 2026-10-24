namespace JoiabagurPV.Application.Commission;

public sealed record CommissionTierBracket(
    decimal MinAmountInclusive,
    decimal? MaxAmountInclusive,
    decimal CommissionPercent);
