using System.Net;
using System.Net.Http.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for the jbg-ai status endpoint (C17).
/// </summary>
/// <remarks>
/// Two things are worth running against the real host rather than a unit test: the authorization
/// boundary, because the report describes infrastructure and an operator has no business seeing
/// it, and the serialized body, because "does not leak a credential" is a property of what
/// actually reaches the wire, not of what the code intended to put there.
/// </remarks>
[Collection(IntegrationTestCollection.Name)]
public class AiHealthControllerTests : IAsyncLifetime
{
    private const string Endpoint = "/api/ai/health";

    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;

    private PointOfSale _pos = null!;

    public AiHealthControllerTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();

        using var mother = new TestDataMother(_factory.Services);

        _pos = await mother.PointOfSale()
            .WithCode("HEALTH-POS")
            .WithName("Health Point of Sale")
            .WithAddress("Test Address")
            // Pinned: the generator produces phone numbers of varying length and the column is
            // varchar(20), so leaving it to chance makes the suite fail intermittently.
            .WithPhone("600123456")
            .CreateAsync();

        await mother.User()
            .WithUsername("healthoperator")
            .AsOperator()
            .AssignedTo(_pos.Id)
            .CreateAsync();
    }

    public Task DisposeAsync() => Task.CompletedTask;

    /// <summary>
    /// Asks the factory for a fresh client on purpose. The one this class holds has performed
    /// logins, so it carries their cookies and is not anonymous — the trap that turns a genuine
    /// 401 assertion into a passing 403.
    /// </summary>
    [Fact]
    public async Task AiHealth_ReturnsUnauthorized_ForAnonymousRequest()
    {
        var anonymous = _factory.CreateClient();

        var response = await anonymous.GetAsync(Endpoint);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    /// <summary>
    /// The report says how many documents are indexed, whether a database is reachable and
    /// whether a provider credential is configured. None of that is an operator's concern.
    /// </summary>
    [Fact]
    public async Task AiHealth_ReturnsForbidden_ForOperatorRole()
    {
        var operatorClient = await AuthenticateAsync("healthoperator", "Test123!");

        var response = await operatorClient.GetAsync(Endpoint);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    /// <summary>
    /// The response is served to a browser, so anything in it is one screenshot away from being
    /// public. This asserts on the RAW body rather than on the deserialized object: a leak would
    /// arrive as an extra field the model does not declare, which deserializing would silently
    /// discard and hide.
    /// </summary>
    [Fact]
    public async Task AiHealth_DoesNotLeakConnectionStringOrApiKey()
    {
        using var factory = _factory.WithWebHostBuilder(builder =>
            builder.ConfigureServices(services => services.AddScoped<IAiGatewayClient>(
                _ => new StubHealthGateway())));

        var admin = await AuthenticateAgainstAsync(factory, "admin", "Admin123!");

        var response = await admin.GetAsync(Endpoint);
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var raw = await response.Content.ReadAsStringAsync();

        raw.Should().NotContain("Host=", "a connection string must never reach a browser");
        raw.Should().NotContain("Password=");
        raw.Should().NotContain("Username=");
        raw.Should().NotContain("jbg-demo-postgres", "the database hostname is infrastructure detail");
        raw.Should().NotContain("sk-", "not one fragment of a provider key");
        raw.Should().NotContain(AiGatewayTestSecrets.SigningSecretFragment,
            "the internal signing secret is shared with jbg-ai and must stay on the server");

        // What it does say, which is the whole point of the endpoint existing.
        var body = (await response.Content.ReadFromJsonAsync<AiHealthResponse>())!;
        body.Database.Should().Be("ok");
        body.Index.Documents.Should().Be(1200);
        body.Provider.Should().Be("configured", "presence of the credential, never its value");
    }

    // ---------------------------------------------------------------- helpers

    /// <summary>A gateway that answers a healthy report without reaching anything.</summary>
    private sealed class StubHealthGateway : IAiGatewayClient
    {
        public Task<AiSearchResponse> SearchAsync(
            AiSearchRequest request, AiCallScope scope, CancellationToken cancellationToken = default) =>
            throw new NotSupportedException();

        public Task<AiEnrichResponse> EnrichAsync(
            AiEnrichRequest request, AiCallScope scope, CancellationToken cancellationToken = default) =>
            throw new NotSupportedException();

        public Task<AiFamilySuggestResponse> SuggestFamiliesAsync(
            AiFamilySuggestRequest request, AiCallScope scope, CancellationToken cancellationToken = default) =>
            throw new NotSupportedException();

        public Task<AiHealthResponse> HealthAsync(CancellationToken cancellationToken = default) =>
            Task.FromResult(new AiHealthResponse
            {
                Status = "OK",
                Version = "0.1.0",
                Database = "ok",
                Provider = "configured",
                Index = new AiHealthIndex
                {
                    Documents = 1200,
                    Model = "openai/text-embedding-3-small",
                    ConfiguredModel = "openai/text-embedding-3-small",
                    Status = "ok"
                }
            });
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

/// <summary>
/// Fragments a leak would contain, kept out of the assertion body so the assertion reads as an
/// assertion rather than as a list of secrets.
/// </summary>
internal static class AiGatewayTestSecrets
{
    /// <summary>Part of the signing secret the test host configures for the AI gateway.</summary>
    public const string SigningSecretFragment = "0123456789abcdefghij";
}
