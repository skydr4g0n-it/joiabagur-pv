using System.Net;
using System.Net.Http.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for the assisted-search telemetry endpoint and its persistence.
/// </summary>
/// <remarks>
/// These run against a real PostgreSQL, because the three things worth proving here are all
/// database behaviour: that ownership is enforced over a row that really exists, that the
/// delete rule really nulls a sale's attribution instead of blocking or cascading, and that the
/// whole two-step write round-trips through jsonb columns intact.
/// </remarks>
[Collection(IntegrationTestCollection.Name)]
public class AiSearchEventsControllerTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;

    private PointOfSale _pos = null!;
    private Product _product = null!;
    private User _owner = null!;
    private HttpClient _ownerClient = null!;

    public AiSearchEventsControllerTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();

        using var mother = new TestDataMother(_factory.Services);

        _pos = await mother.PointOfSale()
            .WithCode("TELEMETRY-POS")
            .WithName("Telemetry Point of Sale")
            .WithAddress("Test Address")
            // Pinned: the generator produces phone numbers of varying length and the column is
            // varchar(20), so leaving it to chance makes the suite fail intermittently.
            .WithPhone("600123456")
            .CreateAsync();

        _product = await mother.Product().WithSku("SKU-TELEMETRY-1").CreateAsync();

        _owner = await mother.User()
            .WithUsername("searchowner")
            .AsOperator()
            .AssignedTo(_pos.Id)
            .CreateAsync();

        _ownerClient = await AuthenticateAsync("searchowner", "Test123!");
    }

    public Task DisposeAsync() => Task.CompletedTask;

    [Fact]
    public async Task RecordSelection_WhenOwnerSelectsAStoredResult_Returns204AndPersistsDerivedRank()
    {
        var eventId = await RecordSearchAsync(_owner.Id, [_product.Id, Guid.NewGuid()]);

        var response = await _ownerClient.PostAsJsonAsync(
            $"/api/ai/search-events/{eventId}/selection",
            new RecordSearchSelectionRequest { ProductId = _product.Id });

        response.StatusCode.Should().Be(HttpStatusCode.NoContent);

        var stored = await LoadEventAsync(eventId);
        stored.SelectedProductId.Should().Be(_product.Id);
        stored.SelectedFromRank.Should().Be(1);
        stored.SelectedAt.Should().NotBeNull();
    }

    [Fact]
    public async Task RecordSelection_WhenEventBelongsToAnotherUser_Returns403()
    {
        using var mother = new TestDataMother(_factory.Services);
        await mother.User().WithUsername("otheroperator").AsOperator().AssignedTo(_pos.Id).CreateAsync();
        var stranger = await AuthenticateAsync("otheroperator", "Test123!");

        var eventId = await RecordSearchAsync(_owner.Id, [_product.Id]);

        var response = await stranger.PostAsJsonAsync(
            $"/api/ai/search-events/{eventId}/selection",
            new RecordSearchSelectionRequest { ProductId = _product.Id });

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
        (await LoadEventAsync(eventId)).SelectedProductId.Should().BeNull();
    }

    [Fact]
    public async Task RecordSelection_WhenCallerIsAdminButNotOwner_Returns403()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var eventId = await RecordSearchAsync(_owner.Id, [_product.Id]);

        var response = await admin.PostAsJsonAsync(
            $"/api/ai/search-events/{eventId}/selection",
            new RecordSearchSelectionRequest { ProductId = _product.Id });

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden,
            "administrators bypass point-of-sale checks elsewhere by design, but a search event "
            + "records what one specific person did and nobody else may complete it");
        (await LoadEventAsync(eventId)).SelectedProductId.Should().BeNull();
    }

    [Fact]
    public async Task RecordSelection_WhenEventDoesNotExist_Returns404()
    {
        var response = await _ownerClient.PostAsJsonAsync(
            $"/api/ai/search-events/{Guid.NewGuid()}/selection",
            new RecordSearchSelectionRequest { ProductId = _product.Id });

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    [Fact]
    public async Task RecordSelection_WhenUnauthenticated_Returns401()
    {
        var eventId = await RecordSearchAsync(_owner.Id, [_product.Id]);

        // A client of its own: the shared one is what performs the logins, so it carries their
        // cookies and would not be anonymous at all.
        var anonymous = _factory.CreateClient();

        var response = await anonymous.PostAsJsonAsync(
            $"/api/ai/search-events/{eventId}/selection",
            new RecordSearchSelectionRequest { ProductId = _product.Id });

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task DeletingSearchEvent_NullsSaleAttribution_WithoutDeletingSale()
    {
        var eventId = await RecordSearchAsync(_owner.Id, [_product.Id]);

        using var mother = new TestDataMother(_factory.Services);
        var paymentMethod = await mother.Context.PaymentMethods.FirstAsync();
        var sale = await mother.Sale()
            .WithProduct(_product.Id)
            .WithPointOfSale(_pos.Id)
            .WithUser(_owner.Id)
            .WithPaymentMethod(paymentMethod.Id)
            .CreateAsync();

        using (var scope = _factory.Services.CreateScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var tracked = await context.Sales.FirstAsync(s => s.Id == sale.Id);
            tracked.SearchEventId = eventId;
            await context.SaveChangesAsync();

            // Raw SQL on purpose: this asserts the database constraint, not EF's in-memory
            // fixup, which would happily null the reference without the schema agreeing.
            await context.Database.ExecuteSqlRawAsync(
                @"DELETE FROM ""ProductSearchEvents"" WHERE ""Id"" = {0}", eventId);
        }

        using (var scope = _factory.Services.CreateScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var survivor = await context.Sales.AsNoTracking().FirstOrDefaultAsync(s => s.Id == sale.Id);

            survivor.Should().NotBeNull("purging telemetry must never destroy a sale");
            survivor!.SearchEventId.Should().BeNull("nor may it be blocked by one");
        }
    }

    [Fact]
    public async Task FullCycle_ProjectingARealGatewayResponse_RoundTripsThroughJsonbIntact()
    {
        // This test stands in for C16, which does not exist yet: it builds the payload out of a
        // real AiSearchResponse, exactly as C15 will. If the projection ever stops fitting in
        // roughly ten readable lines, the payload is wrong and the payload is what gets fixed.
        var response = new AiSearchResponse
        {
            Results =
            [
                new AiSearchResult { ProductId = Guid.NewGuid().ToString(), Sku = "SKU-A", Score = 0.91, MatchReasons = ["material:plata"] },
                new AiSearchResult { ProductId = _product.Id.ToString(), Sku = "SKU-TELEMETRY-1", Score = 0.72, MatchReasons = ["nombre"] }
            ],
            CandidatesReturned = 30,
            TraceId = "0af7651916cd43dd8448eb211c80319c",
            EffectivePosId = _pos.Id.ToString()
        };

        Guid? eventId;
        using (var scope = _factory.Services.CreateScope())
        {
            var service = scope.ServiceProvider.GetRequiredService<IProductSearchEventService>();
            eventId = await service.RecordSearchAsync(new RecordSearchRequest
            {
                Scope = AiCallScope.ForPointOfSale(_owner.Id, "Operator", _pos.Id),
                Query = "anillo de plata para regalo",
                Filters = new AiSearchFilters { Materials = ["plata"] },
                DisplayedResults = response.Results,
                Origin = SearchOrigin.Assisted,
                TraceId = response.TraceId,
                RetrievalMs = 180,
                TotalMs = 240
            });
        }

        eventId.Should().NotBeNull();

        await _ownerClient.PostAsJsonAsync(
            $"/api/ai/search-events/{eventId}/selection",
            new RecordSearchSelectionRequest { ProductId = _product.Id });

        var stored = await LoadEventAsync(eventId!.Value);
        stored.ResultsCount.Should().Be(2);
        stored.TraceId.Should().Be(response.TraceId);
        stored.RetrievalMs.Should().Be(180);
        stored.SearchOrigin.Should().Be(SearchOrigin.Assisted);
        stored.SelectedFromRank.Should().Be(2, "the chosen product was second in the displayed list");

        // Parsed rather than string-matched: jsonb normalises the document on the way in — it
        // reorders keys and rewrites the separators — so any assertion over the raw text would
        // be testing PostgreSQL's formatting rather than our projection.
        using var document = System.Text.Json.JsonDocument.Parse(stored.ResultsJson);
        var entries = document.RootElement.EnumerateArray().ToList();
        entries.Should().HaveCount(2);
        entries[1].GetProperty("rank").GetInt32().Should().Be(2);
        entries[1].GetProperty("sku").GetString().Should().Be("SKU-TELEMETRY-1");
        entries[1].GetProperty("productId").GetString().Should().Be(_product.Id.ToString());
        entries[0].GetProperty("score").GetDouble().Should().Be(0.91);
    }

    /// <summary>
    /// Writes a search event through the real service, the way C15 will.
    /// </summary>
    private async Task<Guid> RecordSearchAsync(Guid userId, IReadOnlyList<Guid> productIds)
    {
        using var scope = _factory.Services.CreateScope();
        var service = scope.ServiceProvider.GetRequiredService<IProductSearchEventService>();

        var id = await service.RecordSearchAsync(new RecordSearchRequest
        {
            Scope = AiCallScope.ForPointOfSale(userId, "Operator", _pos.Id),
            Query = "anillo de plata",
            Filters = new AiSearchFilters(),
            DisplayedResults = [.. productIds.Select((p, i) => new AiSearchResult
            {
                ProductId = p.ToString(),
                Sku = $"SKU-{i}",
                Score = 0.9 - (i * 0.1)
            })],
            Origin = SearchOrigin.Assisted
        });

        id.Should().NotBeNull();
        return id!.Value;
    }

    private async Task<ProductSearchEvent> LoadEventAsync(Guid id)
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        return await context.ProductSearchEvents.AsNoTracking().FirstAsync(e => e.Id == id);
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
