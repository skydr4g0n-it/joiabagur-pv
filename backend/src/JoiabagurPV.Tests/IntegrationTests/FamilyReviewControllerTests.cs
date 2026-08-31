using System.Net;
using System.Net.Http.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.DTOs.Products;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for the family review flow: jbg-ai measures, this side remembers.
/// </summary>
/// <remarks>
/// <para>
/// Two tests here carry most of the weight, and both would pass against an implementation that is
/// quietly wrong. <see cref="DeleteFamily_StampsDepartingProducts"/> is the only one that notices
/// a dissolution the vector index will never hear about; and
/// <see cref="MoveProductBetweenFamilies_ReordersAndSwapsLabels_WithoutPhantomUpdate"/> exercises
/// the one shape C07's apply recorded as a trap — a single request that deletes and inserts
/// membership rows at once.
/// </para>
/// <para>
/// The audit itself is stubbed at the gateway. What is under test on this side is the plumbing
/// around it: that auditing writes nothing, that judgements are remembered and sent back, and
/// that a failure is never dressed up as an empty result.
/// </para>
/// </remarks>
[Collection(IntegrationTestCollection.Name)]
public class FamilyReviewControllerTests : IAsyncLifetime
{
    private const string AuditEndpoint = "/api/ai/catalog/family-audit";
    private const string VerdictsEndpoint = "/api/ai/catalog/family-verdicts";
    private const string FamiliesEndpoint = "/api/product-families";

    private readonly ApiWebApplicationFactory _factory;

    private PointOfSale _pos = null!;
    private Product _small = null!;
    private Product _medium = null!;
    private Product _large = null!;
    private Product _orphan = null!;

    public FamilyReviewControllerTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
    }

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();

        using var mother = new TestDataMother(_factory.Services);

        _pos = await mother.PointOfSale()
            .WithCode("REVIEW-POS")
            .WithName("Review Point of Sale")
            .WithAddress("Test Address")
            // Pinned: Bogus generates phone numbers of varying length against a varchar(20).
            .WithPhone("600123456")
            .CreateAsync();

        _small = await IndexableProductAsync(mother, "REV-S");
        _medium = await IndexableProductAsync(mother, "REV-M");
        _large = await IndexableProductAsync(mother, "REV-L");
        _orphan = await IndexableProductAsync(mother, "REV-ORPHAN");

        await mother.User()
            .WithUsername("revieweroperator")
            .AsOperator()
            .AssignedTo(_pos.Id)
            .CreateAsync();
    }

    public Task DisposeAsync() => Task.CompletedTask;

    // ── Auditing ──────────────────────────────────────────────────────────────────────────────

    [Fact]
    public async Task Audit_ReturnsFlaggedMembersAndCandidates_ForAdministrator()
    {
        using var factory = WithGateway(new AuditingGateway(_medium, _orphan));
        var admin = await AuthenticateAgainstAsync(factory, "admin", "Admin123!");

        var response = await admin.PostAsJsonAsync(AuditEndpoint, new FamilyAuditQueryRequest());

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadFromJsonAsync<AiFamilyAuditResponse>();
        body!.FlaggedMembers.Should().ContainSingle()
            .Which.Margin.Should().BeGreaterThan(0, "the margin is what the reviewer judges by");
        body.OrphanCandidates.Should().ContainSingle();
        body.OrphanCandidates[0].DataOrigin.Should().Be("real");
        body.RejectedGroups.Should().NotBeEmpty("a refusal is half the answer, not an error");
        body.ExcludedProducts.Should().NotBeEmpty();
    }

    /// <summary>
    /// Auditing is a read. Recording a judgement is a different route, and that separation is the
    /// only reason this assertion can be made at all.
    /// </summary>
    [Fact]
    public async Task Audit_WritesNothing_WhenRequested()
    {
        using var factory = WithGateway(new AuditingGateway(_medium, _orphan));
        var admin = await AuthenticateAgainstAsync(factory, "admin", "Admin123!");

        var before = await ProductTimestampsAsync();

        await admin.PostAsJsonAsync(AuditEndpoint, new FamilyAuditQueryRequest());

        (await ProductTimestampsAsync()).Should().Equal(before,
            "an audit that moves a watermark would make the indexing feed re-emit products "
            + "nothing happened to");
        await CountVerdictsAsync().ContinueWith(count => count.Result.Should().Be(0,
            "auditing must not record judgements nobody made"));
        (await CountFamiliesAsync()).Should().Be(0);
    }

    [Fact]
    public async Task Audit_ReturnsForbidden_ForOperator()
    {
        using var factory = WithGateway(new AuditingGateway(_medium, _orphan));
        var operatorClient = await AuthenticateAgainstAsync(
            factory, "revieweroperator", "Test123!");

        var response = await operatorClient.PostAsJsonAsync(
            AuditEndpoint, new FamilyAuditQueryRequest());

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    [Fact]
    public async Task Audit_Unauthenticated_ReturnsUnauthorized()
    {
        // A fresh client from the factory, never one that has logged in: the shared client keeps
        // the cookies of every login it performed and is not anonymous.
        using var factory = WithGateway(new AuditingGateway(_medium, _orphan));
        var anonymous = factory.CreateClient();

        var response = await anonymous.PostAsJsonAsync(AuditEndpoint, new FamilyAuditQueryRequest());

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    /// <summary>
    /// A failure is never an empty audit.
    /// </summary>
    /// <remarks>
    /// On a catalogue-quality screen an empty answer reads as "the catalogue is clean", which is
    /// precisely the conclusion this whole change exists to establish with evidence. Returning one
    /// because the service did not respond would assert it by accident — the shape in which the
    /// C17 risk actually materialised.
    /// </remarks>
    [Fact]
    public async Task Audit_WhenServiceUnavailable_ReturnsServiceUnavailableNotAnEmptyResult()
    {
        using var factory = WithGateway(new UnavailableGateway());
        var admin = await AuthenticateAgainstAsync(factory, "admin", "Admin123!");

        var response = await admin.PostAsJsonAsync(AuditEndpoint, new FamilyAuditQueryRequest());

        response.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable);
        (await response.Content.ReadAsStringAsync())
            .Should().NotContain("\"flaggedMembers\"",
                "an empty findings list must never be served in place of a failure");
    }

    // ── Verdicts ──────────────────────────────────────────────────────────────────────────────

    [Fact]
    public async Task Verdict_SamePairTwice_CorrectsInsteadOfDuplicating()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium));

        await RecordVerdictAsync(admin, _medium.Id, familyId, "Rejected", note: "no encaja");
        var second = await RecordVerdictAsync(admin, _medium.Id, familyId, "Confirmed", note: "sí encaja");

        second.Created.Should().Be(0);
        second.Updated.Should().Be(1, "judging a pair again is a correction, not a second opinion");
        (await CountVerdictsAsync()).Should().Be(1, "the unique index on the pair says the same thing");
    }

    [Fact]
    public async Task Verdict_DismissedPair_ExcludedFromNextAudit()
    {
        var setupAdmin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(setupAdmin, ("S", _small), ("M", _medium));
        await RecordVerdictAsync(setupAdmin, _orphan.Id, familyId, "Rejected");

        var gateway = new AuditingGateway(_medium, _orphan);
        using var factory = WithGateway(gateway);
        var admin = await AuthenticateAgainstAsync(factory, "admin", "Admin123!");

        await admin.PostAsJsonAsync(AuditEndpoint, new FamilyAuditQueryRequest());

        gateway.LastRequest!.JudgedPairs.Should().ContainSingle(pair =>
            pair.ProductId == _orphan.Id.ToString() && pair.FamilyId == familyId.ToString(),
            "the AI service holds no verdict, so this side has to send what it knows on every call");
    }

    [Fact]
    public async Task Verdict_UnknownOutcome_IsRefused()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium));

        var response = await admin.PostAsJsonAsync(VerdictsEndpoint, new RecordFamilyVerdictsRequest
        {
            Verdicts =
            [
                new FamilyVerdictRequest
                {
                    ProductId = _medium.Id,
                    FamilyId = familyId,
                    Outcome = "Maybe"
                }
            ]
        });

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest,
            "an unrecognised verdict must not fall through to the first member of the enum, which "
            + "would record a confirmation nobody gave");
        (await CountVerdictsAsync()).Should().Be(0);
    }

    [Fact]
    public async Task Verdict_RequiresAdministrator()
    {
        var setupAdmin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(setupAdmin, ("S", _small), ("M", _medium));

        var operatorClient = await AuthenticateAsync("revieweroperator", "Test123!");

        var response = await operatorClient.PostAsJsonAsync(
            VerdictsEndpoint,
            new RecordFamilyVerdictsRequest
            {
                Verdicts =
                [
                    new FamilyVerdictRequest
                    {
                        ProductId = _medium.Id,
                        FamilyId = familyId,
                        Outcome = "Confirmed"
                    }
                ]
            });

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
        (await CountVerdictsAsync()).Should().Be(0);
    }

    // ── Listing ───────────────────────────────────────────────────────────────────────────────

    [Fact]
    public async Task ListFamilies_ReportsMemberAndReviewCounts()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium));
        await RecordVerdictAsync(admin, _medium.Id, familyId, "Rejected");

        var response = await admin.GetAsync(FamiliesEndpoint);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var page = await response.Content
            .ReadFromJsonAsync<PaginatedResultDto<ProductFamilyListItemDto>>();
        page!.TotalCount.Should().Be(1);

        var family = page.Items.Single();
        family.Id.Should().Be(familyId);
        family.MemberCount.Should().Be(2);
        family.ReviewedMemberCount.Should().Be(1);
        family.RejectedMemberCount.Should().Be(1,
            "without these a reviewer cannot tell a family nobody opened from one already worked "
            + "through, and every other column of an assisted batch looks identical");
    }

    [Fact]
    public async Task ListFamilies_FiltersByOrigin()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        await CreateFamilyAsync(admin, ("S", _small), ("M", _medium));

        var manual = await admin.GetAsync($"{FamiliesEndpoint}?origin=Manual");
        var assisted = await admin.GetAsync($"{FamiliesEndpoint}?origin=AiApproved");

        var manualPage = await manual.Content
            .ReadFromJsonAsync<PaginatedResultDto<ProductFamilyListItemDto>>();
        var assistedPage = await assisted.Content
            .ReadFromJsonAsync<PaginatedResultDto<ProductFamilyListItemDto>>();

        manualPage!.TotalCount.Should().Be(1);
        assistedPage!.TotalCount.Should().Be(0,
            "a family created by hand must not be counted among the approved suggestions");
    }

    /// <summary>
    /// An unrecognised origin is refused rather than ignored: serving the unfiltered set would
    /// answer a question nobody asked, and on a review screen it reads as "these are the manual
    /// families" when they are all of them.
    /// </summary>
    [Fact]
    public async Task ListFamilies_UnknownOrigin_ReturnsBadRequest()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.GetAsync($"{FamiliesEndpoint}?origin=Aprobada");

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task ListFamilies_RequiresAdministrator()
    {
        var operatorClient = await AuthenticateAsync("revieweroperator", "Test123!");

        var response = await operatorClient.GetAsync(FamiliesEndpoint);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden,
            "reading one family serves a product's sibling list; enumerating them is administration");
    }

    // ── Dissolving ────────────────────────────────────────────────────────────────────────────

    [Fact]
    public async Task DeleteFamily_CascadesVerdictsAndFreesProducts()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium));
        await RecordVerdictAsync(admin, _medium.Id, familyId, "Rejected");

        var response = await admin.DeleteAsync($"{FamiliesEndpoint}/{familyId}");

        response.StatusCode.Should().Be(HttpStatusCode.NoContent);
        (await CountFamiliesAsync()).Should().Be(0, "dissolving must not leave an empty shell");
        (await CountMembersAsync()).Should().Be(0);
        (await CountVerdictsAsync()).Should().Be(0,
            "a judgement about a family that no longer exists answers a question nobody can ask");

        // And the freed products can be assigned elsewhere, which is the point of dissolving.
        var reassigned = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium));
        reassigned.Should().NotBe(familyId);
    }

    /// <summary>
    /// The only test here that notices a dissolution the vector index will never hear about.
    /// </summary>
    /// <remarks>
    /// The feed's catalogue cursor is the greatest of the product, its profile and its family when
    /// the product is a current member. A product that stops being a member stops joining the
    /// family row, so without an explicit stamp it never appears on an incremental pull again and
    /// its document keeps a family identifier that no longer resolves — with no error anywhere.
    /// Everything else in this class would pass against that implementation.
    /// </remarks>
    [Fact]
    public async Task DeleteFamily_StampsDepartingProducts()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium));

        var cursor = DateTime.UtcNow;
        await Task.Delay(10);

        await admin.DeleteAsync($"{FamiliesEndpoint}/{familyId}");

        var emitted = await ReadFeedSinceAsync(cursor);
        emitted.Should().Contain([_small.Id, _medium.Id],
            "a product that left a family has to reach the index, or its document keeps pointing "
            + "at a family that is gone");
        emitted.Should().NotContain(_large.Id, "nothing happened to the products that never joined");
    }

    [Fact]
    public async Task DeleteFamily_Absent_ReturnsNotFound()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.DeleteAsync($"{FamiliesEndpoint}/{Guid.NewGuid()}");

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    [Fact]
    public async Task DeleteFamily_RequiresAdministrator()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium));

        var operatorClient = await AuthenticateAsync("revieweroperator", "Test123!");

        var response = await operatorClient.DeleteAsync($"{FamiliesEndpoint}/{familyId}");

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
        (await CountFamiliesAsync()).Should().Be(1);
    }

    // ── The trap C07 recorded ─────────────────────────────────────────────────────────────────

    /// <summary>
    /// Moving a product between families, which is one request that deletes and inserts at once.
    /// </summary>
    /// <remarks>
    /// C07's apply left this written down: declaring additions by adding them to the family's
    /// navigation collection fails, because <c>BaseEntity</c> assigns the identifier in its
    /// constructor and the change tracker then takes a new membership for an existing row and
    /// emits an update against nothing. It surfaces <strong>only</strong> when one request deletes
    /// and inserts together — reordering variants, swapping two labels — never when it only adds
    /// or only removes. Moving a product between families is exactly that shape, and the review
    /// screen's most ordinary action.
    /// </remarks>
    [Fact]
    public async Task MoveProductBetweenFamilies_ReordersAndSwapsLabels_WithoutPhantomUpdate()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var source = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium));
        var target = await CreateFamilyAsync(admin, ("L", _large));

        // Out of the source, reordering what stays and swapping its label at the same time.
        var removed = await admin.PutAsJsonAsync(
            $"{FamiliesEndpoint}/{source}/members",
            new ReplaceFamilyMembersRequest
            {
                Members = [new ProductFamilyMemberRequest { ProductId = _small.Id, VariantLabel = "M" }]
            });
        removed.StatusCode.Should().Be(HttpStatusCode.OK);

        // Into the target, which also reorders and relabels in the same request.
        var added = await admin.PutAsJsonAsync(
            $"{FamiliesEndpoint}/{target}/members",
            new ReplaceFamilyMembersRequest
            {
                Members =
                [
                    new ProductFamilyMemberRequest { ProductId = _medium.Id, VariantLabel = "L" },
                    new ProductFamilyMemberRequest { ProductId = _large.Id, VariantLabel = "XL" }
                ]
            });

        added.StatusCode.Should().Be(HttpStatusCode.OK);

        var moved = await added.Content.ReadFromJsonAsync<ProductFamilyDto>();
        moved!.Members.Select(member => member.ProductId).Should().Equal([_medium.Id, _large.Id]);
        moved.Members.Select(member => member.VariantLabel).Should().Equal(["L", "XL"]);

        var left = await (await admin.GetAsync($"{FamiliesEndpoint}/{source}"))
            .Content.ReadFromJsonAsync<ProductFamilyDto>();
        left!.Members.Should().ContainSingle().Which.ProductId.Should().Be(_small.Id);
        left.Members[0].VariantLabel.Should().Be("M",
            "the label swap has to survive a request that also removed a member");
    }

    // ── Helpers ───────────────────────────────────────────────────────────────────────────────

    private WebApplicationFactory<Program> WithGateway(IAiGatewayClient gateway) =>
        _factory.WithWebHostBuilder(builder =>
            builder.ConfigureServices(services => services.AddScoped(_ => gateway)));

    private Task<HttpClient> AuthenticateAsync(string username, string password) =>
        AuthenticateAgainstAsync(_factory, username, password);

    private static async Task<HttpClient> AuthenticateAgainstAsync(
        WebApplicationFactory<Program> factory, string username, string password)
    {
        var login = await factory.CreateClient().PostAsJsonAsync(
            "/api/auth/login",
            new LoginRequest { Username = username, Password = password });
        login.EnsureSuccessStatusCode();

        var authenticated = factory.CreateClient();
        foreach (var cookie in login.Headers.GetValues("Set-Cookie"))
        {
            var parts = cookie.Split(';')[0].Split('=');
            if (parts.Length == 2)
            {
                authenticated.DefaultRequestHeaders.Add("Cookie", $"{parts[0]}={parts[1]}");
            }
        }

        return authenticated;
    }

    private static async Task<Guid> CreateFamilyAsync(
        HttpClient admin, params (string Label, Product Product)[] members)
    {
        var response = await admin.PostAsJsonAsync("/api/product-families", new CreateProductFamilyRequest
        {
            Name = "Anillo erizo de mar",
            Members = [.. members.Select(member => new ProductFamilyMemberRequest
            {
                ProductId = member.Product.Id,
                VariantLabel = member.Label
            })]
        });
        response.EnsureSuccessStatusCode();

        var family = await response.Content.ReadFromJsonAsync<ProductFamilyDto>();
        return family!.Id;
    }

    private static async Task<RecordFamilyVerdictsResponse> RecordVerdictAsync(
        HttpClient admin, Guid productId, Guid familyId, string outcome, string? note = null)
    {
        var response = await admin.PostAsJsonAsync(VerdictsEndpoint, new RecordFamilyVerdictsRequest
        {
            Verdicts =
            [
                new FamilyVerdictRequest
                {
                    ProductId = productId,
                    FamilyId = familyId,
                    Outcome = outcome,
                    MarginAtReview = 0.16,
                    Note = note
                }
            ]
        });
        response.EnsureSuccessStatusCode();

        return (await response.Content.ReadFromJsonAsync<RecordFamilyVerdictsResponse>())!;
    }

    private async Task<List<DateTime>> ProductTimestampsAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        return await context.Products
            .OrderBy(product => product.SKU)
            .Select(product => product.UpdatedAt)
            .ToListAsync();
    }

    private async Task<int> CountVerdictsAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        return await context.FamilyReviewVerdicts.CountAsync();
    }

    private async Task<int> CountFamiliesAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        return await context.ProductFamilies.CountAsync();
    }

    private async Task<int> CountMembersAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        return await context.ProductFamilyMembers.CountAsync();
    }

    private async Task<List<Guid>> ReadFeedSinceAsync(DateTime since)
    {
        using var scope = _factory.Services.CreateScope();
        var feed = scope.ServiceProvider.GetRequiredService<IIndexFeedService>();

        var page = await feed.GetCatalogPageAsync(since, Guid.Empty, CancellationToken.None);

        return [.. page.Items.OfType<CatalogUpsertItemDto>().Select(item => item.ProductId)];
    }

    private static async Task<Product> IndexableProductAsync(TestDataMother mother, string sku)
    {
        var product = await mother.Product().WithSku(sku).WithName("Anillo erizo de mar").CreateAsync();

        mother.Context.ProductAiProfiles.Add(new ProductAiProfile
        {
            ProductId = product.Id,
            PieceType = "anillo",
            MaterialsJson = "[\"plata\"]",
            ColorTagsJson = "[]",
            StyleTagsJson = "[]",
            OccasionTagsJson = "[]",
            FieldConfidenceJson = "{}",
            FieldSourceJson = "{}",
            ProposedProfileJson = "{}",
            SourceHash = new string('a', 64),
            ReviewStatus = Domain.Enums.ProfileReviewStatus.Approved,
            ReviewOrigin = Domain.Enums.ProfileReviewOrigin.AutoBulk
        });
        await mother.Context.SaveChangesAsync();

        return product;
    }

    // ── Gateway doubles ───────────────────────────────────────────────────────────────────────

    /// <summary>Answers an audit with one finding of each kind, and records what it was asked.</summary>
    private sealed class AuditingGateway(Product flagged, Product candidate) : IAiGatewayClient
    {
        /// <summary>What the last call carried, so a test can assert the judged pairs travelled.</summary>
        public AiFamilyAuditRequest? LastRequest { get; private set; }

        public Task<AiSearchResponse> SearchAsync(
            AiSearchRequest request, AiCallScope scope, CancellationToken cancellationToken = default) =>
            throw new NotSupportedException();

        public Task<AiEnrichResponse> EnrichAsync(
            AiEnrichRequest request, AiCallScope scope, CancellationToken cancellationToken = default) =>
            throw new NotSupportedException();

        public Task<AiHealthResponse> HealthAsync(CancellationToken cancellationToken = default) =>
            throw new NotSupportedException();

        public Task<AiFamilySuggestResponse> SuggestFamiliesAsync(
            AiFamilySuggestRequest request, AiCallScope scope, CancellationToken cancellationToken = default) =>
            throw new NotSupportedException();

        public Task<AiFamilyAuditResponse> AuditFamiliesAsync(
            AiFamilyAuditRequest request,
            AiCallScope scope,
            CancellationToken cancellationToken = default)
        {
            LastRequest = request;

            return Task.FromResult(new AiFamilyAuditResponse
            {
                FlaggedMembers =
                [
                    new AiFlaggedFamilyMember
                    {
                        ProductId = flagged.Id.ToString(),
                        Sku = flagged.SKU,
                        Name = flagged.Name,
                        VariantLabel = "M",
                        FamilyId = Guid.NewGuid().ToString(),
                        FamilyName = "Anillo erizo de mar",
                        Margin = 0.16,
                        StrangerFamilyId = Guid.NewGuid().ToString()
                    }
                ],
                OrphanCandidates =
                [
                    new AiOrphanCandidate
                    {
                        ProductId = candidate.Id.ToString(),
                        Sku = candidate.SKU,
                        Name = candidate.Name,
                        PieceType = "anillo",
                        DataOrigin = "real",
                        FamilyId = Guid.NewGuid().ToString(),
                        FamilyName = "Anillo erizo de mar",
                        Similarity = 0.94,
                        WorstSibling = 0.87,
                        Margin = 0.07,
                        Purity = 4
                    }
                ],
                RejectedGroups =
                [
                    new AiRejectedFamilyGroup
                    {
                        Root = "alianzas",
                        PieceType = "anillo",
                        Reason = "root_too_short",
                        ProductNames = ["Alianzas Plata", "Alianzas oro"]
                    }
                ],
                ExcludedProducts =
                [
                    new AiExcludedProduct
                    {
                        ProductId = Guid.NewGuid().ToString(),
                        Sku = "SKU-NO-TYPE",
                        Name = "Diadema perlas",
                        Reason = "no_piece_type"
                    }
                ],
                FamiliesReviewedCount = 1,
                MembersExaminedCount = 2
            });
        }
    }

    /// <summary>Fails the way an unreachable service fails, so the controller's answer is testable.</summary>
    private sealed class UnavailableGateway : IAiGatewayClient
    {
        public Task<AiSearchResponse> SearchAsync(
            AiSearchRequest request, AiCallScope scope, CancellationToken cancellationToken = default) =>
            throw new NotSupportedException();

        public Task<AiEnrichResponse> EnrichAsync(
            AiEnrichRequest request, AiCallScope scope, CancellationToken cancellationToken = default) =>
            throw new NotSupportedException();

        public Task<AiHealthResponse> HealthAsync(CancellationToken cancellationToken = default) =>
            throw new NotSupportedException();

        public Task<AiFamilySuggestResponse> SuggestFamiliesAsync(
            AiFamilySuggestRequest request, AiCallScope scope, CancellationToken cancellationToken = default) =>
            throw new NotSupportedException();

        public Task<AiFamilyAuditResponse> AuditFamiliesAsync(
            AiFamilyAuditRequest request, AiCallScope scope, CancellationToken cancellationToken = default) =>
            throw new Application.Exceptions.AiUnavailableException("The AI service could not be reached.");
    }
}
