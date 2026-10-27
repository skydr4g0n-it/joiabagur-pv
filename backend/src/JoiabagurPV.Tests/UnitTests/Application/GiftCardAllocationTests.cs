using FluentAssertions;
using JoiabagurPV.Application.GiftCards;

namespace JoiabagurPV.Tests.UnitTests.Application;

public class GiftCardAllocationTests
{
    [Fact]
    public void Allocate_CheapestLineFirst_Example150And50()
    {
        var lines = new[]
        {
            new GiftCardAllocationLineState(0, 150m, 150m),
            new GiftCardAllocationLineState(1, 50m, 50m),
        };

        var (applies, _) = GiftCardAllocation.Allocate(lines, new[] { ("GC-1", 100m) });

        applies.Should().Contain(a => a.LineIndex == 1 && a.Amount == 50m);
        applies.Should().Contain(a => a.LineIndex == 0 && a.Amount == 50m);
        applies.Sum(a => a.Amount).Should().Be(100m);
    }
}
