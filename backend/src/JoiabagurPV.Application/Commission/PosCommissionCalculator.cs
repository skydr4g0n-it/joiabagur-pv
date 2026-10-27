using JoiabagurPV.Domain.Common;

namespace JoiabagurPV.Application.Commission;

public enum CommissionTimelineEventKind
{
    Sale,
    Return,
    CoverageRelease
}

public sealed record CommissionTimelineEvent(
    CommissionTimelineEventKind Kind,
    DateTime EventDateUtc,
    DateTime CreatedAtUtc,
    Guid? SaleId,
    decimal Amount);

public static class PosCommissionCalculator
{
    public static decimal GetCommissionPercentForYtd(
        decimal ytdBeforeSale,
        IReadOnlyList<CommissionTierBracket> tiers)
    {
        if (tiers.Count == 0)
            return 0m;

        foreach (var tier in tiers.OrderBy(t => t.MinAmountInclusive))
        {
            var max = tier.MaxAmountInclusive;
            if (ytdBeforeSale >= tier.MinAmountInclusive &&
                (max == null || ytdBeforeSale <= max.Value))
            {
                return tier.CommissionPercent;
            }
        }

        return 0m;
    }

    public static decimal CalculateCommissionForSale(
        decimal ytdBeforeSale,
        decimal saleAmount,
        IReadOnlyList<CommissionTierBracket> tiers)
    {
        var percent = GetCommissionPercentForYtd(ytdBeforeSale, tiers);
        if (percent == 0m)
            return 0m;

        var vatDivisor = 1m + VatConstants.StandardRate;
        var netBase = RoundMoney(saleAmount / vatDivisor);
        var commissionNet = RoundMoney(netBase * percent / 100m);
        return RoundMoney(commissionNet * vatDivisor);
    }

    private static decimal RoundMoney(decimal value) =>
        Math.Round(value, 2, MidpointRounding.AwayFromZero);

    /// <summary>
    /// Walks the UTC calendar-year timeline and returns commission per sale id.
    /// </summary>
    public static IReadOnlyDictionary<Guid, decimal> BuildSaleCommissionMap(
        IReadOnlyList<CommissionTimelineEvent> events,
        IReadOnlyList<CommissionTierBracket> tiers)
    {
        var ordered = events
            .OrderBy(e => e.EventDateUtc)
            .ThenBy(e => e.Kind == CommissionTimelineEventKind.Return ? 0 : 1)
            .ThenBy(e => e.CreatedAtUtc)
            .ThenBy(e => e.SaleId)
            .ToList();

        var ytd = 0m;
        var result = new Dictionary<Guid, decimal>();

        foreach (var evt in ordered)
        {
            if (evt.Kind == CommissionTimelineEventKind.Return)
            {
                ytd -= evt.Amount;
                continue;
            }

            if (evt.Kind == CommissionTimelineEventKind.CoverageRelease)
            {
                ytd += evt.Amount;
                continue;
            }

            if (!evt.SaleId.HasValue)
                continue;

            var commission = CalculateCommissionForSale(ytd, evt.Amount, tiers);
            result[evt.SaleId.Value] = commission;
            ytd += evt.Amount;
        }

        return result;
    }
}
