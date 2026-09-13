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
/// The review service: the queue that writes nothing, the judgement that carries its time, and
/// the bulk approval that is bounded so the batch keeps its evidence.
/// </summary>
public class ProfileReviewServiceTests
{
    private const string Seed = "c28-profile-review";
    private static readonly Guid ReviewerId = Guid.Parse("aaaaaaaa-0000-0000-0000-000000000001");

    private readonly Mock<IRepository<ProductAiProfile>> _profiles = new();
    private readonly Mock<IRepository<Product>> _products = new();
    private readonly Mock<IUnitOfWork> _unitOfWork = new();

    // ── Fixtures ──────────────────────────────────────────────────────────────────────────
    //
    // Everything below is a fixture. No figure produced by these tests is a measurement of the
    // catalog, and none of them may be read as one: the correction rate and the average review
    // time of this change come from a real session over a real batch, and nowhere else.

    private ProfileReviewService CreateService(
        IEnumerable<ProductAiProfile> profiles,
        IEnumerable<Product> products,
        int quota = 60)
    {
        _profiles.Setup(r => r.GetAll()).Returns(profiles.ToList().BuildMock());
        _products.Setup(r => r.GetAll()).Returns(products.ToList().BuildMock());
        _profiles.Setup(r => r.UpdateAsync(It.IsAny<ProductAiProfile>()))
            .ReturnsAsync((ProductAiProfile p) => p);
        _unitOfWork.Setup(u => u.SaveChangesAsync()).ReturnsAsync(1);

        return new ProfileReviewService(
            _profiles.Object,
            _products.Object,
            _unitOfWork.Object,
            Options.Create(new ProfileReviewOptions { SamplingSeed = Seed, QuotaPerStratum = quota }),
            NullLogger<ProfileReviewService>.Instance);
    }

    private static readonly JsonSerializerOptions CamelCase =
        new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };

    /// <summary>
    /// A profile and its product, in a stratum chosen by the confidences given.
    /// </summary>
    private static (ProductAiProfile Profile, Product Product) APair(
        Guid productId,
        double pieceTypeConfidence = 0.85,
        double materialsConfidence = 0.85,
        double? stoneTypeConfidence = 0.85,
        string? pieceType = "anillo",
        string[]? materials = null,
        string? stoneType = "perla",
        string? sizeLabel = "M",
        string? description = "Anillo de plata con perla.",
        ProfileReviewStatus status = ProfileReviewStatus.Approved,
        ProfileReviewOrigin origin = ProfileReviewOrigin.AutoBulk)
    {
        materials ??= ["plata"];

        var proposal = new AiProposedProfile
        {
            ProductId = productId.ToString(),
            Sku = $"SKU-{productId.ToString()[..4]}",
            PieceType = pieceType is null ? null : Text(pieceType, pieceTypeConfidence),
            Materials = new AiProposedList { Value = [.. materials], Confidence = materialsConfidence },
            StoneType = stoneType is null ? null : Text(stoneType, stoneTypeConfidence ?? 0.20),
            SizeLabel = sizeLabel is null ? null : Text(sizeLabel, 1.0),
            ColorTags = new AiProposedList { Value = ["dorado"], Confidence = 0.85 },
            StyleTags = new AiProposedList { Value = [], Confidence = 0.20 },
            OccasionTags = new AiProposedList { Value = [], Confidence = 0.20 }
        };

        var confidence = new Dictionary<string, double>(StringComparer.Ordinal)
        {
            [ProfileFields.PieceType] = pieceTypeConfidence,
            [ProfileFields.Materials] = materialsConfidence,
            [ProfileFields.ColorTags] = 0.85,
            [ProfileFields.StyleTags] = 0.20,
            [ProfileFields.OccasionTags] = 0.20
        };

        if (stoneTypeConfidence.HasValue)
        {
            confidence[ProfileFields.StoneType] = stoneTypeConfidence.Value;
        }

        if (sizeLabel is not null)
        {
            confidence[ProfileFields.SizeLabel] = 1.0;
        }

        var sources = confidence.Keys.ToDictionary(
            field => field,
            field => field == ProfileFields.SizeLabel
                ? ProfileFieldSources.Rule
                : ProfileFieldSources.Inferred,
            StringComparer.Ordinal);

        var profile = new ProductAiProfile
        {
            Id = Guid.NewGuid(),
            ProductId = productId,
            PieceType = pieceType,
            MaterialsJson = JsonSerializer.Serialize(materials, CamelCase),
            StoneType = stoneType,
            SizeLabel = sizeLabel,
            ColorTagsJson = """["dorado"]""",
            StyleTagsJson = "[]",
            OccasionTagsJson = "[]",
            AiConfidence = 0.8m,
            FieldConfidenceJson = JsonSerializer.Serialize(confidence, CamelCase),
            FieldSourceJson = JsonSerializer.Serialize(sources, CamelCase),
            ProposedProfileJson = JsonSerializer.Serialize(proposal, CamelCase),
            SourceHash = "hash",
            PromptVersion = "enrichment/v1",
            ReviewStatus = status,
            ReviewOrigin = origin
        };

        var product = new Product
        {
            Id = productId,
            SKU = proposal.Sku,
            Name = "Anillo erizo de mar",
            Description = description
        };

        return (profile, product);
    }

    private static AiProposedText Text(string value, double confidence) =>
        new() { Value = value, Confidence = confidence, Source = AiFieldSource.Inferred };

    private static Guid Id(int n) => Guid.Parse($"00000000-0000-0000-0000-{n:D12}");

    /// <summary>A request that confirms everything the proposal said. Tests spoil one field.</summary>
    private static RecordProfileReviewRequest Confirming(
        ProductAiProfile profile,
        int durationMs = 27_400) => new()
    {
        ProductId = profile.ProductId,
        Verdict = "approved",
        ReviewDurationMs = durationMs,
        PieceType = profile.PieceType,
        Materials = [.. ProfileCorrection.ParseList(profile.MaterialsJson)],
        StoneType = profile.StoneType,
        SizeLabel = profile.SizeLabel,
        ColorTags = [.. ProfileCorrection.ParseList(profile.ColorTagsJson)],
        StyleTags = [.. ProfileCorrection.ParseList(profile.StyleTagsJson)],
        OccasionTags = [.. ProfileCorrection.ParseList(profile.OccasionTagsJson)]
    };

    // ── The queue writes nothing ──────────────────────────────────────────────────────────

    [Fact]
    public async Task Sampling_QueueRequest_WritesNoRow()
    {
        var pairs = Enumerable.Range(1, 20).Select(n => APair(Id(n))).ToList();
        var service = CreateService(
            pairs.Select(p => p.Profile), pairs.Select(p => p.Product));

        await service.GetQueueAsync(new ProfileReviewQueueRequest());

        _profiles.Verify(r => r.AddAsync(It.IsAny<ProductAiProfile>()), Times.Never);
        _profiles.Verify(r => r.UpdateAsync(It.IsAny<ProductAiProfile>()), Times.Never);
        _unitOfWork.Verify(u => u.SaveChangesAsync(), Times.Never);
    }

    [Fact]
    public async Task Queue_Request_DoesNotChangeAnyReviewStatus()
    {
        var pairs = Enumerable.Range(1, 20).Select(n => APair(Id(n))).ToList();
        var service = CreateService(
            pairs.Select(p => p.Profile), pairs.Select(p => p.Product));

        var result = await service.GetQueueAsync(new ProfileReviewQueueRequest());

        result.Items.Should().NotBeEmpty();
        pairs.Select(p => p.Profile.ReviewStatus)
            .Should().AllBeEquivalentTo(ProfileReviewStatus.Approved);
        pairs.Select(p => p.Profile.ReviewOrigin)
            .Should().AllBeEquivalentTo(ProfileReviewOrigin.AutoBulk);
    }

    [Fact]
    public async Task Queue_Request_LeavesIndexableCountUnchanged()
    {
        // The indexing feed selects approved profiles. Opening a batch into a pending status
        // would withdraw those documents from the vector index for the length of the session
        // and force them to be re-embedded on re-approval — degrading the corpus the demo runs
        // on, to review it.
        var pairs = Enumerable.Range(1, 30).Select(n => APair(Id(n))).ToList();
        var service = CreateService(
            pairs.Select(p => p.Profile), pairs.Select(p => p.Product));

        var before = pairs.Count(p => p.Profile.ReviewStatus == ProfileReviewStatus.Approved);

        await service.GetQueueAsync(new ProfileReviewQueueRequest());

        pairs.Count(p => p.Profile.ReviewStatus == ProfileReviewStatus.Approved).Should().Be(before);
    }

    [Fact]
    public async Task Queue_Item_CarriesStratumDecidingFieldAndSourceText()
    {
        var pair = APair(Id(1), materialsConfidence: 0.45, description: "Pieza de la colección.");
        var service = CreateService([pair.Profile], [pair.Product]);

        var item = (await service.GetQueueAsync(new ProfileReviewQueueRequest())).Items.Single();

        item.Stratum.Should().Be("B");
        item.StratumDecidingField.Should().Be(ProfileFields.Materials);
        item.Question.Should().Be("¿Es correcto?");
        item.Name.Should().Be("Anillo erizo de mar");
        item.Description.Should().Be("Pieza de la colección.");
        item.HasDescription.Should().BeTrue();
    }

    [Fact]
    public async Task Queue_ProductWithoutDescription_StatesTheAbsence()
    {
        var pair = APair(Id(1), description: null);
        var service = CreateService([pair.Profile], [pair.Product]);

        var item = (await service.GetQueueAsync(new ProfileReviewQueueRequest())).Items.Single();

        item.HasDescription.Should().BeFalse();
        item.Description.Should().BeNull();
    }

    [Fact]
    public async Task Queue_MaximumConfidenceStratum_AsksWhetherAnythingIsMissing()
    {
        // The span check has already answered "is the phrase present?". What a person adds there
        // is catching what is absent, and asking the other question is how the 81 measured
        // omissions get confirmed away.
        var pair = APair(Id(1));
        var service = CreateService([pair.Profile], [pair.Product]);

        var item = (await service.GetQueueAsync(new ProfileReviewQueueRequest())).Items.Single();

        item.Stratum.Should().Be("C");
        item.Question.Should().Be("¿Falta algo?");
    }

    [Fact]
    public async Task Queue_InferredSensitiveFields_AreMarkedPendingAndRuleFieldsAreNot()
    {
        var pair = APair(Id(1));
        var service = CreateService([pair.Profile], [pair.Product]);

        var item = (await service.GetQueueAsync(new ProfileReviewQueueRequest())).Items.Single();

        Pending(item, ProfileFields.PieceType).Should().BeTrue();
        Pending(item, ProfileFields.Materials).Should().BeTrue();
        Pending(item, ProfileFields.StoneType).Should().BeTrue();
        Pending(item, ProfileFields.SizeLabel).Should().BeFalse("came from a deterministic rule");
        Pending(item, ProfileFields.ColorTags).Should().BeFalse("is commercial, not sensitive");

        item.Fields.Should().OnlyContain(field => field.Confidence > 0 && field.Source.Length > 0);

        static bool Pending(ProfileReviewItemDto item, string field) =>
            item.Fields.Single(f => f.Field == field).PendingReview;
    }

    [Fact]
    public async Task Queue_FieldTheExtractorNeverProposed_IsReportedAbsentNotInferred()
    {
        // Not a nicety. Measured on the corpus on 2026-09-13, 613 of the 1.114 queued profiles
        // carry no size label at all, and defaulting those to "inferred" says the model asserted
        // something with no evidence about a field it never spoke to — an accusation against the
        // extractor rather than a description of the data. With the per-field review mark
        // withdrawn, this column and the confidence beside it are the whole signal a reviewer
        // reads, so neither may state something untrue.
        var pair = APair(Id(1), sizeLabel: null);
        var service = CreateService([pair.Profile], [pair.Product]);

        var item = (await service.GetQueueAsync(new ProfileReviewQueueRequest())).Items.Single();

        var size = item.Fields.Single(field => field.Field == ProfileFields.SizeLabel);
        size.Source.Should().Be(ProfileReviewService.AbsentSource);
        size.Source.Should().NotBe(ProfileFieldSources.Inferred);

        // And a field the extractor did speak to keeps saying so.
        item.Fields.Single(field => field.Field == ProfileFields.Materials)
            .Source.Should().Be(ProfileFieldSources.Inferred);
    }

    [Fact]
    public async Task Queue_RejectedProfiles_DoNotAppear()
    {
        var approved = APair(Id(1));
        var rejected = APair(Id(2), status: ProfileReviewStatus.Rejected);
        var service = CreateService(
            [approved.Profile, rejected.Profile], [approved.Product, rejected.Product]);

        var result = await service.GetQueueAsync(new ProfileReviewQueueRequest());

        result.Items.Should().ContainSingle().Which.ProductId.Should().Be(Id(1));
    }

    [Fact]
    public async Task Queue_PageSize_IsCappedAtFifty()
    {
        var pairs = Enumerable.Range(1, 120).Select(n => APair(Id(n))).ToList();
        var service = CreateService(
            pairs.Select(p => p.Profile), pairs.Select(p => p.Product), quota: 200);

        var result = await service.GetQueueAsync(new ProfileReviewQueueRequest { PageSize = 500 });

        result.PageSize.Should().Be(50);
        result.Items.Should().HaveCount(50);
    }

    // ── The judgement ─────────────────────────────────────────────────────────────────────

    [Fact]
    public async Task Review_MaterialAdded_RecordsAdditionDirection()
    {
        var pair = APair(Id(1), materials: ["plata"]);
        var service = CreateService([pair.Profile], [pair.Product]);

        var request = Confirming(pair.Profile);
        request.Materials = ["plata", "oro"];

        var result = await service.RecordReviewAsync(request, ReviewerId);

        Direction(result, ProfileFields.Materials).Should().Be("addition");
    }

    [Fact]
    public async Task Review_UnsupportedStoneCleared_RecordsRemovalDirection()
    {
        var pair = APair(Id(1), stoneType: "esmeralda", stoneTypeConfidence: 0.45);
        var service = CreateService([pair.Profile], [pair.Product]);

        var request = Confirming(pair.Profile);
        request.StoneType = null;

        var result = await service.RecordReviewAsync(request, ReviewerId);

        Direction(result, ProfileFields.StoneType).Should().Be("removal");
        pair.Profile.StoneType.Should().BeNull();
    }

    [Fact]
    public async Task Review_FieldUntouched_RecordsConfirmation()
    {
        // Reported rather than omitted. A field left alone is a judgement a person made, and
        // dropping it from the record would shrink the denominator of the correction rate to the
        // fields somebody happened to change — which always reports a rate of one.
        var pair = APair(Id(1));
        var service = CreateService([pair.Profile], [pair.Product]);

        var result = await service.RecordReviewAsync(Confirming(pair.Profile), ReviewerId);

        result.Directions.Should().HaveCount(7);
        result.Directions.Should().OnlyContain(d => d.Direction == "confirmation");
        result.CorrectedFields.Should().Be(0);
    }

    [Fact]
    public async Task Review_PieceTypeReplaced_RecordsSubstitutionDirection()
    {
        var pair = APair(Id(1), pieceType: "anillo");
        var service = CreateService([pair.Profile], [pair.Product]);

        var request = Confirming(pair.Profile);
        request.PieceType = "colgante";

        var result = await service.RecordReviewAsync(request, ReviewerId);

        Direction(result, ProfileFields.PieceType).Should().Be("substitution");
    }

    [Fact]
    public async Task Review_AnyCorrection_LeavesProposedProfileJsonUnchanged()
    {
        // The correction rate *is* the difference between this column and the values in force.
        // A review that rewrote it would leave the profile agreeing with itself, destroying the
        // metric silently and with no way to recover it from the row.
        var pair = APair(Id(1));
        var before = pair.Profile.ProposedProfileJson;
        var confidenceBefore = pair.Profile.FieldConfidenceJson;
        var sourceBefore = pair.Profile.FieldSourceJson;
        var hashBefore = pair.Profile.SourceHash;

        var service = CreateService([pair.Profile], [pair.Product]);

        var request = Confirming(pair.Profile);
        request.PieceType = "colgante";
        request.Materials = ["oro", "hilo"];
        request.StoneType = null;
        request.SizeLabel = "L";
        request.ColorTags = ["plateado"];

        await service.RecordReviewAsync(request, ReviewerId);

        pair.Profile.ProposedProfileJson.Should().Be(before);
        pair.Profile.FieldConfidenceJson.Should().Be(confidenceBefore);
        pair.Profile.FieldSourceJson.Should().Be(sourceBefore);
        pair.Profile.SourceHash.Should().Be(hashBefore);
    }

    [Fact]
    public async Task Review_Individual_PersistsDurationInSameOperation()
    {
        var pair = APair(Id(1));
        var service = CreateService([pair.Profile], [pair.Product]);

        await service.RecordReviewAsync(Confirming(pair.Profile, durationMs: 31_200), ReviewerId);

        pair.Profile.ReviewDurationMs.Should().Be(31_200);
        pair.Profile.ReviewedAt.Should().NotBeNull();
        // One save, carrying the judgement and its time together: losing the tab cannot leave a
        // recorded judgement whose duration was never written.
        _unitOfWork.Verify(u => u.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task Review_IndividualWithoutDuration_IsRejected()
    {
        var pair = APair(Id(1));
        var service = CreateService([pair.Profile], [pair.Product]);

        var request = Confirming(pair.Profile);
        request.ReviewDurationMs = null;

        var act = async () => await service.RecordReviewAsync(request, ReviewerId);

        await act.Should().ThrowAsync<ArgumentException>();
        pair.Profile.ReviewOrigin.Should().Be(ProfileReviewOrigin.AutoBulk);
        _unitOfWork.Verify(u => u.SaveChangesAsync(), Times.Never);
    }

    [Fact]
    public async Task Review_Reviewer_TakenFromCurrentUserNotFromBody()
    {
        var pair = APair(Id(1));
        var service = CreateService([pair.Profile], [pair.Product]);

        await service.RecordReviewAsync(Confirming(pair.Profile), ReviewerId);

        pair.Profile.ReviewedByUserId.Should().Be(ReviewerId);
        pair.Profile.ReviewOrigin.Should().Be(ProfileReviewOrigin.Human);

        // And the body cannot say otherwise: a request that could name its own reviewer would
        // let the metric be attributed to somebody who reviewed nothing. Pinned on the shape of
        // the request rather than trusted to review.
        typeof(RecordProfileReviewRequest).GetProperties()
            .Select(property => property.Name)
            .Should().NotContain(name =>
                name.Contains("Reviewer", StringComparison.OrdinalIgnoreCase)
                || name.Contains("ReviewedAt", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public async Task Review_Rejected_LeavesStatusRejectedAndOriginHuman()
    {
        var pair = APair(Id(1));
        var service = CreateService([pair.Profile], [pair.Product]);

        var request = Confirming(pair.Profile);
        request.Verdict = "rejected";

        await service.RecordReviewAsync(request, ReviewerId);

        pair.Profile.ReviewStatus.Should().Be(ProfileReviewStatus.Rejected);
        pair.Profile.ReviewOrigin.Should().Be(ProfileReviewOrigin.Human);
    }

    // ── Bulk approval, bounded ────────────────────────────────────────────────────────────

    [Fact]
    public async Task BulkApprove_SelectionSpansStrata_IsRejectedAndModifiesNothing()
    {
        var withSpan = APair(Id(1));
        var noSpan = APair(Id(2), materialsConfidence: 0.45);
        var service = CreateService(
            [withSpan.Profile, noSpan.Profile], [withSpan.Product, noSpan.Product]);

        var act = async () => await service.BulkApproveAsync(
            new BulkApproveProfilesRequest
            {
                Fields = [ProfileFields.ColorTags],
                Stratum = "C",
                ProductIds = [Id(1), Id(2)]
            },
            ReviewerId);

        await act.Should().ThrowAsync<ArgumentException>();
        withSpan.Profile.ReviewOrigin.Should().Be(ProfileReviewOrigin.AutoBulk);
        noSpan.Profile.ReviewOrigin.Should().Be(ProfileReviewOrigin.AutoBulk);
        _unitOfWork.Verify(u => u.SaveChangesAsync(), Times.Never);
    }

    [Fact]
    public async Task BulkApprove_MoreThanOneField_IsRejectedAndModifiesNothing()
    {
        var pair = APair(Id(1));
        var service = CreateService([pair.Profile], [pair.Product]);

        var act = async () => await service.BulkApproveAsync(
            new BulkApproveProfilesRequest
            {
                Fields = [ProfileFields.ColorTags, ProfileFields.StyleTags],
                Stratum = "C",
                ProductIds = [Id(1)]
            },
            ReviewerId);

        await act.Should().ThrowAsync<ArgumentException>();
        pair.Profile.ReviewOrigin.Should().Be(ProfileReviewOrigin.AutoBulk);
        _unitOfWork.Verify(u => u.SaveChangesAsync(), Times.Never);
    }

    [Fact]
    public async Task BulkApprove_Success_LeavesDurationNullAndMarksBulk()
    {
        var pairs = Enumerable.Range(1, 4).Select(n => APair(Id(n))).ToList();
        var service = CreateService(pairs.Select(p => p.Profile), pairs.Select(p => p.Product));

        var result = await service.BulkApproveAsync(
            new BulkApproveProfilesRequest
            {
                Fields = [ProfileFields.ColorTags],
                Stratum = "C",
                ProductIds = [.. pairs.Select(p => p.Profile.ProductId)]
            },
            ReviewerId);

        result.Approved.Should().Be(4);
        result.Field.Should().Be(ProfileFields.ColorTags);

        foreach (var (profile, _) in pairs)
        {
            profile.ReviewOrigin.Should().Be(ProfileReviewOrigin.Human);
            profile.ReviewedByUserId.Should().Be(ReviewerId);
            // Absent by design. A shared timestamp across forty rows would produce an average
            // that flatters the process; a null drops out of it and reports what happened.
            profile.ReviewDurationMs.Should().BeNull();
        }
    }

    [Fact]
    public async Task BulkApprove_UnknownField_IsRejected()
    {
        var pair = APair(Id(1));
        var service = CreateService([pair.Profile], [pair.Product]);

        var act = async () => await service.BulkApproveAsync(
            new BulkApproveProfilesRequest
            {
                Fields = ["inventado"],
                Stratum = "C",
                ProductIds = [Id(1)]
            },
            ReviewerId);

        await act.Should().ThrowAsync<ArgumentException>();
    }

    [Fact]
    public async Task BulkApprove_WithoutDeclaredStratum_IsRejected()
    {
        var pair = APair(Id(1));
        var service = CreateService([pair.Profile], [pair.Product]);

        var act = async () => await service.BulkApproveAsync(
            new BulkApproveProfilesRequest
            {
                Fields = [ProfileFields.ColorTags],
                Stratum = null,
                ProductIds = [Id(1)]
            },
            ReviewerId);

        await act.Should().ThrowAsync<ArgumentException>();
    }

    // ── The rejected, asked the opposite question ─────────────────────────────────────────

    [Fact]
    public async Task RejectedList_DoesNotConsumeStratumQuota()
    {
        // Most of the rejected are correctly rejected non-jewellery and they cluster in the
        // stratum of absence. Letting them draw against its quota would spend the scarcest
        // attention in the batch confirming that a candle is not a piece of jewellery.
        var queued = Enumerable.Range(1, 3)
            .Select(n => APair(Id(n), pieceTypeConfidence: 0.20))
            .ToList();
        var rejected = Enumerable.Range(10, 5)
            .Select(n => APair(Id(n), pieceTypeConfidence: 0.20, status: ProfileReviewStatus.Rejected))
            .ToList();

        var all = queued.Concat(rejected).ToList();
        var service = CreateService(all.Select(p => p.Profile), all.Select(p => p.Product));

        var queue = await service.GetQueueAsync(new ProfileReviewQueueRequest());
        var rejectedList = await service.GetRejectedAsync(1, 50);

        queue.Strata.Single(s => s.Stratum == "A").CorpusSize.Should().Be(3);
        queue.Items.Should().HaveCount(3);
        queue.Items.Select(i => i.ProductId).Should().NotIntersectWith(
            rejectedList.Items.Select(i => i.ProductId));
        rejectedList.TotalCount.Should().Be(5);
        rejectedList.Question.Should().Be("¿Hay algún rechazo incorrecto?");
    }

    [Fact]
    public async Task RejectedProfile_ReturnedToApproved_RecordsReviewerAndInstant()
    {
        var pair = APair(Id(1), status: ProfileReviewStatus.Rejected);
        var service = CreateService([pair.Profile], [pair.Product]);

        var result = await service.RestoreRejectedAsync(
            new RestoreRejectedProfileRequest { ProductId = Id(1) }, ReviewerId);

        result.ReviewStatus.Should().Be(nameof(ProfileReviewStatus.Approved));
        pair.Profile.ReviewStatus.Should().Be(ProfileReviewStatus.Approved);
        pair.Profile.ReviewOrigin.Should().Be(ProfileReviewOrigin.Human);
        pair.Profile.ReviewedByUserId.Should().Be(ReviewerId);
        pair.Profile.ReviewedAt.Should().NotBeNull();
    }

    [Fact]
    public async Task RestoreRejected_ProfileNotRejected_IsRefused()
    {
        var pair = APair(Id(1));
        var service = CreateService([pair.Profile], [pair.Product]);

        var act = async () => await service.RestoreRejectedAsync(
            new RestoreRejectedProfileRequest { ProductId = Id(1) }, ReviewerId);

        await act.Should().ThrowAsync<ArgumentException>();
        _unitOfWork.Verify(u => u.SaveChangesAsync(), Times.Never);
    }

    private static string Direction(RecordProfileReviewResponse response, string field) =>
        response.Directions.Single(direction => direction.Field == field).Direction;
}
