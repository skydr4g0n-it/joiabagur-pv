using FluentAssertions;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.DTOs.Users;
using JoiabagurPV.API.Filters;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for withdrawn ImageRecognitionController endpoints.
/// </summary>
[Collection(IntegrationTestCollection.Name)]
public class ImageRecognitionControllerTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;
    private HttpClient? _adminClient;
    private HttpClient? _operatorClient;

    public ImageRecognitionControllerTests(ApiWebApplicationFactory factory)
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
                LastName = "User",
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
            var cookieParts = cookie.Split(';')[0].Split('=');
            if (cookieParts.Length == 2)
            {
                authClient.DefaultRequestHeaders.Add("Cookie", $"{cookieParts[0]}={cookieParts[1]}");
            }
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

    [Theory]
    [InlineData("/api/image-recognition/model/metadata")]
    [InlineData("/api/image-recognition/model/health")]
    [InlineData("/api/image-recognition/model/versions")]
    [InlineData("/api/image-recognition/model")]
    [InlineData("/api/image-recognition/model/class-labels")]
    [InlineData("/api/image-recognition/training-dataset")]
    [InlineData("/api/image-recognition/embeddings")]
    [InlineData("/api/image-recognition/embeddings/status")]
    public async Task GetRoute_AsAdmin_ReturnsGone(string path)
    {
        var response = await _adminClient!.GetAsync(path);
        await AssertWithdrawnAsync(response);
    }

    [Fact]
    public async Task GetModelHealth_AsOperator_ReturnsGone()
    {
        var response = await _operatorClient!.GetAsync("/api/image-recognition/model/health");
        await AssertWithdrawnAsync(response);
    }

    [Fact]
    public async Task InitiateRetraining_AsOperator_ReturnsGone()
    {
        var response = await _operatorClient!.PostAsync("/api/image-recognition/retrain", null);
        await AssertWithdrawnAsync(response);
    }

    [Fact]
    public async Task GetTrainingDataset_AsOperator_ReturnsGone()
    {
        var response = await _operatorClient!.GetAsync("/api/image-recognition/training-dataset");
        await AssertWithdrawnAsync(response);
    }

    [Fact]
    public async Task GetModelMetadata_Unauthenticated_ReturnsUnauthorized()
    {
        var anonymousClient = _factory.CreateClient();
        var response = await anonymousClient.GetAsync("/api/image-recognition/model/metadata");
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task GetModelHealth_Unauthenticated_ReturnsUnauthorized()
    {
        var anonymousClient = _factory.CreateClient();
        var response = await anonymousClient.GetAsync("/api/image-recognition/model/health");
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task PostRetrain_AsAdmin_ReturnsGone()
    {
        var response = await _adminClient!.PostAsync("/api/image-recognition/retrain", null);
        await AssertWithdrawnAsync(response);
    }

    [Fact]
    public async Task GetEmbeddings_AsOperator_ReturnsGone()
    {
        var response = await _operatorClient!.GetAsync("/api/image-recognition/embeddings");
        await AssertWithdrawnAsync(response);
    }
}
