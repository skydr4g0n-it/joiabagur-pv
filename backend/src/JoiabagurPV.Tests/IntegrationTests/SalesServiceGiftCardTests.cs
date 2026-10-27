using FluentAssertions;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.DTOs.GiftCards;
using JoiabagurPV.Application.DTOs.Sales;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Constants;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;
using System.Net;
using System.Net.Http.Json;

namespace JoiabagurPV.Tests.IntegrationTests;

[Collection(IntegrationTestCollection.Name)]
public class SalesServiceGiftCardTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private PointOfSale _pos = null!;
    private PointOfSale _otherPos = null!;
    private User _operator = null!;
    private PaymentMethod _cash = null!;
    private PaymentMethod _giftPay = null!;
    private HttpClient _operatorClient = null!;

    public SalesServiceGiftCardTests(ApiWebApplicationFactory factory) => _factory = factory;

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();
        using var mother = new TestDataMother(_factory.Services);
        _pos = await mother.PointOfSale().WithCode("RDM-POS").WithName("Redeem POS").CreateAsync();
        _otherPos = await mother.PointOfSale().WithCode("RDM-OTHER").WithName("Other POS").CreateAsync();
        _cash = await mother.Context.PaymentMethods.FirstAsync(pm => pm.Code == "CASH");
        _giftPay = await mother.Context.PaymentMethods.FirstAsync(pm => pm.Code == GiftCardConstants.GiftCardPaymentMethodCode);
        await GiftCardSeedHelper.EnsureGiftCardMethodAssignedToPosAsync(mother.Context, _giftPay.Id, _pos.Id, NullLogger.Instance);
        await GiftCardSeedHelper.EnsureGiftCardMethodAssignedToPosAsync(mother.Context, _giftPay.Id, _otherPos.Id, NullLogger.Instance);
        if (!await mother.Context.PointOfSalePaymentMethods.AnyAsync(a => a.PointOfSaleId == _pos.Id && a.PaymentMethodId == _cash.Id))
        {
            mother.Context.PointOfSalePaymentMethods.Add(new PointOfSalePaymentMethod
            {
                PointOfSaleId = _pos.Id,
                PaymentMethodId = _cash.Id,
                IsActive = true
            });
            await mother.Context.SaveChangesAsync();
        }
        if (!await mother.Context.PointOfSalePaymentMethods.AnyAsync(a => a.PointOfSaleId == _otherPos.Id && a.PaymentMethodId == _cash.Id))
        {
            mother.Context.PointOfSalePaymentMethods.Add(new PointOfSalePaymentMethod
            {
                PointOfSaleId = _otherPos.Id,
                PaymentMethodId = _cash.Id,
                IsActive = true
            });
            await mother.Context.SaveChangesAsync();
        }
        _operator = await mother.User().WithUsername("rdmop").AsOperator().AssignedTo(_pos.Id).CreateAsync();
        _operatorClient = await CreateAuthenticatedClientAsync("rdmop", "Test123!");
    }

    public Task DisposeAsync() => Task.CompletedTask;

    [Fact]
    public async Task Redeem_Example1_50EurProduct_FullCoverage()
    {
        var card = await Issue100CardAsync();
        var product = await CreateProductAsync(50m, 5);
        var result = await BulkAsync(product.Id, 1, card.Code, fullyCovered: true);
        result.Success.Should().BeTrue();
        result.Sales![0].GiftCardCoverageAmount.Should().Be(50m);
        await AssertSpendableZero(card.Code);
    }

    [Fact]
    public async Task Redeem_Example2_150EurProduct_PartialCoverage()
    {
        var card = await Issue100CardAsync();
        var product = await CreateProductAsync(150m, 5);
        var result = await BulkAsync(product.Id, 1, card.Code, fullyCovered: false);
        result.Success.Should().BeTrue();
        result.Sales![0].GiftCardCoverageAmount.Should().Be(100m);
    }

    [Fact]
    public async Task Redeem_Example3_50And150_CheapestFirst()
    {
        var card = await Issue100CardAsync();
        var p50 = await CreateProductAsync(50m, 5, "SKU-50");
        var p150 = await CreateProductAsync(150m, 5, "SKU-150");
        var result = await BulkAsync(new[] { (p150.Id, 1), (p50.Id, 1) }, card.Code, fullyCovered: false);
        result.Success.Should().BeTrue();
        var bySku = result.Sales!.ToDictionary(s => s.ProductSku);
        bySku["SKU-50"].GiftCardCoverageAmount.Should().Be(50m);
        bySku["SKU-150"].GiftCardCoverageAmount.Should().Be(50m);
    }

    [Fact]
    public async Task Redeem_Example4_150And200_CoversCheaperOnly()
    {
        var card = await Issue100CardAsync();
        var p150 = await CreateProductAsync(150m, 5, "SKU-150B");
        var p200 = await CreateProductAsync(200m, 5, "SKU-200");
        var result = await BulkAsync(new[] { (p150.Id, 1), (p200.Id, 1) }, card.Code, fullyCovered: false);
        result.Success.Should().BeTrue();
        var bySku = result.Sales!.ToDictionary(s => s.ProductSku);
        bySku["SKU-150B"].GiftCardCoverageAmount.Should().Be(100m);
        bySku["SKU-200"].GiftCardCoverageAmount.Should().Be(0m);
    }

    [Fact]
    public async Task Redeem_Example5_50And30_FullyCovered()
    {
        var card = await Issue100CardAsync();
        var p50 = await CreateProductAsync(50m, 5, "SKU-50C");
        var p30 = await CreateProductAsync(30m, 5, "SKU-30");
        var result = await BulkAsync(new[] { (p50.Id, 1), (p30.Id, 1) }, card.Code, fullyCovered: true);
        result.Success.Should().BeTrue();
        result.Sales!.Sum(s => s.GiftCardCoverageAmount).Should().Be(80m);
    }

    [Fact]
    public async Task Redeem_ExpiredCard_LeavesBalanceUnchanged()
    {
        var card = await Issue100CardAsync();
        using (var scope = _factory.Services.CreateScope())
        {
            var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var entity = await ctx.GiftCards.FirstAsync(c => c.Code == card.Code);
            entity.ExpiryDate = DateOnly.FromDateTime(DateTime.UtcNow.AddDays(-2));
            await ctx.SaveChangesAsync();
        }

        var product = await CreateProductAsync(50m, 5);
        var result = await BulkAsync(product.Id, 1, card.Code, fullyCovered: true);
        result.Success.Should().BeFalse();

        using var verifyScope = _factory.Services.CreateScope();
        var verifyCtx = verifyScope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var balance = await verifyCtx.GiftCards.Where(c => c.Code == card.Code).Select(c => c.SpendableBalance).FirstAsync();
        balance.Should().Be(100m);
    }

    [Fact]
    public async Task Redeem_WrongPos_ReturnsBadRequest()
    {
        var card = await Issue100CardAsync();
        var product = await CreateProductAsync(50m, 5);
        using var scope = _factory.Services.CreateScope();
        var sales = scope.ServiceProvider.GetRequiredService<ISalesService>();
        var result = await sales.CreateBulkSalesAsync(new CreateBulkSalesRequest
        {
            PointOfSaleId = _otherPos.Id,
            PaymentMethodId = _cash.Id,
            GiftCardCodes = new List<string> { card.Code },
            Lines = new List<BulkSaleLineRequest> { new() { ProductId = product.Id, Quantity = 1 } }
        }, _operator.Id, false);
        result.Success.Should().BeFalse();
    }

    [Fact]
    public async Task Redeem_AlreadyUsed_ReturnsBadRequest()
    {
        var card = await Issue100CardAsync();
        var product = await CreateProductAsync(50m, 5);
        (await BulkAsync(product.Id, 1, card.Code, fullyCovered: true)).Success.Should().BeTrue();
        var second = await BulkAsync(product.Id, 1, card.Code, fullyCovered: true);
        second.Success.Should().BeFalse();
    }

    [Fact]
    public async Task Redeem_AccountedRemainderOnly_ReturnsBadRequest()
    {
        var card = await Issue100CardAsync();
        var product = await CreateProductAsync(50m, 5);
        (await BulkAsync(product.Id, 1, card.Code, fullyCovered: true)).Success.Should().BeTrue();
        var product2 = await CreateProductAsync(30m, 5, "SKU-RETRY");
        var retry = await BulkAsync(product2.Id, 1, card.Code, fullyCovered: true);
        retry.Success.Should().BeFalse();
    }

    [Fact]
    public async Task Redeem_SameIdempotencyKey_DoesNotDuplicate()
    {
        var card = await Issue100CardAsync();
        var product = await CreateProductAsync(50m, 5);
        var request = new CreateBulkSalesRequest
        {
            PointOfSaleId = _pos.Id,
            PaymentMethodId = _giftPay.Id,
            GiftCardCodes = new List<string> { card.Code },
            Lines = new List<BulkSaleLineRequest> { new() { ProductId = product.Id, Quantity = 1 } }
        };

        var first = new HttpRequestMessage(HttpMethod.Post, "/api/sales/bulk");
        first.Content = JsonContent.Create(request);
        first.Headers.Add("Idempotency-Key", "gc-bulk-idem-1");
        var firstResponse = await _operatorClient.SendAsync(first);

        var second = new HttpRequestMessage(HttpMethod.Post, "/api/sales/bulk");
        second.Content = JsonContent.Create(request);
        second.Headers.Add("Idempotency-Key", "gc-bulk-idem-1");
        var secondResponse = await _operatorClient.SendAsync(second);

        firstResponse.StatusCode.Should().Be(HttpStatusCode.Created);
        secondResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        using var scope = _factory.Services.CreateScope();
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        (await ctx.Sales.CountAsync(s => s.ProductId == product.Id)).Should().Be(1);
    }

    [Fact]
    public async Task Redeem_InactiveRemainderPaymentMethod_ReturnsBadRequest()
    {
        var card = await Issue100CardAsync();
        var product = await CreateProductAsync(150m, 5);
        using (var scope = _factory.Services.CreateScope())
        {
            var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var assignment = await ctx.PointOfSalePaymentMethods
                .FirstAsync(a => a.PointOfSaleId == _pos.Id && a.PaymentMethodId == _cash.Id);
            assignment.IsActive = false;
            await ctx.SaveChangesAsync();
        }

        using var salesScope = _factory.Services.CreateScope();
        var sales = salesScope.ServiceProvider.GetRequiredService<ISalesService>();
        var result = await sales.CreateBulkSalesAsync(new CreateBulkSalesRequest
        {
            PointOfSaleId = _pos.Id,
            PaymentMethodId = _cash.Id,
            GiftCardCodes = new List<string> { card.Code },
            Lines = new List<BulkSaleLineRequest> { new() { ProductId = product.Id, Quantity = 1 } }
        }, _operator.Id, false);
        result.Success.Should().BeFalse();
    }

    [Fact]
    public async Task GetHistory_CoveredSale_IncludesCoverageAmount()
    {
        var card = await Issue100CardAsync();
        var product = await CreateProductAsync(150m, 5);
        var bulk = await BulkAsync(product.Id, 1, card.Code, fullyCovered: false);
        bulk.Success.Should().BeTrue();
        var saleId = bulk.Sales![0].Id;

        using var scope = _factory.Services.CreateScope();
        var sales = scope.ServiceProvider.GetRequiredService<ISalesService>();
        var history = await sales.GetSalesHistoryAsync(new SalesHistoryFilterRequest
        {
            PointOfSaleId = _pos.Id,
            Page = 1,
            PageSize = 50
        }, _operator.Id, false);

        var row = history.Sales.First(s => s.Id == saleId);
        row.GiftCardCoverageAmount.Should().Be(100m);
    }

    [Fact]
    public async Task CreateBulk_SystemProductLine_ReturnsBadRequest()
    {
        using var scope = _factory.Services.CreateScope();
        var sales = scope.ServiceProvider.GetRequiredService<ISalesService>();
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var sys = await ctx.Products.FirstAsync(p => p.SystemProductKind == SystemProductKind.GiftCard);
        var result = await sales.CreateBulkSalesAsync(new CreateBulkSalesRequest
        {
            PointOfSaleId = _pos.Id,
            PaymentMethodId = _cash.Id,
            Lines = new List<BulkSaleLineRequest> { new() { ProductId = sys.Id, Quantity = 1 } }
        }, _operator.Id, false);
        result.Success.Should().BeFalse();
    }

    private async Task<GiftCardDetailDto> Issue100CardAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var giftCards = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        var result = await giftCards.IssueAsync(new IssueGiftCardRequest
        {
            PointOfSaleId = _pos.Id,
            NominalAmount = 100m,
            ExpiryDate = DateOnly.FromDateTime(DateTime.UtcNow.AddDays(30)),
            PaymentMethodId = _cash.Id
        }, _operator.Id, false, null);
        return result.Card!;
    }

    private async Task<Product> CreateProductAsync(decimal price, int stock, string? sku = null)
    {
        using var mother = new TestDataMother(_factory.Services);
        var product = await mother.Product()
            .WithSku(sku ?? $"SKU-{price}")
            .WithName($"Product {price}")
            .WithPrice(price)
            .CreateAsync();
        await mother.Inventory().WithProduct(product.Id).WithPointOfSale(_pos.Id).WithQuantity(stock).CreateAsync();
        return product;
    }

    private async Task<CreateBulkSalesResult> BulkAsync(Guid productId, int qty, string cardCode, bool fullyCovered)
    {
        return await BulkAsync(new[] { (productId, qty) }, cardCode, fullyCovered);
    }

    private async Task<CreateBulkSalesResult> BulkAsync(IEnumerable<(Guid ProductId, int Qty)> lines, string cardCode, bool fullyCovered)
    {
        using var scope = _factory.Services.CreateScope();
        var sales = scope.ServiceProvider.GetRequiredService<ISalesService>();
        return await sales.CreateBulkSalesAsync(new CreateBulkSalesRequest
        {
            PointOfSaleId = _pos.Id,
            PaymentMethodId = fullyCovered ? _giftPay.Id : _cash.Id,
            GiftCardCodes = new List<string> { cardCode },
            Lines = lines.Select(l => new BulkSaleLineRequest { ProductId = l.ProductId, Quantity = l.Qty }).ToList()
        }, _operator.Id, false);
    }

    private async Task AssertSpendableZero(string code)
    {
        using var scope = _factory.Services.CreateScope();
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var card = await ctx.GiftCards.FirstAsync(c => c.Code == code);
        card.SpendableBalance.Should().Be(0m);
    }

    private async Task<HttpClient> CreateAuthenticatedClientAsync(string username, string password)
    {
        var client = _factory.CreateClient();
        var loginResponse = await client.PostAsJsonAsync("/api/auth/login", new LoginRequest
        {
            Username = username,
            Password = password
        });
        loginResponse.EnsureSuccessStatusCode();
        var login = await loginResponse.Content.ReadFromJsonAsync<LoginResponse>();
        client.DefaultRequestHeaders.Authorization =
            new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", login!.AccessToken);
        return client;
    }
}
