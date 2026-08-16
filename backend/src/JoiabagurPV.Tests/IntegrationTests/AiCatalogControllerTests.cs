using System.Net;
using System.Net.Http.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.DTOs.Auth;
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
/// Integration tests for the catalog enrichment endpoint.
/// </summary>
/// <remarks>
/// The point of running these against the real host is the authorization boundary and the
/// validation that happens before any work: the enrichment itself is covered by unit tests with
/// a fake gateway, and reaching a real jbg-ai from here would make the suite depend on a
/// container it is not allowed to need.
/// </remarks>
[Collection(IntegrationTestCollection.Name)]
public class AiCatalogControllerTests : IAsyncLifetime
{
    private const string Endpoint = "/api/ai/catalog/enrich-batch";

    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;

    private PointOfSale _pos = null!;
    private Product _product = null!;

    public AiCatalogControllerTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();

        using var mother = new TestDataMother(_factory.Services);

        _pos = await mother.PointOfSale()
            .WithCode("ENRICH-POS")
            .WithName("Enrichment Point of Sale")
            .WithAddress("Test Address")
            // Pinned: the generator produces phone numbers of varying length and the column is
            // varchar(20), so leaving it to chance makes the suite fail intermittently.
            .WithPhone("600123456")
            .CreateAsync();

        _product = await mother.Product().WithSku("SKU-ENRICH-1").CreateAsync();

        await mother.User()
            .WithUsername("enrichoperator")
            .AsOperator()
            .AssignedTo(_pos.Id)
            .CreateAsync();
    }

    public Task DisposeAsync() => Task.CompletedTask;

    /// <summary>
    /// Enrichment rewrites what the catalog claims about a piece and spends money on a model
    /// provider. Neither is an operator's call.
    /// </summary>
    [Fact]
    public async Task EnrichBatch_AsOperator_Returns403()
    {
        var operatorClient = await AuthenticateAsync("enrichoperator", "Test123!");

        var response = await operatorClient.PostAsJsonAsync(
            Endpoint,
            new EnrichBatchRequest { ProductIds = [_product.Id] });

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    /// <summary>
    /// Asks the factory for a fresh client on purpose. The one this class holds has performed
    /// logins, so it carries their cookies and is not anonymous — the trap that turns a genuine
    /// 401 assertion into a passing 403 or 200.
    /// </summary>
    [Fact]
    public async Task EnrichBatch_Unauthenticated_Returns401()
    {
        var anonymous = _factory.CreateClient();

        var response = await anonymous.PostAsJsonAsync(
            Endpoint,
            new EnrichBatchRequest { ProductIds = [_product.Id] });

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task EnrichBatch_WithMoreThanContractBatchSize_ReturnsBadRequest()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var request = new EnrichBatchRequest
        {
            ProductIds = [.. Enumerable.Range(0, AiEnrichRequest.MaxBatchSize + 1).Select(_ => Guid.NewGuid())]
        };

        var response = await admin.PostAsJsonAsync(Endpoint, request);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest,
            "the contract limit is known on this side; spending a round trip to be told so is waste");
    }

    [Fact]
    public async Task EnrichBatch_WithEmptyBatch_ReturnsBadRequest()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.PostAsJsonAsync(Endpoint, new EnrichBatchRequest { ProductIds = [] });

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    /// <summary>
    /// There is no read surface on this capability, and that is a property worth asserting
    /// rather than a note in a document: reading, approving and measuring profiles belong
    /// elsewhere, and a route added "just for a counter" is how that boundary erodes.
    /// </summary>
    [Theory]
    [InlineData("/api/ai/catalog/profiles")]
    [InlineData("/api/ai/catalog/enrich-batch")]
    public async Task AiCatalog_ExposesNoReadRoute(string path)
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.GetAsync(path);

        response.StatusCode.Should().BeOneOf(
            HttpStatusCode.NotFound,
            HttpStatusCode.MethodNotAllowed);
    }

    /// <summary>
    /// There is no degraded path for enrichment, and that asymmetry with search is deliberate:
    /// a search can drop to the lexical index and still be useful, whereas producing attributes
    /// without the extractor would mean inventing catalog data.
    /// </summary>
    [Fact]
    public async Task EnrichBatch_WhenAiServiceHasNoImplementation_Returns503AndPersistsNothing()
    {
        var response = await CallWithGatewayAsync(
            new ThrowingGateway(() => new AiNotImplementedException("not implemented yet")));

        response.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable);

        var body = await response.Content.ReadAsStringAsync();
        body.Should().Contain("C09",
            "the message must name the change that delivers it, or the reader is left guessing "
            + "whether this is a fault or an unbuilt feature");

        await AssertNoProfilesAsync();
    }

    [Fact]
    public async Task EnrichBatch_WhenAiServiceIsUnavailable_Returns503AndPersistsNothing()
    {
        var response = await CallWithGatewayAsync(
            new ThrowingGateway(() => new AiUnavailableException("circuit open")));

        response.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable);
        await AssertNoProfilesAsync();
    }

    /// <summary>
    /// Runs one enrichment request against a host whose gateway is replaced by a fake that
    /// fails in a chosen way. The registration is appended, so it wins over the real one.
    /// </summary>
    private async Task<HttpResponseMessage> CallWithGatewayAsync(IAiGatewayClient gateway)
    {
        using var factory = _factory.WithWebHostBuilder(builder =>
            builder.ConfigureServices(services => services.AddScoped(_ => gateway)));

        var login = await factory.CreateClient().PostAsJsonAsync(
            "/api/auth/login",
            new LoginRequest { Username = "admin", Password = "Admin123!" });
        login.EnsureSuccessStatusCode();

        var admin = factory.CreateClient();
        foreach (var cookie in login.Headers.GetValues("Set-Cookie"))
        {
            var parts = cookie.Split(';')[0].Split('=');
            if (parts.Length == 2)
            {
                admin.DefaultRequestHeaders.Add("Cookie", $"{parts[0]}={parts[1]}");
            }
        }

        return await admin.PostAsJsonAsync(
            Endpoint,
            new EnrichBatchRequest { ProductIds = [_product.Id] });
    }

    private async Task AssertNoProfilesAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        (await context.ProductAiProfiles.CountAsync()).Should().Be(0,
            "a failed enrichment must leave the catalog exactly as it found it");
    }

    /// <summary>
    /// Two administrators enriching overlapping batches is an ordinary Tuesday, not a
    /// pathological interleaving: the window between reading which products already have a
    /// profile and writing the new ones **is the call to the extraction model**, which takes
    /// seconds. This test opens that window on purpose.
    /// </summary>
    /// <remarks>
    /// The losing row must be reported apart from a failure. It is not one — the product ended
    /// up enriched, just by somebody else — and folding the two together would send an
    /// administrator to re-run a batch chasing a problem that does not exist. Letting the
    /// violation escape would also contradict the method itself, which already treats a product
    /// the extractor answered nothing for as data and lets the other forty-nine through.
    /// </remarks>
    [Fact]
    public async Task EnrichBatch_WhenAnotherBatchWinsTheRace_CountsItSkippedInsteadOfFailingTheBatch()
    {
        using var factory = _factory.WithWebHostBuilder(builder =>
            builder.ConfigureServices(services => services.AddScoped<IAiGatewayClient>(provider =>
                new RaceWinningGateway(_product.Id, _factory.Services))));

        var admin = await AuthenticateAgainstAsync(factory, "admin", "Admin123!");

        var response = await admin.PostAsJsonAsync(
            Endpoint,
            new EnrichBatchRequest { ProductIds = [_product.Id] });

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "a race over one row must not discard the batch");

        var body = await response.Content.ReadFromJsonAsync<EnrichBatchResponse>();
        body!.SkippedConcurrent.Should().Be(1);
        body.Failed.Should().Be(0, "the product is enriched — by the other batch");
        body.Enriched.Should().Be(0);

        await AssertProfileCountAsync(1, "the winner's profile is the only one, and it survived");
    }

    /// <summary>A gateway that only knows how to fail, in the way the test chooses.</summary>
    private sealed class ThrowingGateway(Func<Exception> failure) : IAiGatewayClient
    {
        public Task<AiSearchResponse> SearchAsync(
            AiSearchRequest request, AiCallScope scope, CancellationToken cancellationToken = default) =>
            throw failure();

        public Task<AiEnrichResponse> EnrichAsync(
            AiEnrichRequest request, AiCallScope scope, CancellationToken cancellationToken = default) =>
            throw failure();
    }

    /// <summary>
    /// Simulates the competing batch by writing the rival profile from inside the model call —
    /// which is exactly where the real window is.
    /// </summary>
    private sealed class RaceWinningGateway(Guid productId, IServiceProvider services) : IAiGatewayClient
    {
        public Task<AiSearchResponse> SearchAsync(
            AiSearchRequest request, AiCallScope scope, CancellationToken cancellationToken = default) =>
            throw new NotSupportedException();

        public async Task<AiEnrichResponse> EnrichAsync(
            AiEnrichRequest request, AiCallScope scope, CancellationToken cancellationToken = default)
        {
            using var scoped = services.CreateScope();
            var context = scoped.ServiceProvider.GetRequiredService<ApplicationDbContext>();

            context.ProductAiProfiles.Add(new ProductAiProfile
            {
                ProductId = productId,
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
            await context.SaveChangesAsync(cancellationToken);

            return new AiEnrichResponse
            {
                Profiles =
                [
                    new AiProposedProfile
                    {
                        ProductId = productId.ToString(),
                        Sku = "SKU-ENRICH-1",
                        Materials = new AiProposedList
                        {
                            Value = ["oro"], Confidence = 0.9, Source = AiFieldSource.Inferred
                        },
                        ColorTags = new AiProposedList { Confidence = 0.9, Source = AiFieldSource.Inferred },
                        StyleTags = new AiProposedList { Confidence = 0.9, Source = AiFieldSource.Inferred },
                        OccasionTags = new AiProposedList { Confidence = 0.9, Source = AiFieldSource.Inferred }
                    }
                ],
                PromptVersion = "v1",
                Usage = new AiUsage()
            };
        }
    }

    private async Task AssertProfileCountAsync(int expected, string because)
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        (await context.ProductAiProfiles.CountAsync()).Should().Be(expected, because);
    }

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

    private async Task<HttpClient> AuthenticateAsync(string username, string password)
    {
        var login = await _client.PostAsJsonAsync(
            "/api/auth/login",
            new LoginRequest { Username = username, Password = password });
        login.EnsureSuccessStatusCode();

        var authenticated = _factory.CreateClient();
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
