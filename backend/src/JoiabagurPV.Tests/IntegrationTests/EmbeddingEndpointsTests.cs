using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.DTOs.Users;
using JoiabagurPV.API.Filters;
using JoiabagurPV.Tests.TestHelpers;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for withdrawn embedding endpoints under /api/image-recognition/embeddings.
/// </summary>
[Collection(IntegrationTestCollection.Name)]
public class EmbeddingEndpointsTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;
    private HttpClient? _adminClient;
    private HttpClient? _operatorClient;

    private const string BaseUrl = "/api/image-recognition/embeddings";

    public EmbeddingEndpointsTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();
        _adminClient = await CreateAuthenticatedClientAsync("admin", "Admin123!");
        _operatorClient = await CreateAuthenticatedClientAsync("operator", "Operator123!");
    }

    public Task DisposeAsync() => Task.CompletedTask;

    private async Task<HttpClient> CreateAuthenticatedClientAsync(string username, string password)
    {
        if (username != "admin")
        {
            var adminClient = await CreateAuthenticatedClientAsync("admin", "Admin123!");
            var createRequest = new CreateUserRequest
            {
                Username = username,
                Password = password,
                FirstName = "Test",
                LastName = "Operator",
                Role = "Operator"
            };
            await adminClient.PostAsJsonAsync("/api/users", createRequest);
        }

        var loginRequest = new LoginRequest { Username = username, Password = password };
        var loginResponse = await _client.PostAsJsonAsync("/api/auth/login", loginRequest);
        loginResponse.EnsureSuccessStatusCode();

        var cookies = loginResponse.Headers.GetValues("Set-Cookie").ToList();
        var authClient = _factory.CreateClient();
        foreach (var cookie in cookies)
        {
            var parts = cookie.Split(';')[0].Split('=');
            if (parts.Length == 2)
                authClient.DefaultRequestHeaders.Add("Cookie", $"{parts[0]}={parts[1]}");
        }
        return authClient;
    }

    private static async Task AssertWithdrawnAsync(HttpResponseMessage response)
    {
        response.StatusCode.Should().Be(HttpStatusCode.Gone);
        var body = await response.Content.ReadFromJsonAsync<JsonElement>();
        body.GetProperty("code").GetString().Should().Be(ImageRecognitionWithdrawnFilter.WithdrawalCode);
        body.GetProperty("message").GetString().Should().Contain("retirado");
    }

    [Fact]
    public async Task SaveEmbedding_WithValidRequest_ReturnsGone()
    {
        var vector = TestDataGenerator.CreateEmbeddingVector(1280);
        var request = new { photoId = Guid.NewGuid(), productId = Guid.NewGuid(), sku = "S", vector };

        var response = await _adminClient!.PostAsJsonAsync(BaseUrl, request);
        await AssertWithdrawnAsync(response);
    }

    [Fact]
    public async Task SaveEmbedding_Unauthenticated_Returns401()
    {
        var request = new { photoId = Guid.NewGuid(), productId = Guid.NewGuid(), sku = "S", vector = new float[1280] };

        var anonymousClient = _factory.CreateClient();
        var response = await anonymousClient.PostAsJsonAsync(BaseUrl, request);
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task SaveEmbedding_AsOperator_ReturnsGone()
    {
        var request = new { photoId = Guid.NewGuid(), productId = Guid.NewGuid(), sku = "S", vector = new float[1280] };

        var response = await _operatorClient!.PostAsJsonAsync(BaseUrl, request);
        await AssertWithdrawnAsync(response);
    }

    [Fact]
    public async Task DeleteEmbedding_WhenExists_ReturnsGone()
    {
        var response = await _adminClient!.DeleteAsync($"{BaseUrl}/{Guid.NewGuid()}");
        await AssertWithdrawnAsync(response);
    }

    [Fact]
    public async Task DeleteAllEmbeddings_ReturnsGone()
    {
        var response = await _adminClient!.DeleteAsync(BaseUrl);
        await AssertWithdrawnAsync(response);
    }

    [Fact]
    public async Task GetAllEmbeddings_WhenEmpty_ReturnsGone()
    {
        var response = await _operatorClient!.GetAsync(BaseUrl);
        await AssertWithdrawnAsync(response);
    }

    [Fact]
    public async Task GetAllEmbeddings_Unauthenticated_Returns401()
    {
        var anonymousClient = _factory.CreateClient();
        var response = await anonymousClient.GetAsync(BaseUrl);
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task GetEmbeddingsStatus_WhenEmpty_ReturnsGone()
    {
        var response = await _operatorClient!.GetAsync($"{BaseUrl}/status");
        await AssertWithdrawnAsync(response);
    }

    [Fact]
    public async Task GetEmbeddingsStatus_Unauthenticated_Returns401()
    {
        var anonymousClient = _factory.CreateClient();
        var response = await anonymousClient.GetAsync($"{BaseUrl}/status");
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }
}
