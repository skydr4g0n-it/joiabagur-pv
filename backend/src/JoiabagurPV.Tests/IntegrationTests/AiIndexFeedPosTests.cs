using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using FluentAssertions;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Services;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace JoiabagurPV.Tests.IntegrationTests;

[Collection(IntegrationTestCollection.Name)]
public class AiIndexFeedPosTests : IAsyncLifetime
{
    private static readonly JsonSerializerOptions Json = new() { PropertyNameCaseInsensitive = true };

    private const string PosFeed = "/api/ai/index-feed/pos-availability";

    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;

    private PointOfSale _pos = null!;
    private PaymentMethod _payment = null!;
    private User _user = null!;

    public AiIndexFeedPosTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
        _client.DefaultRequestHeaders.Add(IndexFeedOptions.HeaderName, IndexFeedTestKeys.ApiKey);
    }

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();

        using var mother = new TestDataMother(_factory.Services);
        _pos = await mother.PointOfSale()
            .WithCode("FEED-POS")
            .WithName("Feed POS")
            .WithAddress("Test Address")
            .WithPhone("600123456")
            .CreateAsync();
        _payment = await mother.PaymentMethod().WithCode("FEED-PM").CreateAsync();
        _user = await mother.User()
            .WithUsername("feedposop")
            .AsOperator()
            .AssignedTo(_pos.Id)
            .CreateAsync();
    }

    public Task DisposeAsync() => Task.CompletedTask;

    [Fact]
    public async Task PosAvailabilityFeed_ReturnsBucketNotExactQuantity()
    {
        var zero = await SeedInventoryAsync("SKU-POS-0", quantity: 0);
        var one = await SeedInventoryAsync("SKU-POS-1", quantity: 1);
        var two = await SeedInventoryAsync("SKU-POS-2", quantity: 2);
        var many = await SeedInventoryAsync("SKU-POS-3", quantity: 9);

        var response = await _client.GetAsync(PosFeed);
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        await using var stream = await response.Content.ReadAsStreamAsync();
        using var document = await JsonDocument.ParseAsync(stream);
        var root = document.RootElement;

        root.TryGetProperty("quantity", out _).Should().BeFalse();
        var byProduct = root.GetProperty("items").EnumerateArray()
            .ToDictionary(item => item.GetProperty("productId").GetGuid());

        BucketOf(byProduct[zero.Id]).Should().Be(QtyBucket.Zero);
        BucketOf(byProduct[one.Id]).Should().Be(QtyBucket.OneOrTwo);
        BucketOf(byProduct[two.Id]).Should().Be(QtyBucket.OneOrTwo);
        BucketOf(byProduct[many.Id]).Should().Be(QtyBucket.ThreeOrMore);

        foreach (var item in byProduct.Values)
        {
            item.TryGetProperty("quantity", out _).Should().BeFalse();
            item.GetProperty("isAssignedHint").GetBoolean().Should().BeTrue();
        }
    }

    [Fact]
    public async Task PosAvailabilityFeed_Unassigned_EmitsTombstone()
    {
        var product = await SeedInventoryAsync("SKU-POS-UNASSIGN", quantity: 2);
        var before = DateTime.UtcNow.AddMinutes(-1);

        await using (var scope = _factory.Services.CreateAsyncScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var inventory = await context.Inventories.SingleAsync(row =>
                row.ProductId == product.Id && row.PointOfSaleId == _pos.Id);
            inventory.IsActive = false;
            await context.SaveChangesAsync();
        }

        var page = await GetPosAsync(before, Guid.Empty);
        var item = page.Items.Single(i => i.GetProperty("productId").GetGuid() == product.Id);
        item.GetProperty("kind").GetString().Should().Be(IndexFeedKinds.Tombstone);
        item.GetProperty("reason").GetString().Should().Be(PosTombstoneReasons.Unassigned);
        item.TryGetProperty("qtyBucket", out _).Should().BeFalse();
    }

    [Fact]
    public async Task PosAvailabilityFeed_SalesWindows_DoNotSubtractReturns()
    {
        var product = await SeedInventoryAsync("SKU-POS-SALES", quantity: 4);

        // Anchored to the instant the feed counts against, not to the wall clock. Seeding
        // relative to `UtcNow` made this test a function of the day it ran: with a reference
        // instant configured, a sale "ten days ago" can sit *after* the window's end and score
        // zero. Reading the anchor from configuration keeps the test true with the option set
        // or unset, which is the property that actually needs pinning.
        var asOf = ReferenceInstant();

        using (var mother = new TestDataMother(_factory.Services))
        {
            var recent = await mother.Sale()
                .WithProduct(product.Id)
                .WithPointOfSale(_pos.Id)
                .WithPaymentMethod(_payment.Id)
                .WithUser(_user.Id)
                .WithQuantity(5)
                .WithSaleDate(asOf.AddDays(-10))
                .CreateAsync();

            await mother.Sale()
                .WithProduct(product.Id)
                .WithPointOfSale(_pos.Id)
                .WithPaymentMethod(_payment.Id)
                .WithUser(_user.Id)
                .WithQuantity(2)
                .WithSaleDate(asOf.AddDays(-40))
                .CreateAsync();

            await mother.Return()
                .WithProduct(product.Id)
                .WithPointOfSale(_pos.Id)
                .WithUser(_user.Id)
                .WithQuantity(2)
                .WithCategory(ReturnCategory.NoSatisfecho)
                .WithSaleAssociation(recent.Id, 2, recent.Price)
                .CreateAsync();
        }

        var page = await GetPosAsync();
        var item = page.Items.Single(i => i.GetProperty("productId").GetGuid() == product.Id);
        item.GetProperty("sales30d").GetInt32().Should().Be(5, "returns are not subtracted");
        item.GetProperty("sales90d").GetInt32().Should().Be(7);
        item.TryGetProperty("lastSaleAt", out var last).Should().BeTrue();
        last.ValueKind.Should().NotBe(JsonValueKind.Null);
    }

    [Fact]
    public async Task PosAvailabilityFeed_PageSize_Is200()
    {
        for (var i = 0; i < 201; i++)
        {
            await SeedInventoryAsync($"SKU-POS-PAGE-{i:D3}", quantity: 1);
        }

        var page = await GetPosAsync();
        page.Items.Count.Should().Be(IndexFeedPageSizes.PosAvailability);
        page.PageSize.Should().Be(200);
        page.HasMore.Should().BeTrue();

        var catalogClient = _factory.CreateClient();
        catalogClient.DefaultRequestHeaders.Add(IndexFeedOptions.HeaderName, IndexFeedTestKeys.ApiKey);
        var catalog = await catalogClient.GetAsync("/api/ai/index-feed/catalog");
        catalog.StatusCode.Should().Be(HttpStatusCode.OK);
        var catalogPage = await catalog.Content.ReadFromJsonAsync<FeedPage>(Json);
        catalogPage!.PageSize.Should().Be(IndexFeedPageSizes.Catalog);
    }

    /// <summary>
    /// A sale after the declared horizon must not move <c>lastSaleAt</c>.
    /// </summary>
    /// <remarks>
    /// An integration test and not a unit one on purpose: the bound lives inside a LINQ
    /// expression EF Core translates to SQL, so only a real database proves that the
    /// translated <c>MAX(CASE WHEN …)</c> ignores the excluded rows rather than returning
    /// null for the group. Left unbounded this was the one figure on the page that still
    /// drifted, which defeats the reproducibility the reference instant exists to give.
    /// </remarks>
    [Fact]
    public async Task PosAvailabilityFeed_SaleAfterTheReferenceInstant_DoesNotMoveLastSaleAt()
    {
        var product = await SeedInventoryAsync("SKU-POS-ASOF-SALE", quantity: 3);
        var asOf = ReferenceInstant();
        var inside = asOf.AddDays(-5);

        using (var mother = new TestDataMother(_factory.Services))
        {
            await mother.Sale()
                .WithProduct(product.Id)
                .WithPointOfSale(_pos.Id)
                .WithPaymentMethod(_payment.Id)
                .WithUser(_user.Id)
                .WithQuantity(3)
                .WithSaleDate(inside)
                .CreateAsync();

            await mother.Sale()
                .WithProduct(product.Id)
                .WithPointOfSale(_pos.Id)
                .WithPaymentMethod(_payment.Id)
                .WithUser(_user.Id)
                .WithQuantity(4)
                .WithSaleDate(asOf.AddDays(3))
                .CreateAsync();
        }

        var page = await GetPosAsync();
        var item = page.Items.Single(i => i.GetProperty("productId").GetGuid() == product.Id);

        item.GetProperty("lastSaleAt").GetDateTime().ToUniversalTime()
            .Should().BeCloseTo(inside, TimeSpan.FromSeconds(1),
                "a sale after the declared horizon has not happened yet, from that clock");
        item.GetProperty("sales30d").GetInt32().Should().Be(3, "the later sale is outside too");
        item.GetProperty("sales90d").GetInt32().Should().Be(3);
    }

    [Fact]
    public async Task PosAvailabilityFeed_DeclaresTheClockItCounted_Against()
    {
        await SeedInventoryAsync("SKU-POS-ASOF", quantity: 1);

        var response = await _client.GetAsync(PosFeed);
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        await using var stream = await response.Content.ReadAsStreamAsync();
        using var document = await JsonDocument.ParseAsync(stream);

        document.RootElement.TryGetProperty("computedAsOf", out var computedAsOf)
            .Should().BeTrue("a windowed figure whose clock is not declared cannot be reproduced");
        computedAsOf.GetDateTime().ToUniversalTime().Should().Be(ReferenceInstant());
    }

    /// <summary>The instant the windows are counted against: configured, or the wall clock.</summary>
    private DateTime ReferenceInstant() =>
        _factory.Services.GetRequiredService<IOptions<IndexFeedOptions>>().Value.SalesAsOfUtc
        ?? DateTime.UtcNow;

    private async Task<FeedPage> GetPosAsync(DateTime? since = null, Guid? sinceId = null)
    {
        var url = PosFeed;
        if (since.HasValue)
        {
            url += $"?since={Uri.EscapeDataString(since.Value.ToString("O"))}&sinceId={sinceId ?? Guid.Empty}";
        }

        var response = await _client.GetAsync(url);
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        return (await response.Content.ReadFromJsonAsync<FeedPage>(Json))!;
    }

    private async Task<Product> SeedInventoryAsync(string sku, int quantity)
    {
        using var mother = new TestDataMother(_factory.Services);
        var product = await mother.Product().WithSku(sku).CreateAsync();
        await mother.Inventory()
            .WithProduct(product.Id)
            .WithPointOfSale(_pos.Id)
            .WithQuantity(quantity)
            .CreateAsync();
        return product;
    }

    private static string BucketOf(JsonElement item) => item.GetProperty("qtyBucket").GetString()!;

    private sealed class FeedPage
    {
        public List<JsonElement> Items { get; set; } = [];

        public bool HasMore { get; set; }

        public int PageSize { get; set; }
    }
}
