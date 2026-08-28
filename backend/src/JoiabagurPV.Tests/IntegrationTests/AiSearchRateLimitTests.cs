using System.Net;
using System.Net.Http.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for the request-rate policy of assisted search.
/// </summary>
/// <remarks>
/// <para>
/// These need their own host: the shared factory raises the limit out of the way so the policy
/// does not interfere with the rest of the suite, and a policy nobody can reach is a policy
/// nobody can test. This factory configures a limit of two.
/// </para>
/// <para>
/// The test that matters is the partition one. It fails if <c>UseRateLimiter</c> runs before
/// <c>UseAuthentication</c>, because the limiter then reads an empty principal and partitions by
/// network address — and every operator of a shop shares one behind the reverse proxy. That is
/// the defect this class exists to prevent from coming back: it produced no error, no failing
/// test and no log, only the wrong key.
/// </para>
/// </remarks>
[Collection(IntegrationTestCollection.Name)]
public class AiSearchRateLimitTests : IAsyncLifetime
{
    private const int PermitLimit = 2;

    private readonly ApiWebApplicationFactory _sharedFactory;
    private readonly HttpClient _warmUpClient;

    private WebApplicationFactory<Program> _factory = null!;
    private PointOfSale _pos = null!;
    private HttpClient _firstOperator = null!;
    private HttpClient _secondOperator = null!;

    public AiSearchRateLimitTests(ApiWebApplicationFactory sharedFactory)
    {
        _sharedFactory = sharedFactory;

        // Builds the shared host, which is what applies the migrations before the reset below.
        _warmUpClient = sharedFactory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        await _sharedFactory.ResetDatabaseAsync();

        using var mother = new TestDataMother(_sharedFactory.Services);

        _pos = await mother.PointOfSale()
            .WithCode("RATE-POS").WithName("Rate Limited Point of Sale")
            .WithAddress("Test Address").WithPhone("600123456").CreateAsync();

        var product = await mother.Product()
            .WithSku("SKU-RATE-1").WithName("Anillo de plata").WithPrice(30m).CreateAsync();

        await mother.Inventory().WithProduct(product.Id).WithPointOfSale(_pos.Id)
            .WithQuantity(3).CreateAsync();

        await mother.User().WithUsername("rateone").AsOperator().AssignedTo(_pos.Id).CreateAsync();
        await mother.User().WithUsername("ratetwo").AsOperator().AssignedTo(_pos.Id).CreateAsync();

        // Its own host, reusing the shared fixture's already-started container. The window is
        // stretched so the allowance cannot refill between the requests of one test.
        _factory = _sharedFactory.WithWebHostBuilder(builder =>
        {
            builder.UseSetting("AiSearch:RateLimitPermitLimit", PermitLimit.ToString());
            builder.UseSetting("AiSearch:RateLimitWindowSeconds", "300");
        });

        _firstOperator = await AuthenticateAsync("rateone");
        _secondOperator = await AuthenticateAsync("ratetwo");
    }

    public Task DisposeAsync()
    {
        _factory?.Dispose();
        return Task.CompletedTask;
    }

    [Fact]
    public async Task Search_WhenTheLimitIsExceeded_Returns429()
    {
        for (var i = 0; i < PermitLimit; i++)
        {
            (await SearchAsync(_firstOperator)).StatusCode.Should().Be(HttpStatusCode.OK);
        }

        var rejected = await SearchAsync(_firstOperator);

        rejected.StatusCode.Should().Be(HttpStatusCode.TooManyRequests);
    }

    [Fact]
    public async Task Search_RateLimitIsPartitionedByUser_NotByNetworkOrigin()
    {
        // The first operator exhausts their allowance.
        for (var i = 0; i < PermitLimit; i++)
        {
            (await SearchAsync(_firstOperator)).StatusCode.Should().Be(HttpStatusCode.OK);
        }

        (await SearchAsync(_firstOperator)).StatusCode.Should().Be(HttpStatusCode.TooManyRequests);

        // Their colleague, on the same host and therefore the same network origin, still has
        // theirs. If the limiter partitioned by address this would be 429 — which is precisely
        // what happens when it runs before authentication.
        var colleague = await SearchAsync(_secondOperator);

        colleague.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task Search_RateLimitRejection_IsNotReportedAsAiUnavailability()
    {
        for (var i = 0; i < PermitLimit; i++)
        {
            await SearchAsync(_firstOperator);
        }

        var rejected = await SearchAsync(_firstOperator);

        // A distinguishable status, not a successful body claiming the AI is down. The operator
        // is being throttled, which is a different thing and deserves a different message.
        rejected.StatusCode.Should().Be(HttpStatusCode.TooManyRequests);
        (await rejected.Content.ReadAsStringAsync()).Should().NotContain("aiAvailable");
    }

    // ---------------------------------------------------------------- helpers

    private Task<HttpResponseMessage> SearchAsync(HttpClient client) =>
        client.PostAsJsonAsync(
            "/api/ai/search",
            new AssistedSearchRequest { Query = "anillo plata", PointOfSaleId = _pos.Id });

    private async Task<HttpClient> AuthenticateAsync(string username)
    {
        var client = _factory.CreateClient();

        var response = await client.PostAsJsonAsync(
            "/api/auth/login",
            new LoginRequest { Username = username, Password = "Test123!" });

        response.EnsureSuccessStatusCode();
        return client;
    }
}
