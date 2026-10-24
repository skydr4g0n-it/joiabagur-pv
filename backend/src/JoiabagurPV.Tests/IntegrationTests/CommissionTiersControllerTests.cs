using FluentAssertions;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.DTOs.PointOfSales;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;

namespace JoiabagurPV.Tests.IntegrationTests;

[Collection(IntegrationTestCollection.Name)]
public class CommissionTiersControllerTests : IAsyncLifetime
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    };

    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;
    private HttpClient? _adminClient;
    private HttpClient? _operatorClient;
    private PointOfSale _pos = null!;

    public CommissionTiersControllerTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();
        _adminClient = await CreateAuthenticatedClientAsync("admin", "Admin123!");

        using var mother = new TestDataMother(_factory.Services);
        _pos = await mother.PointOfSale()
            .WithCode("COM-POS")
            .WithName("Commission POS")
            .CreateAsync();

        await mother.User()
            .WithUsername("comoperator")
            .WithName("Com", "Operator")
            .AsOperator()
            .AssignedTo(_pos.Id)
            .CreateAsync();

        _operatorClient = await CreateAuthenticatedClientAsync("comoperator", "Test123!");
    }

    public Task DisposeAsync() => Task.CompletedTask;

    private async Task<HttpClient> CreateAuthenticatedClientAsync(string username, string password)
    {
        var loginResponse = await _client.PostAsJsonAsync("/api/auth/login", new LoginRequest { Username = username, Password = password });
        loginResponse.EnsureSuccessStatusCode();

        var authClient = _factory.CreateClient();
        foreach (var cookie in loginResponse.Headers.GetValues("Set-Cookie"))
        {
            var cookieParts = cookie.Split(';')[0].Split('=');
            if (cookieParts.Length == 2 && cookieParts[0] == "access_token")
                authClient.DefaultRequestHeaders.Add("Cookie", $"access_token={cookieParts[1]}");
        }

        return authClient;
    }

    [Fact]
    public async Task PutCommissionTiers_AsAdmin_ValidRanges_Returns200()
    {
        var request = new ReplaceCommissionTiersRequest
        {
            Tiers =
            [
                new CommissionTierInputDto { MinAmountInclusive = 0, MaxAmountInclusive = 20000, CommissionPercent = 20 },
                new CommissionTierInputDto { MinAmountInclusive = 20001, MaxAmountInclusive = null, CommissionPercent = 30 }
            ]
        };

        var response = await _adminClient!.PutAsJsonAsync(
            $"/api/point-of-sales/{_pos.Id}/commission-tiers", request, JsonOptions);
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var getResponse = await _adminClient.GetAsync($"/api/point-of-sales/{_pos.Id}/commission-tiers");
        var tiers = await getResponse.Content.ReadFromJsonAsync<List<CommissionTierDto>>();
        tiers.Should().HaveCount(2);
    }

    [Fact]
    public async Task PutCommissionTiers_InvalidRanges_Returns400()
    {
        var request = new ReplaceCommissionTiersRequest
        {
            Tiers =
            [
                new CommissionTierInputDto { MinAmountInclusive = 100, MaxAmountInclusive = 500, CommissionPercent = 10 }
            ]
        };

        var response = await _adminClient!.PutAsJsonAsync(
            $"/api/point-of-sales/{_pos.Id}/commission-tiers", request, JsonOptions);
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task GetCommissionTiers_AsOperator_Returns403()
    {
        var response = await _operatorClient!.GetAsync($"/api/point-of-sales/{_pos.Id}/commission-tiers");
        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    [Fact]
    public async Task PutCommissionTiers_AsOperator_Returns403()
    {
        var request = new ReplaceCommissionTiersRequest { Tiers = [] };
        var response = await _operatorClient!.PutAsJsonAsync(
            $"/api/point-of-sales/{_pos.Id}/commission-tiers", request, JsonOptions);
        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }
}
