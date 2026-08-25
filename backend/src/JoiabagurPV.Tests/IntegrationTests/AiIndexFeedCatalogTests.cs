using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using FluentAssertions;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Tests.IntegrationTests;

[Collection(IntegrationTestCollection.Name)]
public class AiIndexFeedCatalogTests : IAsyncLifetime
{
    private static readonly JsonSerializerOptions Json = new() { PropertyNameCaseInsensitive = true };

    private const string Catalog = "/api/ai/index-feed/catalog";

    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;

    public AiIndexFeedCatalogTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = FeedClient(factory);
    }

    public async Task InitializeAsync() => await _factory.ResetDatabaseAsync();

    public Task DisposeAsync() => Task.CompletedTask;

    [Fact]
    public async Task CatalogFeed_WithSinceCursor_ReturnsOnlyChangedRows()
    {
        var first = await SeedApprovedAsync("SKU-FEED-A", 40m);
        var page = await GetCatalogAsync();
        var firstItem = page.Items.Single(item => IdOf(item) == first.Id);

        var second = await SeedApprovedAsync("SKU-FEED-B", 50m);

        var after = await GetCatalogAsync(SinceOf(firstItem), first.Id);
        IdsOf(after).Should().Contain(second.Id);
        IdsOf(after).Should().NotContain(first.Id);
        after.Items.Count.Should().BeLessThanOrEqualTo(IndexFeedPageSizes.Catalog);
    }

    [Fact]
    public async Task CatalogFeed_EmitsTombstoneWhenProductDeactivated()
    {
        var product = await SeedApprovedAsync("SKU-FEED-DEACT", 40m);
        var before = DateTime.UtcNow.AddMinutes(-1);

        await using (var scope = _factory.Services.CreateAsyncScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var tracked = await context.Products.SingleAsync(p => p.Id == product.Id);
            tracked.IsActive = false;
            await context.SaveChangesAsync();
        }

        var page = await GetCatalogAsync(before, Guid.Empty);
        var item = page.Items.Single(i => IdOf(i) == product.Id);
        KindOf(item).Should().Be(IndexFeedKinds.Tombstone);
        item.GetProperty("reason").GetString().Should().Be(CatalogTombstoneReasons.Deactivated);
        item.TryGetProperty("sku", out _).Should().BeFalse();
    }

    [Fact]
    public async Task CatalogFeed_ExcludesUnapprovedProfiles()
    {
        await SeedProfileAsync("SKU-FEED-PEND", 40m, ProfileReviewStatus.Pending);
        await SeedProfileAsync("SKU-FEED-REJ", 40m, ProfileReviewStatus.Rejected);

        var page = await GetCatalogAsync();
        page.Items.Should().BeEmpty("pending and rejected profiles are not indexable and a full sync does not emit tombstones for them");
    }

    [Fact]
    public async Task CatalogFeed_NeverApprovedProduct_IsAbsent()
    {
        var product = await SeedProfileAsync("SKU-FEED-NEVER", 40m, ProfileReviewStatus.Pending);

        var page = await GetCatalogAsync();
        IdsOf(page).Should().NotContain(product.Id);
    }

    [Fact]
    public async Task CatalogFeed_EmitsTombstoneWhenProfileUnapproved()
    {
        var product = await SeedApprovedAsync("SKU-FEED-UNAPP", 40m);
        var before = DateTime.UtcNow.AddMinutes(-1);

        await using (var scope = _factory.Services.CreateAsyncScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var profile = await context.ProductAiProfiles.SingleAsync(p => p.ProductId == product.Id);
            profile.ReviewStatus = ProfileReviewStatus.Rejected;
            await context.SaveChangesAsync();
        }

        var page = await GetCatalogAsync(before, Guid.Empty);
        var item = page.Items.Single(i => IdOf(i) == product.Id);
        KindOf(item).Should().Be(IndexFeedKinds.Tombstone);
        item.GetProperty("reason").GetString().Should().Be(CatalogTombstoneReasons.Unapproved);
    }

    [Fact]
    public async Task CatalogFeed_ProductWithoutProfile_IsAbsent()
    {
        Product product;
        using (var mother = new TestDataMother(_factory.Services))
        {
            product = await mother.Product().WithSku("SKU-FEED-NOPROFILE").CreateAsync();
        }

        var page = await GetCatalogAsync(DateTime.UtcNow.AddMinutes(-1), Guid.Empty);
        IdsOf(page).Should().NotContain(product.Id);
    }

    [Fact]
    public async Task Feed_ReturnsAggregateHashForDriftDetection()
    {
        for (var i = 0; i < 51; i++)
        {
            await SeedApprovedAsync($"SKU-FEED-HASH-{i:D2}", 40m + i);
        }

        var first = await GetCatalogAsync();
        first.Items.Count.Should().Be(IndexFeedPageSizes.Catalog);
        first.HasMore.Should().BeTrue();
        first.PageSize.Should().Be(50);
        first.NextCursor.Should().NotBeNull();

        var second = await GetCatalogAsync(first.NextCursor!.Since, first.NextCursor.SinceId);
        second.AggregateHash.Should().Be(first.AggregateHash);
        first.AggregateHash.Should().MatchRegex("^[0-9a-f]{64}$");

        var leavingId = IdOf(first.Items[0]);
        await using (var scope = _factory.Services.CreateAsyncScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var tracked = await context.Products.SingleAsync(p => p.Id == leavingId);
            tracked.IsActive = false;
            await context.SaveChangesAsync();
        }

        var after = await GetCatalogAsync();
        after.AggregateHash.Should().NotBe(first.AggregateHash);
    }

    [Fact]
    public async Task CatalogFeed_IgnoresClientPageSize_AndOmitsProvenance()
    {
        await SeedApprovedAsync("SKU-FEED-MAP", 29.99m);

        var response = await _client.GetAsync($"{Catalog}?pageSize=1000");
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        await using var stream = await response.Content.ReadAsStreamAsync();
        using var document = await JsonDocument.ParseAsync(stream);
        var root = document.RootElement;

        root.GetProperty("pageSize").GetInt32().Should().Be(50);
        root.GetProperty("items").GetArrayLength().Should().BeLessThanOrEqualTo(50);
        root.TryGetProperty("quantity", out _).Should().BeFalse();
        root.TryGetProperty("dataOrigin", out _).Should().BeFalse();

        var item = root.GetProperty("items")[0];
        item.TryGetProperty("quantity", out _).Should().BeFalse();
        item.TryGetProperty("dataOrigin", out _).Should().BeFalse();
        item.TryGetProperty("textProvenance", out _).Should().BeFalse();
        item.TryGetProperty("source", out _).Should().BeFalse();
        item.TryGetProperty("confidence", out _).Should().BeFalse();
        item.GetProperty("priceBand").GetString().Should().Be("lt-30");
        item.GetProperty("materials").ValueKind.Should().Be(JsonValueKind.Array);
    }

    private static HttpClient FeedClient(ApiWebApplicationFactory factory)
    {
        var client = factory.CreateClient();
        client.DefaultRequestHeaders.Add(IndexFeedOptions.HeaderName, IndexFeedTestKeys.ApiKey);
        return client;
    }

    private async Task<FeedPage> GetCatalogAsync(DateTime? since = null, Guid? sinceId = null)
    {
        var url = Catalog;
        if (since.HasValue)
        {
            url += $"?since={Uri.EscapeDataString(since.Value.ToString("O"))}&sinceId={sinceId ?? Guid.Empty}";
        }

        var response = await _client.GetAsync(url);
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        return (await response.Content.ReadFromJsonAsync<FeedPage>(Json))!;
    }

    private async Task<Product> SeedApprovedAsync(string sku, decimal price) =>
        await SeedProfileAsync(sku, price, ProfileReviewStatus.Approved);

    private async Task<Product> SeedProfileAsync(string sku, decimal price, ProfileReviewStatus status)
    {
        using var mother = new TestDataMother(_factory.Services);
        var product = await mother.Product().WithSku(sku).WithPrice(price).CreateAsync();

        mother.Context.ProductAiProfiles.Add(new ProductAiProfile
        {
            ProductId = product.Id,
            PieceType = "anillo",
            MaterialsJson = "[\"plata\"]",
            ColorTagsJson = "[\"dorado\"]",
            StyleTagsJson = "[]",
            OccasionTagsJson = "[]",
            FieldConfidenceJson = "{}",
            FieldSourceJson = "{}",
            ProposedProfileJson = "{}",
            SourceHash = new string('a', 64),
            ReviewStatus = status,
            ReviewOrigin = ProfileReviewOrigin.AutoBulk
        });
        await mother.Context.SaveChangesAsync();
        return product;
    }

    private static Guid IdOf(JsonElement item) => item.GetProperty("productId").GetGuid();

    private static string KindOf(JsonElement item) => item.GetProperty("kind").GetString()!;

    private static DateTime SinceOf(JsonElement item) =>
        item.TryGetProperty("watermark", out var watermark)
            ? watermark.GetDateTime()
            : item.GetProperty("at").GetDateTime();

    private static IEnumerable<Guid> IdsOf(FeedPage page) => page.Items.Select(IdOf);

    private sealed class FeedPage
    {
        public List<JsonElement> Items { get; set; } = [];

        public FeedCursor? NextCursor { get; set; }

        public bool HasMore { get; set; }

        public int PageSize { get; set; }

        public string AggregateHash { get; set; } = string.Empty;
    }

    private sealed class FeedCursor
    {
        public DateTime Since { get; set; }

        public Guid SinceId { get; set; }
    }
}
