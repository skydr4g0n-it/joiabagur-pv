using System.Text.Json;
using FluentAssertions;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using MockQueryable;
using Moq;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// The figures the delivery cites: correction rate per field, stratum and direction, and the two
/// time populations kept apart.
/// </summary>
/// <remarks>
/// <strong>Every number in this file is a fixture.</strong> None of them is a measurement of the
/// catalog and none may be read as one. The correction rate and the average review time this
/// change delivers come from a real review session over a real batch, and from nowhere else —
/// fabricating either of them here would falsify the result of the project rather than shorten
/// the work.
/// </remarks>
public class ProfileReviewMetricsTests
{
    private const string Seed = "c28-profile-review";
    private static readonly Guid ReviewerId = Guid.Parse("aaaaaaaa-0000-0000-0000-000000000001");

    private static readonly JsonSerializerOptions CamelCase =
        new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };

    private readonly Mock<IRepository<ProductAiProfile>> _profiles = new();
    private readonly Mock<IRepository<Product>> _products = new();
    private readonly Mock<IUnitOfWork> _unitOfWork = new();

    private ProfileReviewService CreateService(IEnumerable<ProductAiProfile> profiles)
    {
        var list = profiles.ToList();
        _profiles.Setup(r => r.GetAll()).Returns(list.BuildMock());
        _products.Setup(r => r.GetAll()).Returns(new List<Product>().BuildMock());
        _unitOfWork.Setup(u => u.SaveChangesAsync()).ReturnsAsync(1);

        return new ProfileReviewService(
            _profiles.Object,
            _products.Object,
            _unitOfWork.Object,
            Options.Create(new ProfileReviewOptions { SamplingSeed = Seed, QuotaPerStratum = 60 }),
            NullLogger<ProfileReviewService>.Instance);
    }

    private static Guid Id(int n) => Guid.Parse($"00000000-0000-0000-0000-{n:D12}");

    /// <summary>
    /// A profile whose proposal and values in force can be set apart, so a direction is forced.
    /// </summary>
    private static ProductAiProfile AProfile(
        int n,
        EvidenceStratum stratum,
        string? proposedPieceType = "anillo",
        string? pieceTypeInForce = "anillo",
        string[]? proposedMaterials = null,
        string[]? materialsInForce = null,
        string? proposedStone = null,
        string? stoneInForce = null,
        ProfileReviewOrigin origin = ProfileReviewOrigin.AutoBulk,
        int? durationMs = null,
        ProfileReviewStatus status = ProfileReviewStatus.Approved)
    {
        proposedMaterials ??= ["plata"];
        materialsInForce ??= proposedMaterials;

        // The confidences are chosen only to land the profile in the stratum the test wants.
        var (piece, materials, stone) = stratum switch
        {
            EvidenceStratum.Absence => (0.20, 0.85, (double?)null),
            EvidenceStratum.NoSpan => (0.85, 0.45, (double?)null),
            _ => (0.85, 0.85, (double?)null)
        };

        var proposal = new AiProposedProfile
        {
            ProductId = Id(n).ToString(),
            Sku = $"SKU-{n}",
            PieceType = proposedPieceType is null ? null : Text(proposedPieceType, piece),
            Materials = new AiProposedList { Value = [.. proposedMaterials], Confidence = materials },
            StoneType = proposedStone is null ? null : Text(proposedStone, 0.45),
            SizeLabel = Text("M", 1.0),
            ColorTags = new AiProposedList { Value = [], Confidence = 0.20 },
            StyleTags = new AiProposedList { Value = [], Confidence = 0.20 },
            OccasionTags = new AiProposedList { Value = [], Confidence = 0.20 }
        };

        var confidence = new Dictionary<string, double>(StringComparer.Ordinal)
        {
            [ProfileFields.PieceType] = piece,
            [ProfileFields.Materials] = materials,
            [ProfileFields.SizeLabel] = 1.0,
            [ProfileFields.ColorTags] = 0.20,
            [ProfileFields.StyleTags] = 0.20,
            [ProfileFields.OccasionTags] = 0.20
        };

        if (stone.HasValue)
        {
            confidence[ProfileFields.StoneType] = stone.Value;
        }

        return new ProductAiProfile
        {
            Id = Guid.NewGuid(),
            ProductId = Id(n),
            PieceType = pieceTypeInForce,
            MaterialsJson = JsonSerializer.Serialize(materialsInForce, CamelCase),
            StoneType = stoneInForce,
            SizeLabel = "M",
            ColorTagsJson = "[]",
            StyleTagsJson = "[]",
            OccasionTagsJson = "[]",
            AiConfidence = 0.8m,
            FieldConfidenceJson = JsonSerializer.Serialize(confidence, CamelCase),
            FieldSourceJson = "{}",
            ProposedProfileJson = JsonSerializer.Serialize(proposal, CamelCase),
            SourceHash = "hash",
            PromptVersion = "enrichment/v1",
            ReviewStatus = status,
            ReviewOrigin = origin,
            ReviewedByUserId = origin == ProfileReviewOrigin.Human ? ReviewerId : null,
            ReviewedAt = origin == ProfileReviewOrigin.Human ? DateTime.UtcNow : null,
            ReviewDurationMs = durationMs
        };
    }

    private static AiProposedText Text(string value, double confidence) =>
        new() { Value = value, Confidence = confidence, Source = AiFieldSource.Inferred };

    // ── The rate ──────────────────────────────────────────────────────────────────────────

    [Fact]
    public async Task Metrics_CorrectionRate_ComputedPerField()
    {
        var profiles = new[]
        {
            // One material added; everything else left as proposed.
            AProfile(1, EvidenceStratum.WithSpan,
                proposedMaterials: ["plata"], materialsInForce: ["plata", "oro"],
                origin: ProfileReviewOrigin.Human, durationMs: 30_000),
            AProfile(2, EvidenceStratum.WithSpan,
                origin: ProfileReviewOrigin.Human, durationMs: 20_000)
        };

        var metrics = await CreateService(profiles).GetMetricsAsync();

        var materials = metrics.Fields.Single(field => field.Field == ProfileFields.Materials);
        materials.Reviewed.Should().Be(2);
        materials.Corrected.Should().Be(1);
        materials.SampleCorrectionRate.Should().Be(50.0);

        var pieceType = metrics.Fields.Single(field => field.Field == ProfileFields.PieceType);
        pieceType.Corrected.Should().Be(0);
        pieceType.SampleCorrectionRate.Should().Be(0.0);

        // Every reviewed field is reported, not only the ones somebody moved.
        metrics.Fields.Select(field => field.Field)
            .Should().BeEquivalentTo(ProfileCorrection.ReviewedFields);
    }

    [Fact]
    public async Task Metrics_CorrectionRate_SplitByStratumAndDirection()
    {
        var profiles = new[]
        {
            // Stratum B: a stone the text does not name, taken away. A removal.
            AProfile(1, EvidenceStratum.NoSpan,
                proposedStone: "esmeralda", stoneInForce: null,
                origin: ProfileReviewOrigin.Human, durationMs: 25_000),
            // Stratum C: a material the extractor missed, supplied. An addition.
            AProfile(2, EvidenceStratum.WithSpan,
                proposedMaterials: ["plata"], materialsInForce: ["plata", "hilo"],
                origin: ProfileReviewOrigin.Human, durationMs: 25_000)
        };

        var metrics = await CreateService(profiles).GetMetricsAsync();

        var stoneInB = metrics.Fields
            .Single(field => field.Field == ProfileFields.StoneType)
            .ByStratum.Single(stratum => stratum.Stratum == "B");
        stoneInB.Removals.Should().Be(1);
        stoneInB.Additions.Should().Be(0);

        var materialsInC = metrics.Fields
            .Single(field => field.Field == ProfileFields.Materials)
            .ByStratum.Single(stratum => stratum.Stratum == "C");
        materialsInC.Additions.Should().Be(1);
        materialsInC.Removals.Should().Be(0);

        metrics.Strata.Single(stratum => stratum.Stratum == "B").Removals.Should().Be(1);
        metrics.Strata.Single(stratum => stratum.Stratum == "C").Additions.Should().Be(1);
    }

    [Fact]
    public async Task Metrics_Total_WeightedByCorpusStratumSize_NotBySampleSize()
    {
        // Two strata sampled at the same rate out of very different populations: one profile
        // reviewed in each, corrected in B and clean in C, with B holding 2 of the corpus and
        // C holding 8. An unweighted total would report 50 %; weighting by the catalog reports
        // 20 %, because the stratum that was corrected is the small one.
        var profiles = new List<ProductAiProfile>
        {
            AProfile(1, EvidenceStratum.NoSpan,
                proposedStone: "esmeralda", stoneInForce: null,
                origin: ProfileReviewOrigin.Human, durationMs: 10_000),
            AProfile(2, EvidenceStratum.NoSpan),
            AProfile(3, EvidenceStratum.WithSpan,
                origin: ProfileReviewOrigin.Human, durationMs: 10_000)
        };
        profiles.AddRange(Enumerable.Range(4, 7).Select(n => AProfile(n, EvidenceStratum.WithSpan)));

        var metrics = await CreateService(profiles).GetMetricsAsync();

        metrics.Strata.Single(stratum => stratum.Stratum == "B").CorpusSize.Should().Be(2);
        metrics.Strata.Single(stratum => stratum.Stratum == "C").CorpusSize.Should().Be(8);

        var rateB = metrics.Strata.Single(stratum => stratum.Stratum == "B").CorrectionRate!.Value;
        var rateC = metrics.Strata.Single(stratum => stratum.Stratum == "C").CorrectionRate!.Value;

        var weighted = Math.Round(((rateB * 2) + (rateC * 8)) / 10d, 1);
        metrics.WeightedCorrectionRate.Should().Be(weighted);

        // And it is genuinely different from the figure the sample alone would report.
        metrics.WeightedCorrectionRate.Should().NotBe(metrics.SampleCorrectionRate);
    }

    [Fact]
    public async Task Metrics_StratumNobodyReviewed_IsLeftOutOfTheWeightingNotCountedAsZero()
    {
        // A stratum nobody looked at reports nothing about the catalog. Counting it as zero
        // would publish a catalog cleaner than anything that was actually reviewed.
        var profiles = new List<ProductAiProfile>
        {
            AProfile(1, EvidenceStratum.WithSpan,
                proposedMaterials: ["plata"], materialsInForce: ["plata", "oro"],
                origin: ProfileReviewOrigin.Human, durationMs: 10_000)
        };
        profiles.AddRange(Enumerable.Range(2, 50).Select(n => AProfile(n, EvidenceStratum.Absence)));

        var metrics = await CreateService(profiles).GetMetricsAsync();

        metrics.Strata.Single(stratum => stratum.Stratum == "A").CorrectionRate.Should().BeNull();
        metrics.WeightedCorrectionRate.Should().Be(
            metrics.Strata.Single(stratum => stratum.Stratum == "C").CorrectionRate);
    }

    // ── The population ────────────────────────────────────────────────────────────────────

    [Fact]
    public async Task Metrics_ExcludesAutoBulkProfiles()
    {
        // A profile nobody looked at agrees with its own proposal by construction. Counting it
        // would drive the published rate towards zero in proportion to how little of the catalog
        // was reviewed — reporting the size of the review as the quality of the extractor.
        var profiles = new List<ProductAiProfile>
        {
            AProfile(1, EvidenceStratum.WithSpan,
                proposedMaterials: ["plata"], materialsInForce: ["plata", "oro"],
                origin: ProfileReviewOrigin.Human, durationMs: 30_000)
        };
        profiles.AddRange(Enumerable.Range(2, 99).Select(n => AProfile(n, EvidenceStratum.WithSpan)));

        var metrics = await CreateService(profiles).GetMetricsAsync();

        metrics.ProfilesTotal.Should().Be(100);
        metrics.ProfilesReviewedByHuman.Should().Be(1);
        metrics.ProfilesAutoBulk.Should().Be(99);

        // Seven fields from the single reviewed profile, and nothing from the other ninety-nine.
        metrics.FieldsReviewed.Should().Be(7);
        metrics.FieldsCorrected.Should().Be(1);
        metrics.Fields.Single(field => field.Field == ProfileFields.Materials)
            .SampleCorrectionRate.Should().Be(100.0);
    }

    [Fact]
    public async Task Metrics_ReportsProfileCountPerReviewOrigin()
    {
        var profiles = new List<ProductAiProfile>
        {
            AProfile(1, EvidenceStratum.WithSpan, origin: ProfileReviewOrigin.Human, durationMs: 1_000),
            AProfile(2, EvidenceStratum.WithSpan, origin: ProfileReviewOrigin.Human),
            AProfile(3, EvidenceStratum.WithSpan),
            AProfile(4, EvidenceStratum.WithSpan)
        };

        var metrics = await CreateService(profiles).GetMetricsAsync();

        metrics.ProfilesReviewedByHuman.Should().Be(2);
        metrics.ProfilesAutoBulk.Should().Be(2);
        metrics.ReviewedShare.Should().Be(50.0);
        metrics.ProfilesByPromptVersion.Should().ContainKey("enrichment/v1")
            .WhoseValue.Should().Be(4);
    }

    // ── The two time populations ──────────────────────────────────────────────────────────

    [Fact]
    public async Task Metrics_NoTimedReviews_AverageIsNullNotZero()
    {
        // Zero asserts an instantaneous review, which is a claim. An absence reports that
        // nothing was measured, which is the truth — and it is the truth the previous review
        // capability had to report for sixty-four judgements and six timings.
        var profiles = new[]
        {
            AProfile(1, EvidenceStratum.WithSpan, origin: ProfileReviewOrigin.Human),
            AProfile(2, EvidenceStratum.WithSpan, origin: ProfileReviewOrigin.Human)
        };

        var metrics = await CreateService(profiles).GetMetricsAsync();

        metrics.AverageReviewSeconds.Should().BeNull();
        metrics.MinReviewSeconds.Should().BeNull();
        metrics.MaxReviewSeconds.Should().BeNull();
        metrics.TimedReviews.Should().Be(0);
    }

    [Fact]
    public async Task Metrics_TimedAndBulkPopulations_CountedApart()
    {
        var profiles = new[]
        {
            AProfile(1, EvidenceStratum.WithSpan, origin: ProfileReviewOrigin.Human, durationMs: 20_000),
            AProfile(2, EvidenceStratum.WithSpan, origin: ProfileReviewOrigin.Human, durationMs: 40_000),
            AProfile(3, EvidenceStratum.WithSpan, origin: ProfileReviewOrigin.Human),
            AProfile(4, EvidenceStratum.WithSpan, origin: ProfileReviewOrigin.Human),
            AProfile(5, EvidenceStratum.WithSpan, origin: ProfileReviewOrigin.Human)
        };

        var metrics = await CreateService(profiles).GetMetricsAsync();

        metrics.TimedReviews.Should().Be(2);
        metrics.BulkApprovedReviews.Should().Be(3);
        // Averaged over the timed population only. Mixing in a population that cannot be timed
        // produces a figure that describes neither.
        metrics.AverageReviewSeconds.Should().Be(30.0);
        metrics.MinReviewSeconds.Should().Be(20.0);
        metrics.MaxReviewSeconds.Should().Be(40.0);
    }

    [Fact]
    public async Task Metrics_BulkRejectedProfiles_DoNotWeightTheCorpus()
    {
        // The profiles the bulk pass rejected are gift-shop articles with no piece type in the
        // closed vocabulary. They are not part of the population the batch is drawn from, so
        // they must not lend weight to the stratum they cluster in.
        var profiles = new List<ProductAiProfile>
        {
            AProfile(1, EvidenceStratum.Absence)
        };
        profiles.AddRange(Enumerable.Range(2, 9).Select(n =>
            AProfile(n, EvidenceStratum.Absence, status: ProfileReviewStatus.Rejected)));

        var metrics = await CreateService(profiles).GetMetricsAsync();

        metrics.Strata.Single(stratum => stratum.Stratum == "A").CorpusSize.Should().Be(1);
    }
}
