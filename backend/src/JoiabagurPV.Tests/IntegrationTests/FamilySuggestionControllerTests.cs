using System.Net;
using System.Net.Http.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.DTOs.Products;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for the assisted family flow: jbg-ai proposes, this side persists.
/// </summary>
/// <remarks>
/// The test that matters most is
/// <see cref="ApplyFamilySuggestions_MakesMembersVisibleToAnIncrementalPull"/>. Everything else
/// here would also pass against an implementation that wrote the membership rows by direct SQL —
/// and that implementation would leave the vector index blind to every family it ever created,
/// without raising anything. The watermark is the only observable difference.
/// </remarks>
[Collection(IntegrationTestCollection.Name)]
public class FamilySuggestionControllerTests : IAsyncLifetime
{
    private const string SuggestEndpoint = "/api/ai/catalog/family-suggestions";
    private const string ApplyEndpoint = "/api/ai/catalog/family-suggestions/apply";

    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;

    private PointOfSale _pos = null!;
    private Product _small = null!;
    private Product _medium = null!;
    private Product _large = null!;

    public FamilySuggestionControllerTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();

        using var mother = new TestDataMother(_factory.Services);

        _pos = await mother.PointOfSale()
            .WithCode("SUGGEST-POS")
            .WithName("Suggestion Point of Sale")
            .WithAddress("Test Address")
            // Pinned: Bogus generates phone numbers of varying length against a varchar(20).
            .WithPhone("600123456")
            .CreateAsync();

        _small = await IndexableProductAsync(mother, "SUG-S");
        _medium = await IndexableProductAsync(mother, "SUG-M");
        _large = await IndexableProductAsync(mother, "SUG-L");

        await mother.User()
            .WithUsername("suggestoperator")
            .AsOperator()
            .AssignedTo(_pos.Id)
            .CreateAsync();
    }

    public Task DisposeAsync() => Task.CompletedTask;

    // ── Suggesting ────────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Asking for suggestions returns them and leaves the catalog exactly as it was found.
    /// </summary>
    /// <remarks>
    /// <para>
    /// The gateway is replaced by a stub proposing the fixture's own products. Without one the
    /// call ends at the real service and the assertions prove nothing: a request that returned no
    /// proposal could not have persisted one either, so the test would pass on a controller that
    /// writes eagerly the moment it does receive proposals.
    /// </para>
    /// <para>
    /// <c>UpdatedAt</c> is asserted alongside the row counts because it is the half of "wrote
    /// nothing" that has no visible row: stamping a product with no family attached creates
    /// nothing and still drags it into the next incremental pull.
    /// </para>
    /// </remarks>
    [Fact]
    public async Task SuggestFamilies_ReturnsProposals_WithoutWritingAnything()
    {
        var before = await ProductTimestampsAsync();

        using var factory = _factory.WithWebHostBuilder(builder =>
            builder.ConfigureServices(services =>
                services.AddScoped<IAiGatewayClient>(_ => new ProposingGateway(_small, _medium))));

        var admin = await AuthenticateAgainstAsync(factory, "admin", "Admin123!");

        var response = await admin.PostAsJsonAsync(SuggestEndpoint, new FamilySuggestionsRequest());

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await response.Content.ReadFromJsonAsync<AiFamilySuggestResponse>();
        body!.Proposals.Should().ContainSingle()
            .Which.Members.Should().HaveCount(2, "the proposal must reach the caller intact");

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        (await context.ProductFamilies.CountAsync()).Should().Be(0,
            "proposing is not approving: the write path is /apply and nothing else");
        (await context.ProductFamilyMembers.CountAsync()).Should().Be(0);

        (await ProductTimestampsAsync()).Should().Equal(before,
            "a product nothing happened to must stay out of the incremental feed's cursor");
    }

    // ── Applying ──────────────────────────────────────────────────────────────────────────────

    [Fact]
    public async Task ApplyFamilySuggestions_RecordsAiApprovedOriginWithApprover()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.PostAsJsonAsync(ApplyEndpoint, BatchOf(("S", _small), ("M", _medium)));

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await response.Content.ReadFromJsonAsync<ApplyFamilySuggestionsResponse>();
        body!.FamiliesCreated.Should().Be(1);
        body.MembersCreated.Should().Be(2);

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var family = await context.ProductFamilies.SingleAsync();

        family.Origin.Should().Be(Domain.Enums.FamilyOrigin.AiApproved,
            "the three columns C07 reserved finally have a write path");
        family.ApprovedByUserId.Should().NotBeNull();
        family.ApprovedAt.Should().NotBeNull();
    }

    [Fact]
    public async Task CreateFamily_StillRecordsManualOrigin()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        await admin.PostAsJsonAsync("/api/product-families", new CreateProductFamilyRequest
        {
            Name = "Hecha a mano",
            Members = [new ProductFamilyMemberRequest { ProductId = _small.Id, VariantLabel = "S" }]
        });

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var family = await context.ProductFamilies.SingleAsync();

        family.Origin.Should().Be(Domain.Enums.FamilyOrigin.Manual,
            "the two paths must stay distinguishable after the fact");
        family.ApprovedByUserId.Should().BeNull();
        family.ApprovedAt.Should().BeNull();
    }

    /// <summary>
    /// The one test that tells this implementation apart from one that fails silently.
    /// </summary>
    /// <remarks>
    /// <para>
    /// What has to be true is that an incremental catalog pull sees the new members. It is
    /// asserted on the feed rather than on a timestamp because the timestamp is not the mechanism:
    /// the feed's watermark is <c>greatest(Product.UpdatedAt, profile.UpdatedAt, family.UpdatedAt
    /// when the product is a current member)</c>, so <em>creating</em> a family moves it through
    /// the family's own <c>UpdatedAt</c> without touching <c>Product</c> at all. Only a
    /// <em>replace</em> needs the product stamped, because a product that <em>leaves</em> stops
    /// joining the family row and would otherwise vanish from the cursor.
    /// </para>
    /// <para>
    /// A first version of this test asserted <c>Product.UpdatedAt</c> and failed — correctly. The
    /// timestamp was the implementation detail; the feed is the requirement.
    /// </para>
    /// </remarks>
    [Fact]
    public async Task ApplyFamilySuggestions_MakesMembersVisibleToAnIncrementalPull()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var cursor = DateTime.UtcNow;

        await admin.PostAsJsonAsync(ApplyEndpoint, BatchOf(("S", _small), ("M", _medium)));

        var emitted = await ReadFeedSinceAsync(cursor);

        emitted.Should().Contain(_small.Id, "it entered a family after the cursor");
        emitted.Should().Contain(_medium.Id, "it entered a family after the cursor");
        emitted.Should().NotContain(_large.Id,
            "a product that entered nothing must not be re-emitted, or the pull would drag the world");
    }

    [Fact]
    public async Task ApplyFamilySuggestions_ReportsConflict_WithoutPartialFamily()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        await admin.PostAsJsonAsync(ApplyEndpoint, BatchOf(("S", _small), ("M", _medium)));

        // A second batch claiming a product the first one took, plus a clean family beside it.
        var second = new ApplyFamilySuggestionsRequest
        {
            Families =
            [
                new ApprovedFamilyRequest
                {
                    Name = "Familia en conflicto",
                    Members =
                    [
                        new ApprovedFamilyMemberRequest { ProductId = _small.Id, VariantLabel = "S" },
                        new ApprovedFamilyMemberRequest { ProductId = _large.Id, VariantLabel = "L" }
                    ]
                }
            ]
        };

        var response = await admin.PostAsJsonAsync(ApplyEndpoint, second);

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "a contested product is a reportable outcome, not a failed request");

        var body = await response.Content.ReadFromJsonAsync<ApplyFamilySuggestionsResponse>();
        body!.FamiliesCreated.Should().Be(0);
        body.Conflicts.Should().ContainSingle()
            .Which.Conflicts.Should().ContainSingle()
            .Which.ProductId.Should().Be(_small.Id);

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        (await context.ProductFamilies.CountAsync()).Should().Be(1,
            "the conflicting family must be skipped whole, never half-created");
        (await context.ProductFamilyMembers.CountAsync()).Should().Be(2);
    }

    /// <summary>
    /// Re-approving an already applied suggestion writes nothing — and says so.
    /// </summary>
    /// <remarks>
    /// It does not short-circuit the way an identical membership replace does in C07: it takes the
    /// conflict path, because from the catalogue's point of view those products already belong
    /// somewhere. Nothing is written either way, and reporting it beats absorbing it in silence —
    /// approving the same batch twice is a mistake worth seeing.
    /// </remarks>
    [Fact]
    public async Task ApplyFamilySuggestions_AppliedTwice_WritesNothingTheSecondTime()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var batch = BatchOf(("S", _small), ("M", _medium));

        await admin.PostAsJsonAsync(ApplyEndpoint, batch);
        var second = await admin.PostAsJsonAsync(ApplyEndpoint, batch);

        var body = await second.Content.ReadFromJsonAsync<ApplyFamilySuggestionsResponse>();
        body!.FamiliesCreated.Should().Be(0);
        body.MembersCreated.Should().Be(0);
        body.Conflicts.Should().ContainSingle();

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        (await context.ProductFamilies.CountAsync()).Should().Be(1, "no second family is created");
        (await context.ProductFamilyMembers.CountAsync()).Should().Be(2);
    }

    // ── Validation ────────────────────────────────────────────────────────────────────────────

    [Fact]
    public async Task ApplyFamilySuggestions_RejectsDuplicateVariantLabelWithinAFamily()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.PostAsJsonAsync(ApplyEndpoint, BatchOf(("S", _small), ("S", _medium)));

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest,
            "two members that cannot be told apart defeat the purpose of the family");
    }

    [Fact]
    public async Task ApplyFamilySuggestions_RejectsAProductDeclaredInTwoFamiliesOfTheSameBatch()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var request = new ApplyFamilySuggestionsRequest
        {
            Families =
            [
                new ApprovedFamilyRequest
                {
                    Name = "Primera",
                    Members =
                    [
                        new ApprovedFamilyMemberRequest { ProductId = _small.Id, VariantLabel = "S" },
                        new ApprovedFamilyMemberRequest { ProductId = _medium.Id, VariantLabel = "M" }
                    ]
                },
                new ApprovedFamilyRequest
                {
                    Name = "Segunda",
                    Members =
                    [
                        new ApprovedFamilyMemberRequest { ProductId = _small.Id, VariantLabel = "S" },
                        new ApprovedFamilyMemberRequest { ProductId = _large.Id, VariantLabel = "L" }
                    ]
                }
            ]
        };

        var response = await admin.PostAsJsonAsync(ApplyEndpoint, request);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest,
            "otherwise the first family is created and the second fails on the index, "
            + "leaving a half-applied batch with no obvious cause");

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        (await context.ProductFamilies.CountAsync()).Should().Be(0, "nothing is written on a rejected batch");
    }

    [Fact]
    public async Task ApplyFamilySuggestions_RejectsAFamilyOfOne()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.PostAsJsonAsync(ApplyEndpoint, BatchOf(("S", _small)));

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    // ── Authorization ─────────────────────────────────────────────────────────────────────────

    [Fact]
    public async Task SuggestFamilies_ReturnsForbidden_ForOperator()
    {
        var operatorClient = await AuthenticateAsync("suggestoperator", "Test123!");

        var response = await operatorClient.PostAsJsonAsync(SuggestEndpoint, new FamilySuggestionsRequest());

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    [Fact]
    public async Task ApplyFamilySuggestions_ReturnsForbidden_ForOperator()
    {
        var operatorClient = await AuthenticateAsync("suggestoperator", "Test123!");

        var response = await operatorClient.PostAsJsonAsync(ApplyEndpoint, BatchOf(("S", _small), ("M", _medium)));

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        (await context.ProductFamilies.CountAsync()).Should().Be(0);
    }

    /// <summary>
    /// A fresh client, never the shared one.
    /// </summary>
    /// <remarks>
    /// The class-level <see cref="HttpClient"/> keeps the cookies of every login it performed, so
    /// asserting 401 through it passes or fails depending on which test ran first. Asking the
    /// factory for a new client is the only way to be genuinely anonymous.
    /// </remarks>
    [Fact]
    public async Task SuggestFamilies_ReturnsUnauthorized_ForAnonymous()
    {
        var anonymous = _factory.CreateClient();

        var response = await anonymous.PostAsJsonAsync(SuggestEndpoint, new FamilySuggestionsRequest());

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────────────────────

    private static ApplyFamilySuggestionsRequest BatchOf(params (string? Label, Product Product)[] members) =>
        new()
        {
            Families =
            [
                new ApprovedFamilyRequest
                {
                    Name = "Anillo erizo de mar",
                    Members = [.. members.Select(member => new ApprovedFamilyMemberRequest
                    {
                        ProductId = member.Product.Id,
                        VariantLabel = member.Label
                    })]
                }
            ]
        };

    /// <summary>
    /// A product the catalog feed can actually emit.
    /// </summary>
    /// <remarks>
    /// The feed inner-joins the AI profile and requires it approved, so a product without one is
    /// invisible to it no matter what happens to its families. A first version of this fixture
    /// created bare products and the feed assertion failed against an empty page — which was the
    /// fixture's fault, not the flow's.
    /// </remarks>
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

    /// <summary>Product identifiers an incremental catalog pull emits after a cursor.</summary>
    private async Task<List<Guid>> ReadFeedSinceAsync(DateTime since)
    {
        using var scope = _factory.Services.CreateScope();
        var feed = scope.ServiceProvider.GetRequiredService<IIndexFeedService>();

        var page = await feed.GetCatalogPageAsync(since, Guid.Empty, CancellationToken.None);

        return [.. page.Items.OfType<CatalogUpsertItemDto>().Select(item => item.ProductId)];
    }

    private Task<HttpClient> AuthenticateAsync(string username, string password) =>
        AuthenticateAgainstAsync(_factory, username, password);

    /// <summary>
    /// Logs in against a specific host, which the gateway-replacing tests need: their host is a
    /// different one from the class's, and a cookie issued by one is no use to the other.
    /// </summary>
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

    /// <summary>Every product's <c>UpdatedAt</c>, in a stable order, to compare before and after.</summary>
    private async Task<List<DateTime>> ProductTimestampsAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        return await context.Products
            .OrderBy(product => product.SKU)
            .Select(product => product.UpdatedAt)
            .ToListAsync();
    }

    /// <summary>Proposes the fixture's own products, so any write would land on rows this test reads.</summary>
    private sealed class ProposingGateway(Product first, Product second) : IAiGatewayClient
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
            AiFamilySuggestRequest request,
            AiCallScope scope,
            CancellationToken cancellationToken = default) =>
            Task.FromResult(new AiFamilySuggestResponse
            {
                Proposals =
                [
                    new AiFamilyProposal
                    {
                        Root = "anillo erizo de mar",
                        SuggestedName = "Anillo erizo de mar",
                        PieceType = "anillo",
                        Members =
                        [
                            new AiProposedFamilyMember
                            {
                                ProductId = first.Id.ToString(),
                                Sku = first.SKU,
                                Name = first.Name,
                                VariantLabel = "S",
                                Position = 0
                            },
                            new AiProposedFamilyMember
                            {
                                ProductId = second.Id.ToString(),
                                Sku = second.SKU,
                                Name = second.Name,
                                VariantLabel = "M",
                                Position = 1
                            }
                        ]
                    }
                ]
            });
    }
}
