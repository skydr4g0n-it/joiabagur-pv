using System.Net;
using System.Net.Http.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Tests.TestHelpers.Mothers;

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
