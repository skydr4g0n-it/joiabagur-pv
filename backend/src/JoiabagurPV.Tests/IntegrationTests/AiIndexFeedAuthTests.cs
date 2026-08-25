using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using FluentAssertions;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Tests.TestHelpers;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Auth boundary of the indexing feeds. Every 401 here uses a fresh HTTP client: the shared
/// login client keeps cookies and would turn a genuine 401 into a 403 or 200.
/// </summary>
[Collection(IntegrationTestCollection.Name)]
public class AiIndexFeedAuthTests : IAsyncLifetime
{
    private const string Catalog = "/api/ai/index-feed/catalog";

    private readonly ApiWebApplicationFactory _factory;

    public AiIndexFeedAuthTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
    }

    public async Task InitializeAsync() => await _factory.ResetDatabaseAsync();

    public Task DisposeAsync() => Task.CompletedTask;

    [Fact]
    public async Task Feed_WithUserJwt_Returns401()
    {
        var loginClient = _factory.CreateClient();
        var login = await loginClient.PostAsJsonAsync(
            "/api/auth/login",
            new LoginRequest { Username = "admin", Password = "Admin123!" });
        login.EnsureSuccessStatusCode();

        var withCookie = _factory.CreateClient();
        foreach (var cookie in login.Headers.GetValues("Set-Cookie"))
        {
            var parts = cookie.Split(';')[0].Split('=');
            if (parts.Length == 2)
            {
                withCookie.DefaultRequestHeaders.Add("Cookie", $"{parts[0]}={parts[1]}");
            }
        }

        var response = await withCookie.GetAsync(Catalog);
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task Feed_WithC03Token_Returns401()
    {
        using var scope = _factory.Services.CreateScope();
        var factory = scope.ServiceProvider.GetRequiredService<IAiServiceTokenFactory>();
        var token = factory.Create(
            AiCallScope.ForCatalog(Guid.NewGuid(), "Administrator"),
            "trace-index-feed-auth");

        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

        var response = await client.GetAsync(Catalog);
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task Feed_MissingApiKey_Returns401()
    {
        var client = _factory.CreateClient();
        var response = await client.GetAsync(Catalog);
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task Feed_WrongApiKey_Returns401()
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Add(IndexFeedOptions.HeaderName, "wrong-index-feed-key-0123456789abcdef");

        var response = await client.GetAsync(Catalog);
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task Feed_WithValidApiKey_Returns200()
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Add(IndexFeedOptions.HeaderName, IndexFeedTestKeys.ApiKey);

        var response = await client.GetAsync(Catalog);
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }
}
