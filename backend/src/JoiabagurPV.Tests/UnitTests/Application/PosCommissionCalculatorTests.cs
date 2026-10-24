using FluentAssertions;
using JoiabagurPV.Application.Commission;

namespace JoiabagurPV.Tests.UnitTests.Application;

public class PosCommissionCalculatorTests
{
    private static readonly IReadOnlyList<CommissionTierBracket> SampleTiers =
    [
        new(0m, 20000m, 20m),
        new(20001m, 100000m, 30m),
        new(100001m, null, 40m)
    ];

    [Fact]
    public void CalculateCommissionForSale_SingleTierSale_ExpectedResult()
    {
        var commission = PosCommissionCalculator.CalculateCommissionForSale(15000m, 10000m, SampleTiers);
        commission.Should().Be(2000m);
    }

    [Fact]
    public void CalculateCommissionForSale_BoundaryCrossSale_ExpectedResult()
    {
        var commission = PosCommissionCalculator.CalculateCommissionForSale(19500m, 10000m, SampleTiers);
        commission.Should().Be(2000m);
    }

    [Fact]
    public void BuildSaleCommissionMap_PartialReturnAdjustingYtd_ExpectedResult()
    {
        var year = 2026;
        var events = new List<CommissionTimelineEvent>
        {
            new(CommissionTimelineEventKind.Sale, new DateTime(year, 3, 1, 12, 0, 0, DateTimeKind.Utc), new DateTime(year, 3, 1, 12, 0, 0, DateTimeKind.Utc), Guid.Parse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"), 18000m),
            new(CommissionTimelineEventKind.Return, new DateTime(year, 3, 15, 12, 0, 0, DateTimeKind.Utc), new DateTime(year, 3, 15, 12, 0, 0, DateTimeKind.Utc), null, 5000m),
            new(CommissionTimelineEventKind.Sale, new DateTime(year, 3, 20, 12, 0, 0, DateTimeKind.Utc), new DateTime(year, 3, 20, 12, 0, 0, DateTimeKind.Utc), Guid.Parse("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"), 10000m),
        };

        var tiers = new List<CommissionTierBracket> { new(0m, 20000m, 20m) };
        var map = PosCommissionCalculator.BuildSaleCommissionMap(events, tiers);

        map[Guid.Parse("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")].Should().Be(2000m);
    }

    [Fact]
    public void BuildSaleCommissionMap_YearReset_ExpectedResult()
    {
        var saleId = Guid.NewGuid();
        var events = new List<CommissionTimelineEvent>
        {
            new(CommissionTimelineEventKind.Sale, new DateTime(2027, 1, 2, 0, 0, 0, DateTimeKind.Utc), new DateTime(2027, 1, 2, 0, 0, 0, DateTimeKind.Utc), saleId, 10000m),
        };

        var map = PosCommissionCalculator.BuildSaleCommissionMap(events, SampleTiers);
        map[saleId].Should().Be(2000m);
    }

    [Fact]
    public void CalculateCommissionForSale_NoTiers_ExpectedResult()
    {
        var commission = PosCommissionCalculator.CalculateCommissionForSale(50000m, 1000m, Array.Empty<CommissionTierBracket>());
        commission.Should().Be(0m);
    }
}
