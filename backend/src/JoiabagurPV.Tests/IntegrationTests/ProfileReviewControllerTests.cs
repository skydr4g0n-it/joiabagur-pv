using System.Net;
using System.Net.Http.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// The six routes of the profile review capability, and who may call them.
/// </summary>
/// <remarks>
/// A review rewrites what the catalog asserts about a piece — that it is silver, that it is a
/// ring — and those assertions reach a customer through an operator repeating them. So the
/// question of who may record one is not a formality, and it is asserted over every route rather
/// than over a representative one: an authorisation attribute is per action, and the route added
/// last is the one nobody checks.
/// </remarks>
[Collection(IntegrationTestCollection.Name)]
public class ProfileReviewControllerTests : IAsyncLifetime
{
    private const string QueueEndpoint = "/api/ai/catalog/profile-review-queue";
    private const string ReviewsEndpoint = "/api/ai/catalog/profile-reviews";
    private const string BulkEndpoint = "/api/ai/catalog/profile-reviews/bulk";
    private const string RejectedEndpoint = "/api/ai/catalog/profile-reviews/rejected";
    private const string RestoreEndpoint = "/api/ai/catalog/profile-reviews/restore";
    private const string MetricsEndpoint = "/api/ai/catalog/profile-review-metrics";

    private readonly ApiWebApplicationFactory _factory;

    private Product _product = null!;

    public ProfileReviewControllerTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
    }

    public async Task InitializeAsync()
    {
        // Starts the host before anything asks the database to be reset. Migrations run at
        // start-up, and the reset builds its plan by reading the schema — so calling it first
        // against a container nothing has migrated finds no tables. Other classes in this
        // collection get away with the reverse order only because some earlier class already
        // started the host, which makes them pass together and fail alone.
        _factory.CreateClient().Dispose();

        await _factory.ResetDatabaseAsync();

        using var mother = new TestDataMother(_factory.Services);

        var pos = await mother.PointOfSale()
            .WithCode("PROFILE-POS")
            .WithName("Profile Review Point of Sale")
            .WithAddress("Test Address")
            // Pinned: Bogus generates phone numbers of varying length against a varchar(20).
            .WithPhone("600123456")
            .CreateAsync();

        _product = await mother.Product()
            .WithSku("PROF-1")
            .WithName("Anillo erizo de mar talla M")
            .WithDescription("Anillo en plata de ley con acabado pulido.")
            .CreateAsync();

        await mother.User()
            .WithUsername("profileoperator")
            .AsOperator()
            .AssignedTo(pos.Id)
            .CreateAsync();

        await SeedProfileAsync();
    }

    public Task DisposeAsync() => Task.CompletedTask;

    /// <summary>Every route of the capability, with a body that would be valid if it were allowed.</summary>
    public static TheoryData<string, string> EveryRoute() => new()
    {
        { HttpMethod.Get.Method, QueueEndpoint },
        { HttpMethod.Post.Method, ReviewsEndpoint },
        { HttpMethod.Post.Method, BulkEndpoint },
        { HttpMethod.Get.Method, RejectedEndpoint },
        { HttpMethod.Post.Method, RestoreEndpoint },
        { HttpMethod.Get.Method, MetricsEndpoint }
    };

    [Theory]
    [MemberData(nameof(EveryRoute))]
    public async Task ProfileReview_OperatorRole_Returns403(string method, string endpoint)
    {
        var operatorClient = await AuthenticateAsync("profileoperator", "Test123!");

        var response = await SendAsync(operatorClient, method, endpoint);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        // And nothing moved. A 403 that had already written is not a refusal.
        await AssertProfileUntouchedAsync();
    }

    [Theory]
    [MemberData(nameof(EveryRoute))]
    public async Task ProfileReview_Unauthenticated_Returns401(string method, string endpoint)
    {
        // A fresh client from the factory, never one that has logged in: the shared client keeps
        // the cookies of every login it performed and is not anonymous. Asserting 401 with a
        // reused client is how a test comes back green having proved the opposite of its name.
        var anonymous = _factory.CreateClient();

        var response = await SendAsync(anonymous, method, endpoint);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task ProfileReview_Queue_ReturnsBatchForAdministrator()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.GetAsync(QueueEndpoint);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadFromJsonAsync<ProfileReviewQueueDto>();
        body!.Seed.Should().NotBeNullOrWhiteSpace("a figure has to be able to name its own sample");
        body.Strata.Should().HaveCount(3);
        body.Items.Should().ContainSingle().Which.Sku.Should().Be("PROF-1");
        body.PageSize.Should().BeLessThanOrEqualTo(ProfileReviewQueueRequest.MaxPageSize);
    }

    [Fact]
    public async Task ProfileReview_QueuePageSizeAboveFifty_IsRejected()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.GetAsync($"{QueueEndpoint}?pageSize=500");

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task ProfileReview_IndividualWithoutDuration_IsRejectedByTheRoute()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.PostAsJsonAsync(ReviewsEndpoint, new RecordProfileReviewRequest
        {
            ProductId = _product.Id,
            Verdict = "approved",
            ReviewDurationMs = null,
            Materials = ["plata"]
        });

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        await AssertProfileUntouchedAsync();
    }

    [Fact]
    public async Task ProfileReview_Individual_StampsReviewerServerSide()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        // Read back before the review rather than compared against the literal that was written.
        // The column is jsonb, so PostgreSQL reorders the keys and reformats the whitespace on
        // the way in: a byte comparison against the source literal fails on a document nothing
        // touched, and would have to be "fixed" by relaxing exactly the assertion that matters.
        var proposalBefore = await ReadProposalAsync();

        var response = await admin.PostAsJsonAsync(ReviewsEndpoint, new RecordProfileReviewRequest
        {
            ProductId = _product.Id,
            Verdict = "approved",
            ReviewDurationMs = 28_500,
            PieceType = "anillo",
            Materials = ["plata", "oro"],
            SizeLabel = "M"
        });

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadFromJsonAsync<RecordProfileReviewResponse>();
        body!.Directions.Should().Contain(direction =>
            direction.Field == "materials" && direction.Direction == "addition");

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var stored = await context.ProductAiProfiles
            .AsNoTracking()
            .SingleAsync(profile => profile.ProductId == _product.Id);

        stored.ReviewedByUserId.Should().NotBeNull("the server stamps the reviewer, not the body");
        stored.ReviewDurationMs.Should().Be(28_500);
        stored.ReviewOrigin.Should().Be(Domain.Enums.ProfileReviewOrigin.Human);
        stored.MaterialsJson.Should().Contain("oro", "the reviewer's correction is what is in force");
        stored.ProposedProfileJson.Should().Be(
            proposalBefore, "the raw proposal is what the correction rate is measured against");
    }

    [Fact]
    public async Task ProfileReview_BulkSpanningFields_IsRejectedByTheRoute()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.PostAsJsonAsync(BulkEndpoint, new BulkApproveProfilesRequest
        {
            Fields = ["color_tags", "style_tags"],
            Stratum = "C",
            ProductIds = [_product.Id]
        });

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        await AssertProfileUntouchedAsync();
    }

    [Fact]
    public async Task ProfileReview_Metrics_ReportsAbsentAverageRatherThanZero()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.GetAsync(MetricsEndpoint);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadFromJsonAsync<ProfileReviewMetricsDto>();
        body!.AverageReviewSeconds.Should().BeNull(
            "nothing has been timed: a zero would assert an instantaneous review");
        body.ProfilesAutoBulk.Should().Be(1);
        body.ProfilesReviewedByHuman.Should().Be(0);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// The stored proposal, held as a constant so a test can assert it was not rewritten.
    /// </summary>
    private const string ProposalJson = """
        {"productId":"00000000-0000-0000-0000-000000000000","sku":"PROF-1","pieceType":{"value":"anillo","confidence":0.85,"source":2},"materials":{"value":["plata"],"confidence":0.85,"source":2},"sizeLabel":{"value":"M","confidence":1,"source":1},"colorTags":{"value":[],"confidence":0.2,"source":2},"styleTags":{"value":[],"confidence":0.2,"source":2},"occasionTags":{"value":[],"confidence":0.2,"source":2},"warnings":[]}
        """;

    private async Task SeedProfileAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        context.ProductAiProfiles.Add(new ProductAiProfile
        {
            ProductId = _product.Id,
            PieceType = "anillo",
            MaterialsJson = """["plata"]""",
            SizeLabel = "M",
            ColorTagsJson = "[]",
            StyleTagsJson = "[]",
            OccasionTagsJson = "[]",
            AiConfidence = 0.85m,
            // No stone at all, so the profile lands in the stratum of values asserted with a
            // textual span — the one the design expects omissions to concentrate in.
            FieldConfidenceJson =
                """{"piece_type":0.85,"materials":0.85,"size_label":1.0,"color_tags":0.2,"style_tags":0.2,"occasion_tags":0.2}""",
            FieldSourceJson =
                """{"piece_type":"inferred","materials":"inferred","size_label":"rule","color_tags":"inferred","style_tags":"inferred","occasion_tags":"inferred"}""",
            ProposedProfileJson = ProposalJson,
            SourceHash = "profile-review-test-hash",
            PromptVersion = "enrichment/v1",
            ReviewStatus = Domain.Enums.ProfileReviewStatus.Approved,
            ReviewOrigin = Domain.Enums.ProfileReviewOrigin.AutoBulk
        });

        await context.SaveChangesAsync();
    }

    private async Task<string> ReadProposalAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var stored = await context.ProductAiProfiles
            .AsNoTracking()
            .SingleAsync(profile => profile.ProductId == _product.Id);

        return stored.ProposedProfileJson;
    }

    private async Task AssertProfileUntouchedAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var stored = await context.ProductAiProfiles
            .AsNoTracking()
            .SingleAsync(profile => profile.ProductId == _product.Id);

        stored.ReviewOrigin.Should().Be(Domain.Enums.ProfileReviewOrigin.AutoBulk);
        stored.ReviewedByUserId.Should().BeNull();
        stored.ReviewDurationMs.Should().BeNull();
    }

    private static Task<HttpResponseMessage> SendAsync(
        HttpClient client, string method, string endpoint) =>
        method == HttpMethod.Get.Method
            ? client.GetAsync(endpoint)
            : client.PostAsJsonAsync(endpoint, EmptyBodyFor(endpoint));

    /// <summary>
    /// A body that would be accepted if the caller were allowed, so a 400 cannot be mistaken
    /// for the 401 or 403 the test is about.
    /// </summary>
    private static object EmptyBodyFor(string endpoint) => endpoint switch
    {
        BulkEndpoint => new BulkApproveProfilesRequest
        {
            Fields = ["color_tags"],
            Stratum = "C",
            ProductIds = [Guid.NewGuid()]
        },
        RestoreEndpoint => new RestoreRejectedProfileRequest { ProductId = Guid.NewGuid() },
        _ => new RecordProfileReviewRequest
        {
            ProductId = Guid.NewGuid(),
            Verdict = "approved",
            ReviewDurationMs = 1_000,
            Materials = ["plata"]
        }
    };

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
}
