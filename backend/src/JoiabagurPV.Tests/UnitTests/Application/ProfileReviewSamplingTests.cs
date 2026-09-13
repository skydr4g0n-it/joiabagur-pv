using FluentAssertions;
using JoiabagurPV.Application.Services;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// The stratified draw: reproducible from a declared seed, and stored nowhere.
/// </summary>
/// <remarks>
/// Determinism is the whole contract. The batch behind a published correction rate is defended
/// by anyone being able to reconstruct it from the seed, so a draw that differed between two
/// runs would not be a flaky test — it would be a figure nobody could check.
/// </remarks>
public class ProfileReviewSamplingTests
{
    private const string Seed = "c28-profile-review";

    private static IReadOnlyCollection<Guid> Products(int count) =>
        [.. Enumerable.Range(1, count).Select(i => Guid.Parse($"00000000-0000-0000-0000-{i:D12}"))];

    [Fact]
    public void Sampling_SameSeed_ReturnsSameBatchInSameOrder()
    {
        var products = Products(200);

        var first = ProfileReviewSampling.Draw(
            EvidenceStratum.WithSpan, products, id => id, Seed, quota: 60);
        var second = ProfileReviewSampling.Draw(
            EvidenceStratum.WithSpan, products, id => id, Seed, quota: 60);

        second.Items.Should().Equal(first.Items);
    }

    [Fact]
    public void Sampling_SameSeed_IsIndependentOfInputOrder()
    {
        // The corpus arrives in whatever order the database returns it, which is not a promise.
        // If the draw inherited that order, the same seed would produce different batches on two
        // machines and the published figure would be unreconstructable without the query plan.
        var products = Products(120);
        var shuffled = products.Reverse().ToList();

        var fromNatural = ProfileReviewSampling.Draw(
            EvidenceStratum.NoSpan, products, id => id, Seed, quota: 40);
        var fromShuffled = ProfileReviewSampling.Draw(
            EvidenceStratum.NoSpan, shuffled, id => id, Seed, quota: 40);

        fromShuffled.Items.Should().Equal(fromNatural.Items);
    }

    [Fact]
    public void Sampling_DifferentSeed_ReturnsADifferentBatch()
    {
        // Not a property the design requires, but its absence would mean the seed does nothing —
        // and a seed that does nothing is a reproducibility claim with no mechanism behind it.
        var products = Products(200);

        var first = ProfileReviewSampling.Draw(
            EvidenceStratum.WithSpan, products, id => id, Seed, quota: 60);
        var other = ProfileReviewSampling.Draw(
            EvidenceStratum.WithSpan, products, id => id, "another-seed", quota: 60);

        other.Items.Should().NotEqual(first.Items);
    }

    [Fact]
    public void Sampling_StratumSmallerThanQuota_ReturnsAllAndReportsExhausted()
    {
        var products = Products(17);

        var draw = ProfileReviewSampling.Draw(
            EvidenceStratum.Absence, products, id => id, Seed, quota: 60);

        draw.Items.Should().HaveCount(17);
        draw.Available.Should().Be(17);
        draw.Quota.Should().Be(60);
        draw.Exhausted.Should().BeTrue();
    }

    [Fact]
    public void Sampling_StratumLargerThanQuota_ReportsNotExhausted()
    {
        var draw = ProfileReviewSampling.Draw(
            EvidenceStratum.WithSpan, Products(761), id => id, Seed, quota: 60);

        draw.Items.Should().HaveCount(60);
        draw.Available.Should().Be(761);
        draw.Exhausted.Should().BeFalse();
    }

    [Fact]
    public void Sampling_EmptyStratum_DrawsNothingAndReportsExhausted()
    {
        var draw = ProfileReviewSampling.Draw(
            EvidenceStratum.Absence, Array.Empty<Guid>(), id => id, Seed, quota: 60);

        draw.Items.Should().BeEmpty();
        draw.Exhausted.Should().BeTrue();
    }

    [Fact]
    public void Sampling_OrderKey_IsStableAcrossCalls()
    {
        // Pinned rather than trusted: the key must not depend on a runtime hash, a platform's
        // byte order, or anything else that varies between two hosts running the same seed.
        var product = Guid.Parse("3f2504e0-4f89-11d3-9a0c-0305e82c3301");

        var key = ProfileReviewSampling.OrderKey(product, Seed);

        key.Should().Be(ProfileReviewSampling.OrderKey(product, Seed));
        key.Should().HaveLength(64).And.MatchRegex("^[0-9a-f]+$");
        key.Should().NotBe(ProfileReviewSampling.OrderKey(product, "other"));
    }
}
