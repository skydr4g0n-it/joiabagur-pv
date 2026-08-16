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
/// Batch enrichment: what gets sent to the model, what does not, and what is written down.
/// </summary>
public class ProductAiProfileServiceTests
{
    private static readonly Guid AdminId = Guid.NewGuid();

    private readonly Mock<IAiGatewayClient> _gateway = new(MockBehavior.Strict);
    private readonly Mock<IRepository<Product>> _products = new();
    private readonly Mock<IRepository<ProductAiProfile>> _profiles = new();
    private readonly Mock<IUnitOfWork> _unitOfWork = new();
    private readonly List<ProductAiProfile> _saved = [];

    private ProductAiProfileService CreateService(
        IEnumerable<Product> products,
        IEnumerable<ProductAiProfile>? existingProfiles = null)
    {
        _products.Setup(r => r.GetAll()).Returns(products.ToList().BuildMock());
        _profiles.Setup(r => r.GetAll())
            .Returns((existingProfiles ?? []).ToList().BuildMock());

        _profiles.Setup(r => r.AddAsync(It.IsAny<ProductAiProfile>()))
            .Callback<ProductAiProfile>(_saved.Add)
            .ReturnsAsync((ProductAiProfile p) => p);
        _profiles.Setup(r => r.UpdateAsync(It.IsAny<ProductAiProfile>()))
            .Callback<ProductAiProfile>(_saved.Add)
            .ReturnsAsync((ProductAiProfile p) => p);

        _unitOfWork.Setup(u => u.SaveChangesAsync()).ReturnsAsync(1);

        var policy = new ProfileReviewPolicy(Options.Create(new ProfileReviewOptions
        {
            TagAutoApproveThreshold = 0.80,
            MinimumFieldConfidence = 0.50
        }));

        return new ProductAiProfileService(
            _gateway.Object,
            policy,
            _products.Object,
            _profiles.Object,
            _unitOfWork.Object,
            NullLogger<ProductAiProfileService>.Instance);
    }

    private static Product AProduct(Guid? id = null) => new()
    {
        Id = id ?? Guid.NewGuid(),
        SKU = "ERIZO-M",
        Name = "Anillo erizo de mar talla M",
        Description = "Pieza en plata con baño de oro."
    };

    /// <summary>A proposal with one inferred sensitive field, so routing sends it to review.</summary>
    private static AiProposedProfile AProposal(Guid productId) => new()
    {
        ProductId = productId.ToString(),
        Sku = "ERIZO-M",
        PieceType = new AiProposedText { Value = "anillo", Confidence = 0.88, Source = AiFieldSource.Inferred },
        Materials = new AiProposedList
        {
            Value = ["plata", "baño de oro"],
            Confidence = 0.72,
            Source = AiFieldSource.Inferred
        },
        SizeLabel = new AiProposedText { Value = "M", Confidence = 1.0, Source = AiFieldSource.Rule },
        ColorTags = new AiProposedList { Value = ["dorado"], Confidence = 0.92, Source = AiFieldSource.Inferred },
        StyleTags = new AiProposedList { Value = ["marino"], Confidence = 0.91, Source = AiFieldSource.Inferred },
        OccasionTags = new AiProposedList { Value = ["regalo"], Confidence = 0.90, Source = AiFieldSource.Inferred }
    };

    private void SetupGateway(params AiProposedProfile[] profiles) =>
        _gateway
            .Setup(g => g.EnrichAsync(
                It.IsAny<AiEnrichRequest>(), It.IsAny<AiCallScope>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new AiEnrichResponse
            {
                Profiles = [.. profiles],
                PromptVersion = "v1",
                Usage = new AiUsage { TotalTokens = 160, Model = "test-model" },
                TraceId = "trace-test"
            });

    [Fact]
    public async Task EnrichBatch_WithInferredSensitiveField_PersistsPendingProfile()
    {
        var product = AProduct();
        SetupGateway(AProposal(product.Id));
        var service = CreateService([product]);

        var response = await service.EnrichBatchAsync(
            new EnrichBatchRequest { ProductIds = [product.Id] }, AdminId, "Administrator");

        response.Enriched.Should().Be(1);
        response.SkippedUnchanged.Should().Be(0);

        var profile = _saved.Single();
        profile.ReviewStatus.Should().Be(ProfileReviewStatus.Pending);
        profile.ReviewOrigin.Should().Be(ProfileReviewOrigin.AutoBulk);
        profile.PromptVersion.Should().Be("v1");
        profile.GeneratedByModel.Should().Be("test-model");

        response.Profiles.Single().FieldsPendingReview.Should().Contain("piece_type");
    }

    [Fact]
    public async Task Profile_StoresMultipleMaterials()
    {
        var product = AProduct();
        SetupGateway(AProposal(product.Id));
        var service = CreateService([product]);

        await service.EnrichBatchAsync(
            new EnrichBatchRequest { ProductIds = [product.Id] }, AdminId, "Administrator");

        var materials = JsonSerializer.Deserialize<List<string>>(_saved.Single().MaterialsJson);

        materials.Should().Equal(["plata", "baño de oro"],
            "a piece is routinely silver and gold-plated at once, and the retrieval filter is an "
            + "overlap test over a list, not an equality on a single value");
    }

    [Fact]
    public async Task EnrichBatch_WithNoMaterialEvidence_StoresEmptyListNotNull()
    {
        var product = AProduct();
        var proposal = AProposal(product.Id);
        proposal.Materials = new AiProposedList { Value = [], Confidence = 0.2, Source = AiFieldSource.Inferred };
        SetupGateway(proposal);
        var service = CreateService([product]);

        await service.EnrichBatchAsync(
            new EnrichBatchRequest { ProductIds = [product.Id] }, AdminId, "Administrator");

        _saved.Single().MaterialsJson.Should().Be("[]",
            "an absence of evidence must not become a default material that reads like a finding");
    }

    /// <summary>
    /// The skip that makes repeating a batch both cheap and safe.
    /// </summary>
    [Fact]
    public async Task EnrichBatch_WhenSourceHashUnchanged_SkipsProductWithoutCallingGateway()
    {
        var product = AProduct();
        var existing = new ProductAiProfile
        {
            ProductId = product.Id,
            MaterialsJson = "[]",
            ColorTagsJson = "[]",
            StyleTagsJson = "[]",
            OccasionTagsJson = "[]",
            FieldConfidenceJson = "{}",
            FieldSourceJson = "{}",
            ProposedProfileJson = "{}",
            SourceHash = ProductEnrichmentSourceHash.Compute(product, null),
            ReviewStatus = ProfileReviewStatus.Approved,
            ReviewOrigin = ProfileReviewOrigin.Human,
            ReviewedByUserId = Guid.NewGuid(),
            ReviewedAt = DateTime.UtcNow
        };

        var service = CreateService([product], [existing]);

        var response = await service.EnrichBatchAsync(
            new EnrichBatchRequest { ProductIds = [product.Id] }, AdminId, "Administrator");

        response.SkippedUnchanged.Should().Be(1);
        response.Enriched.Should().Be(0);

        // The strict mock makes this an assertion rather than a hope: an unexpected call throws.
        _gateway.Verify(
            g => g.EnrichAsync(It.IsAny<AiEnrichRequest>(), It.IsAny<AiCallScope>(), It.IsAny<CancellationToken>()),
            Times.Never);

        existing.ReviewOrigin.Should().Be(ProfileReviewOrigin.Human,
            "a profile a person reviewed must survive a repeated batch untouched");
        _saved.Should().BeEmpty();
    }

    [Fact]
    public async Task EnrichBatch_WithForce_ReEnrichesEvenWhenHashMatches()
    {
        var product = AProduct();
        var existing = new ProductAiProfile
        {
            ProductId = product.Id,
            MaterialsJson = "[]",
            ColorTagsJson = "[]",
            StyleTagsJson = "[]",
            OccasionTagsJson = "[]",
            FieldConfidenceJson = "{}",
            FieldSourceJson = "{}",
            ProposedProfileJson = "{}",
            SourceHash = ProductEnrichmentSourceHash.Compute(product, null)
        };
        SetupGateway(AProposal(product.Id));
        var service = CreateService([product], [existing]);

        var response = await service.EnrichBatchAsync(
            new EnrichBatchRequest { ProductIds = [product.Id], Force = true }, AdminId, "Administrator");

        response.Enriched.Should().Be(1);
        response.SkippedUnchanged.Should().Be(0);
    }

    [Fact]
    public async Task EnrichBatch_WhenInputsChanged_ResetsPreviousHumanReview()
    {
        var product = AProduct();
        var existing = new ProductAiProfile
        {
            ProductId = product.Id,
            MaterialsJson = "[]",
            ColorTagsJson = "[]",
            StyleTagsJson = "[]",
            OccasionTagsJson = "[]",
            FieldConfidenceJson = "{}",
            FieldSourceJson = "{}",
            ProposedProfileJson = "{}",
            SourceHash = "a-hash-of-some-older-text",
            ReviewStatus = ProfileReviewStatus.Approved,
            ReviewOrigin = ProfileReviewOrigin.Human,
            ReviewedByUserId = Guid.NewGuid(),
            ReviewedAt = DateTime.UtcNow,
            ReviewDurationMs = 4200
        };
        SetupGateway(AProposal(product.Id));
        var service = CreateService([product], [existing]);

        await service.EnrichBatchAsync(
            new EnrichBatchRequest { ProductIds = [product.Id] }, AdminId, "Administrator");

        var profile = _saved.Single();
        profile.ReviewOrigin.Should().Be(ProfileReviewOrigin.AutoBulk);
        profile.ReviewedByUserId.Should().BeNull(
            "the text this profile describes is not the text the previous reviewer read; keeping "
            + "their name would claim they checked content they never saw");
        profile.ReviewedAt.Should().BeNull();
        profile.ReviewDurationMs.Should().BeNull();
    }

    /// <summary>
    /// The declared shortcut of the design, and the property that keeps it honest.
    /// </summary>
    [Fact]
    public async Task EnrichBatch_WithAutoBulkMode_ApprovesButRecordsWhatRoutingWouldHaveSaid()
    {
        var product = AProduct();
        SetupGateway(AProposal(product.Id));
        var service = CreateService([product]);

        var response = await service.EnrichBatchAsync(
            new EnrichBatchRequest { ProductIds = [product.Id], ReviewMode = ProfileReviewMode.AutoBulk },
            AdminId,
            "Administrator");

        var profile = _saved.Single();

        profile.ReviewStatus.Should().Be(ProfileReviewStatus.Approved,
            "the corpus has to be indexable; only what is approved reaches the feed");
        profile.ReviewOrigin.Should().Be(ProfileReviewOrigin.AutoBulk,
            "and it has to stay distinguishable from what a person actually approved");

        var sources = JsonSerializer.Deserialize<Dictionary<string, string>>(profile.FieldSourceJson)!;
        sources["piece_type"].Should().Be("inferred",
            "the shortcut is declared, not hidden: afterwards it must still be answerable how "
            + "much of the corpus nobody looked at, and which fields would have needed it");

        // The routing outcome is still reported to the caller, even though it was overridden.
        response.Profiles.Single().FieldsPendingReview.Should().Contain("piece_type");
    }

    [Fact]
    public async Task EnrichBatch_PreservesTheRawProposalSeparatelyFromTheValuesInForce()
    {
        var product = AProduct();
        SetupGateway(AProposal(product.Id));
        var service = CreateService([product]);

        await service.EnrichBatchAsync(
            new EnrichBatchRequest { ProductIds = [product.Id] }, AdminId, "Administrator");

        var proposed = JsonSerializer.Deserialize<JsonElement>(_saved.Single().ProposedProfileJson);

        proposed.GetProperty("pieceType").GetProperty("value").GetString().Should().Be("anillo",
            "the correction rate of the extractor is the difference between this and the values "
            + "in force; without it the metric cannot be computed at all");
    }

    [Fact]
    public async Task EnrichBatch_UsesACatalogScope()
    {
        var product = AProduct();
        SetupGateway(AProposal(product.Id));
        var service = CreateService([product]);
        AiCallScope? captured = null;

        _gateway
            .Setup(g => g.EnrichAsync(
                It.IsAny<AiEnrichRequest>(), It.IsAny<AiCallScope>(), It.IsAny<CancellationToken>()))
            .Callback<AiEnrichRequest, AiCallScope, CancellationToken>((_, scope, _) => captured = scope)
            .ReturnsAsync(new AiEnrichResponse
            {
                Profiles = [AProposal(product.Id)],
                PromptVersion = "v1",
                Usage = new AiUsage()
            });

        await service.EnrichBatchAsync(
            new EnrichBatchRequest { ProductIds = [product.Id] }, AdminId, "Administrator");

        captured!.Kind.Should().Be(AiCallScopeKind.Catalog);
        captured.PointOfSaleId.Should().BeNull();
    }

    [Fact]
    public async Task EnrichBatch_WhenServiceReturnsNoProposalForAProduct_CountsItFailedWithoutLosingTheRest()
    {
        var withProposal = AProduct();
        var without = AProduct();
        SetupGateway(AProposal(withProposal.Id));
        var service = CreateService([withProposal, without]);

        var response = await service.EnrichBatchAsync(
            new EnrichBatchRequest { ProductIds = [withProposal.Id, without.Id] },
            AdminId,
            "Administrator");

        response.Enriched.Should().Be(1);
        response.Failed.Should().Be(1,
            "one product the extractor could not answer for must not discard the work already "
            + "done for the others");
        _saved.Should().HaveCount(1);
    }
}

/// <summary>
/// The hash that decides whether a batch has to pay for a model call again.
/// </summary>
public class ProductEnrichmentSourceHashTests
{
    private static Product AProduct() => new()
    {
        Id = Guid.NewGuid(),
        SKU = "ERIZO-M",
        Name = "Anillo erizo",
        Description = "Plata con baño de oro."
    };

    [Fact]
    public void Compute_ForTheSameInputs_IsStable()
    {
        var product = AProduct();

        ProductEnrichmentSourceHash.Compute(product, "Verano")
            .Should().Be(ProductEnrichmentSourceHash.Compute(product, "Verano"));
    }

    [Theory]
    [InlineData("sku")]
    [InlineData("name")]
    [InlineData("description")]
    [InlineData("collection")]
    public void Compute_WhenAnyInputChanges_ChangesTheDigest(string field)
    {
        var product = AProduct();
        var before = ProductEnrichmentSourceHash.Compute(product, "Verano");
        var collection = "Verano";

        switch (field)
        {
            case "sku": product.SKU = "ERIZO-L"; break;
            case "name": product.Name = "Anillo erizo grande"; break;
            case "description": product.Description = "Otra cosa."; break;
            case "collection": collection = "Invierno"; break;
        }

        ProductEnrichmentSourceHash.Compute(product, collection).Should().NotBe(before);
    }

    /// <summary>
    /// Moving text across a field boundary must not produce the same digest, or a rename that
    /// only shifts words would look like no change at all.
    /// </summary>
    [Fact]
    public void Compute_DistinguishesTextMovedBetweenFields()
    {
        var first = AProduct();
        first.Name = "Anillo";
        first.Description = "erizo";

        var second = new Product { Id = first.Id, SKU = first.SKU, Name = "Anilloerizo", Description = "" };

        ProductEnrichmentSourceHash.Compute(first, null)
            .Should().NotBe(ProductEnrichmentSourceHash.Compute(second, null));
    }

    [Fact]
    public void Compute_ProducesAHexadecimalSha256()
    {
        var digest = ProductEnrichmentSourceHash.Compute(AProduct(), null);

        digest.Should().HaveLength(64).And.MatchRegex("^[0-9a-f]{64}$");
    }
}
