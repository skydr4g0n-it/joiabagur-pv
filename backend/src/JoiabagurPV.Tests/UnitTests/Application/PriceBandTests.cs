using FluentAssertions;
using JoiabagurPV.Application.Services;

namespace JoiabagurPV.Tests.UnitTests.Application;

public class PriceBandTests
{
    [Theory]
    [InlineData(29.99, PriceBand.Lt30)]
    [InlineData(30, PriceBand.From30To80)]
    [InlineData(80, PriceBand.From80To150)]
    [InlineData(150, PriceBand.From150To300)]
    [InlineData(300, PriceBand.Gte300)]
    public void PriceBand_Cuts_MatchV1(decimal price, string expected)
    {
        PriceBand.From(price).Should().Be(expected);
        PriceBand.PriceBandVersion.Should().Be("price-band/v1");
    }

    [Fact]
    public void PriceBand_Zero_IsLt30()
    {
        PriceBand.From(0m).Should().Be(PriceBand.Lt30);
    }

    [Fact]
    public void PriceBand_NegativePrice_Throws()
    {
        var act = () => PriceBand.From(-0.01m);
        act.Should().Throw<ArgumentOutOfRangeException>().WithParameterName("price");
    }
}
