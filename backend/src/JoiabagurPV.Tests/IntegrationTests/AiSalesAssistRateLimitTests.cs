using System.Net;
using System.Net.Http.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Tests.TestHelpers;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for the rate policy of the generative route (C34).
/// </summary>
/// <remarks>
/// Its own host, like the search policy's: the shared factory raises the limit out of the way,
/// and a policy nobody can reach is a policy nobody can test. This one sets a limit of two.
/// </remarks>
[Collection(IntegrationTestCollection.Name)]
public class AiSalesAssistRateLimitTests : IAsyncLifetime
{
    private const int PermitLimit = 2;

    private readonly ApiWebApplicationFactory _sharedFactory;
    private readonly HttpClient _warmUpClient;
    private readonly CountingGateway _gateway = new();

    private WebApplicationFactory<Program> _factory = null!;
    private PointOfSale _pos = null!;
    private Product _product = null!;
    private HttpClient _firstOperator = null!;
    private HttpClient _secondOperator = null!;

    public AiSalesAssistRateLimitTests(ApiWebApplicationFactory sharedFactory)
    {
        _sharedFactory = sharedFactory;

        // Builds the shared host, which applies the migrations before the reset below.
        _warmUpClient = sharedFactory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        await _sharedFactory.ResetDatabaseAsync();

        using var mother = new TestDataMother(_sharedFactory.Services);

        _pos = await mother.PointOfSale()
            .WithCode("ASSIST-RATE").WithName("Rate Limited Card")
            .WithAddress("Test Address").WithPhone("600123456").CreateAsync();

        _product = await mother.Product().WithSku("SKU-ASSIST-RATE").WithName("Anillo").WithPrice(30m).CreateAsync();

        await mother.Inventory().WithProduct(_product.Id).WithPointOfSale(_pos.Id).WithQuantity(3).CreateAsync();

        await mother.User().WithUsername("assistone").AsOperator().AssignedTo(_pos.Id).CreateAsync();
        await mother.User().WithUsername("assisttwo").AsOperator().AssignedTo(_pos.Id).CreateAsync();

        // The window is stretched so the allowance cannot refill between the requests of one test.
        _factory = _sharedFactory.WithWebHostBuilder(builder =>
        {
            builder.UseSetting("AiSalesAssist:EnabledByDefault", "true");
            builder.UseSetting("AiSalesAssist:RateLimitPermitLimit", PermitLimit.ToString());
            builder.UseSetting("AiSalesAssist:RateLimitWindowSeconds", "300");
            builder.ConfigureServices(services => services.AddScoped<IAiGatewayClient>(_ => _gateway));
        });

        _firstOperator = await AuthenticateAsync("assistone");
        _secondOperator = await AuthenticateAsync("assisttwo");
    }

    public Task DisposeAsync()
    {
        _factory?.Dispose();
        return Task.CompletedTask;
    }

    [Fact]
    public async Task SalesAssist_WhenRateLimitExceeded_Returns429WithoutCallingAi()
    {
        for (var i = 0; i < PermitLimit; i++)
        {
            (await AssistAsync(_firstOperator)).StatusCode.Should().Be(HttpStatusCode.OK);
        }

        var rejected = await AssistAsync(_firstOperator);

        rejected.StatusCode.Should().Be(HttpStatusCode.TooManyRequests,
            "throttled is distinguishable from AI unavailable, which is a 200");
        (await rejected.Content.ReadAsStringAsync()).Should().NotContain("aiAvailable");
        _gateway.AssistCalls.Should().Be(PermitLimit, "the rejected request never reached the AI");
    }

    [Fact]
    public async Task SalesAssist_RateLimitIsPartitionedByUser_NotByNetworkOrigin()
    {
        for (var i = 0; i < PermitLimit; i++)
        {
            await AssistAsync(_firstOperator);
        }

        (await AssistAsync(_firstOperator)).StatusCode.Should().Be(HttpStatusCode.TooManyRequests);

        // Same host, same network origin: if the limiter partitioned by address this would be 429.
        (await AssistAsync(_secondOperator)).StatusCode.Should().Be(HttpStatusCode.OK);
    }

    /// <summary>
    /// Substitutes call no model and ride on the search policy: exhausting the generative
    /// allowance must not take them down with it.
    /// </summary>
    [Fact]
    public async Task SalesAssist_ExhaustedAllowance_DoesNotThrottleSubstitutes()
    {
        for (var i = 0; i <= PermitLimit; i++)
        {
            await AssistAsync(_firstOperator);
        }

        var substitutes = await _firstOperator.GetAsync(
            $"/api/ai/products/{_product.Id}/substitutes?pointOfSaleId={_pos.Id}");

        substitutes.StatusCode.Should().Be(HttpStatusCode.OK);
        _gateway.SubstitutesCalls.Should().Be(1);
    }

    private Task<HttpResponseMessage> AssistAsync(HttpClient client) =>
        client.PostAsJsonAsync(
            $"/api/ai/products/{_product.Id}/sales-assist",
            new SalesAssistRequest { PointOfSaleId = _pos.Id });

    private async Task<HttpClient> AuthenticateAsync(string username)
    {
        var client = _factory.CreateClient();
        var response = await client.PostAsJsonAsync(
            "/api/auth/login", new LoginRequest { Username = username, Password = "Test123!" });
        response.EnsureSuccessStatusCode();
        return client;
    }

    private sealed class CountingGateway : ThrowingAiGatewayClient
    {
        private int _assistCalls;
        private int _substitutesCalls;

        public int AssistCalls => _assistCalls;

        public int SubstitutesCalls => _substitutesCalls;

        public override Task<AiAssistSaleResponse> AssistSaleAsync(
            AiAssistSaleRequest request, AiCallScope scope, CancellationToken cancellationToken = default)
        {
            Interlocked.Increment(ref _assistCalls);
            return Task.FromResult(new AiAssistSaleResponse
            {
                Intent = "product_pitch",
                Groups = [new AiAssistGroup { Members = [new AiAssistGroupMember { ProductId = request.ProductId!, Sku = "SKU-ASSIST-RATE" }] }],
                Pitch = "",
                PromptVersion = null
            });
        }

        public override Task<AiSubstitutesResponse> SubstitutesAsync(
            AiSubstitutesRequest request, AiCallScope scope, CancellationToken cancellationToken = default)
        {
            Interlocked.Increment(ref _substitutesCalls);
            return Task.FromResult(new AiSubstitutesResponse());
        }
    }
}
