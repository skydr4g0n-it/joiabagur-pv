using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Services;

namespace JoiabagurPV.Tests.UnitTests.Application;

public class IndexFeedAggregateHashTests
{
    [Fact]
    public void Hash_IsStableRegardlessOfInputOrder()
    {
        var a = Guid.Parse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
        var b = Guid.Parse("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");

        IndexFeedAggregateHash.OfProductIds([b, a])
            .Should().Be(IndexFeedAggregateHash.OfProductIds([a, b]));
    }

    [Fact]
    public void Hash_Is64LowercaseHex()
    {
        var hash = IndexFeedAggregateHash.OfProductIds([Guid.NewGuid()]);
        hash.Should().MatchRegex("^[0-9a-f]{64}$");
    }

    [Fact]
    public void Hash_ChangesWhenAProductLeavesTheSet()
    {
        var a = Guid.NewGuid();
        var b = Guid.NewGuid();

        IndexFeedAggregateHash.OfProductIds([a, b])
            .Should().NotBe(IndexFeedAggregateHash.OfProductIds([a]));
    }

    [Fact]
    public void PosHash_OrdersByPairNotByArrival()
    {
        var posA = Guid.Parse("11111111-1111-1111-1111-111111111111");
        var posB = Guid.Parse("22222222-2222-2222-2222-222222222222");
        var product = Guid.Parse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");

        IndexFeedAggregateHash.OfPosPairs([(posB, product), (posA, product)])
            .Should().Be(IndexFeedAggregateHash.OfPosPairs([(posA, product), (posB, product)]));
    }
}

public class IndexFeedDtoContractTests
{
    [Fact]
    public void CatalogUpsert_HasNoForbiddenProperties()
    {
        var names = typeof(CatalogUpsertItemDto).GetProperties().Select(p => p.Name).ToHashSet();
        names.Should().NotContain("Quantity");
        names.Should().NotContain("DataOrigin");
        names.Should().NotContain("TextProvenance");
        names.Should().NotContain("Source");
        names.Should().NotContain("Confidence");
    }

    [Fact]
    public void PosUpsert_HasNoQuantityProperty()
    {
        var names = typeof(PosAvailabilityUpsertItemDto).GetProperties().Select(p => p.Name);
        names.Should().NotContain("Quantity");
        names.Should().NotContain("quantity");
    }

    [Fact]
    public void PageDto_HasNoQuantityOrProvenance()
    {
        var names = typeof(IndexFeedPageDto).GetProperties().Select(p => p.Name).ToHashSet();
        names.Should().NotContain("Quantity");
        names.Should().NotContain("DataOrigin");
        names.Should().NotContain("TextProvenance");
    }
}
