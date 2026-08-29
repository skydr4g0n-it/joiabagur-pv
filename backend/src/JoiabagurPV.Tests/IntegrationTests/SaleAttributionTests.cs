using System.Net;
using System.Net.Http.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.DTOs.Sales;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for attributing a sale to the assisted search that originated it.
/// </summary>
/// <remarks>
/// <para>
/// These run against a real PostgreSQL because the whole point of the feature is what ends up
/// in the column: the telemetry capability declares that a sale carries its originating search,
/// and until this change there was no path through the API by which that could ever happen.
/// </para>
/// <para>
/// The degradation cases matter more than the happy path. Attribution is analytics, so an
/// unusable identifier must leave the sale untouched rather than reject it — a till that
/// refuses a sale over a measurement is worse than a measurement that is missing.
/// </para>
/// </remarks>
[Collection(IntegrationTestCollection.Name)]
public class SaleAttributionTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;

    private PointOfSale _pos = null!;
    private Product _product = null!;
    private Product _secondProduct = null!;
    private PaymentMethod _paymentMethod = null!;
    private User _seller = null!;
    private HttpClient _sellerClient = null!;

    public SaleAttributionTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();

        using var mother = new TestDataMother(_factory.Services);

        _pos = await mother.PointOfSale()
            .WithCode("ATTRIBUTION-POS")
            .WithName("Attribution Point of Sale")
            .WithAddress("Test Address")
            // Pinned: the generator produces phone numbers of varying length and the column is
            // varchar(20), so leaving it to chance makes the suite fail intermittently.
            .WithPhone("600123456")
            .CreateAsync();

        _paymentMethod = await mother.Context.PaymentMethods.FirstAsync(pm => pm.Code == "CASH");

        mother.Context.PointOfSalePaymentMethods.Add(new PointOfSalePaymentMethod
        {
            Id = Guid.NewGuid(),
            PointOfSaleId = _pos.Id,
            PaymentMethodId = _paymentMethod.Id,
            CreatedAt = DateTime.UtcNow
        });
        await mother.Context.SaveChangesAsync();

        _product = await mother.Product()
            .WithSku("SKU-ATTRIBUTION-1")
            .WithName("Anillo de plata")
            .WithPrice(100.00m)
            .CreateAsync();

        _secondProduct = await mother.Product()
            .WithSku("SKU-ATTRIBUTION-2")
            .WithName("Pendientes de plata")
            .WithPrice(40.00m)
            .CreateAsync();

        await mother.Inventory()
            .WithProduct(_product.Id)
            .WithPointOfSale(_pos.Id)
            .WithQuantity(10)
            .CreateAsync();

        await mother.Inventory()
            .WithProduct(_secondProduct.Id)
            .WithPointOfSale(_pos.Id)
            .WithQuantity(10)
            .CreateAsync();

        _seller = await mother.User()
            .WithUsername("attributionseller")
            .AsOperator()
            .AssignedTo(_pos.Id)
            .CreateAsync();

        _sellerClient = await AuthenticateAsync("attributionseller", "Test123!");
    }

    public Task DisposeAsync() => Task.CompletedTask;

    [Fact]
    public async Task CreateSale_WithOwnSearchEvent_StoresAttribution()
    {
        var eventId = await RecordSearchAsync(_seller.Id);

        var response = await _sellerClient.PostAsJsonAsync("/api/sales", NewSaleRequest(eventId));

        response.StatusCode.Should().Be(HttpStatusCode.Created);
        (await LoadOnlySaleAsync()).SearchEventId.Should().Be(eventId);
    }

    [Fact]
    public async Task CreateSale_WithUnknownSearchEvent_StoresNullAttribution()
    {
        var response = await _sellerClient.PostAsJsonAsync(
            "/api/sales", NewSaleRequest(Guid.NewGuid()));

        response.StatusCode.Should().Be(HttpStatusCode.Created,
            "attribution is analytics: an identifier that cannot be resolved must never turn "
            + "into a refused sale");

        (await LoadOnlySaleAsync()).SearchEventId.Should().BeNull();
    }

    [Fact]
    public async Task CreateSale_WithSearchEventOfAnotherUser_StoresNullAttribution()
    {
        using var mother = new TestDataMother(_factory.Services);
        var stranger = await mother.User()
            .WithUsername("attributionstranger")
            .AsOperator()
            .AssignedTo(_pos.Id)
            .CreateAsync();

        var foreignEventId = await RecordSearchAsync(stranger.Id);

        var response = await _sellerClient.PostAsJsonAsync(
            "/api/sales", NewSaleRequest(foreignEventId));

        response.StatusCode.Should().Be(HttpStatusCode.Created);

        (await LoadOnlySaleAsync()).SearchEventId.Should().BeNull(
            "a search event records what one specific person did, so attributing a sale to "
            + "somebody else's search would corrupt the adoption metrics without leaving a trace");
    }

    [Fact]
    public async Task CreateSale_WithUnusableSearchEvent_LeavesTheRestOfTheSaleUntouched()
    {
        var stockBefore = await LoadQuantityAsync(_product.Id);

        // Two sales of the same product, one after the other: the first with no reference at all,
        // the second with one that cannot be resolved. Everything except the attribution has to
        // come out identical. Deleting the first instead would not work — a sale is referenced by
        // its inventory movement — and comparing against a different product would compare prices.
        var withoutAttribution = await _sellerClient.PostAsJsonAsync(
            "/api/sales", NewSaleRequest(searchEventId: null));
        withoutAttribution.StatusCode.Should().Be(HttpStatusCode.Created);

        var withUnusableAttribution = await _sellerClient.PostAsJsonAsync(
            "/api/sales", NewSaleRequest(Guid.NewGuid()));
        withUnusableAttribution.StatusCode.Should().Be(HttpStatusCode.Created);

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        var sales = await context.Sales.AsNoTracking()
            .OrderBy(s => s.SaleDate)
            .ToListAsync();

        sales.Should().HaveCount(2);
        var baseline = sales[0];
        var degraded = sales[1];

        degraded.Price.Should().Be(baseline.Price);
        degraded.Quantity.Should().Be(baseline.Quantity);
        degraded.PriceWasOverridden.Should().Be(baseline.PriceWasOverridden);
        degraded.OriginalProductPrice.Should().Be(baseline.OriginalProductPrice);
        degraded.SearchEventId.Should().BeNull();

        (await LoadQuantityAsync(_product.Id)).Should().Be(stockBefore - 4,
            "the stock movement must be exactly what it would have been with no reference at all");

        var movements = await context.InventoryMovements.AsNoTracking()
            .Where(m => sales.Select(s => s.Id).Contains(m.SaleId!.Value))
            .ToListAsync();
        movements.Should().HaveCount(2, "an unusable attribution must not skip the stock movement");
    }

    [Fact]
    public async Task BulkSale_AttributesEachLineToItsOwnSearchEvent()
    {
        var firstEventId = await RecordSearchAsync(_seller.Id);
        var secondEventId = await RecordSearchAsync(_seller.Id);

        var request = new CreateBulkSalesRequest
        {
            PointOfSaleId = _pos.Id,
            PaymentMethodId = _paymentMethod.Id,
            Lines =
            [
                new BulkSaleLineRequest { ProductId = _product.Id, Quantity = 1, SearchEventId = firstEventId },
                new BulkSaleLineRequest { ProductId = _secondProduct.Id, Quantity = 1, SearchEventId = secondEventId },
                new BulkSaleLineRequest { ProductId = _product.Id, Quantity = 1 }
            ]
        };

        var response = await _sellerClient.PostAsJsonAsync("/api/sales/bulk", request);
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var sales = await context.Sales.AsNoTracking().ToListAsync();

        sales.Should().HaveCount(3);
        sales.Count(s => s.SearchEventId == firstEventId).Should().Be(1);
        sales.Count(s => s.SearchEventId == secondEventId).Should().Be(1);
        sales.Count(s => s.SearchEventId == null).Should().Be(1,
            "a line with no search behind it stays valid and unattributed");
    }

    [Fact]
    public async Task BulkSale_WithUnknownSearchEventOnOneLine_StillCompletesEveryLine()
    {
        var request = new CreateBulkSalesRequest
        {
            PointOfSaleId = _pos.Id,
            PaymentMethodId = _paymentMethod.Id,
            Lines =
            [
                new BulkSaleLineRequest { ProductId = _product.Id, Quantity = 1, SearchEventId = Guid.NewGuid() },
                new BulkSaleLineRequest { ProductId = _secondProduct.Id, Quantity = 1 }
            ]
        };

        var response = await _sellerClient.PostAsJsonAsync("/api/sales/bulk", request);

        response.StatusCode.Should().Be(HttpStatusCode.Created,
            "the checkout is atomic, so a degrading attribution on one line must not be able to "
            + "roll the whole operation back");

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var sales = await context.Sales.AsNoTracking().ToListAsync();

        sales.Should().HaveCount(2);
        sales.Should().OnlyContain(s => s.SearchEventId == null);
    }

    private CreateSaleRequest NewSaleRequest(Guid? searchEventId) => new()
    {
        ProductId = _product.Id,
        PointOfSaleId = _pos.Id,
        PaymentMethodId = _paymentMethod.Id,
        Quantity = 2,
        SearchEventId = searchEventId
    };

    /// <summary>
    /// Writes a search event through the real service, the way the search endpoint does.
    /// </summary>
    private async Task<Guid> RecordSearchAsync(Guid userId)
    {
        using var scope = _factory.Services.CreateScope();
        var service = scope.ServiceProvider.GetRequiredService<IProductSearchEventService>();

        var id = await service.RecordSearchAsync(new RecordSearchRequest
        {
            Scope = AiCallScope.ForPointOfSale(userId, "Operator", _pos.Id),
            Query = "anillo de plata para regalar",
            Filters = new AiSearchFilters(),
            DisplayedResults =
            [
                new AiSearchResult { ProductId = _product.Id.ToString(), Sku = _product.SKU, Score = 0.9 }
            ],
            Origin = SearchOrigin.Assisted
        });

        id.Should().NotBeNull();
        return id!.Value;
    }

    private async Task<Sale> LoadOnlySaleAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        return await context.Sales.AsNoTracking().SingleAsync();
    }

    private async Task<int> LoadQuantityAsync(Guid productId)
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var inventory = await context.Inventories.AsNoTracking()
            .FirstAsync(i => i.ProductId == productId && i.PointOfSaleId == _pos.Id);
        return inventory.Quantity;
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
