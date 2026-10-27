using FluentAssertions;
using JoiabagurPV.Application.DTOs.GiftCards;
using JoiabagurPV.Application.DTOs.Sales;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Constants;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;

namespace JoiabagurPV.Tests.IntegrationTests;

[Collection(IntegrationTestCollection.Name)]
public class GiftCardExchangeTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private PointOfSale _pos = null!;
    private User _operator = null!;
    private PaymentMethod _cash = null!;
    private PaymentMethod _giftPay = null!;

    public GiftCardExchangeTests(ApiWebApplicationFactory factory) => _factory = factory;

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();
        using var mother = new TestDataMother(_factory.Services);
        _pos = await mother.PointOfSale().WithCode("EX-POS").WithName("Exchange POS").CreateAsync();
        _cash = await mother.Context.PaymentMethods.FirstAsync(pm => pm.Code == "CASH");
        _giftPay = await mother.Context.PaymentMethods.FirstAsync(pm => pm.Code == GiftCardConstants.GiftCardPaymentMethodCode);
        await GiftCardSeedHelper.EnsureGiftCardMethodAssignedToPosAsync(mother.Context, _giftPay.Id, _pos.Id, NullLogger.Instance);
        await EnsureCashAssignedAsync(mother.Context, _pos.Id, _cash.Id);
        _operator = await mother.User().WithUsername("exop").AsOperator().AssignedTo(_pos.Id).CreateAsync();
    }

    public Task DisposeAsync() => Task.CompletedTask;

    [Fact]
    public async Task Exchange_UpgradeInsideRemainder_ChargesNothing()
    {
        var card = await IssueAndRedeemAsync(50m, 50m);
        var replacement = await CreateProductAsync(80m, 5, "EX-80");
        var result = await ExchangeAsync(card.Id, card.LinkedProducts[0].SaleId, replacement.Id);
        result.Success.Should().BeTrue();
        result.CashDue.Should().Be(0m);
        using var scope = _factory.Services.CreateScope();
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var reloaded = await ctx.GiftCards.Include(g => g.CoverageEntries).FirstAsync(g => g.Id == card.Id);
        reloaded.SpendableBalance.Should().Be(0m);
        (await scope.ServiceProvider.GetRequiredService<IGiftCardRepository>().GetAccountedRemainderAsync(card.Id))
            .Should().Be(20m);
    }

    [Fact]
    public async Task Exchange_UpgradeBeyondRemainder_ChargesExcess()
    {
        var card = await IssueAndRedeemAsync(150m, 100m);
        var replacement = await CreateProductAsync(180m, 5, "EX-180");
        var result = await ExchangeAsync(card.Id, card.LinkedProducts[0].SaleId, replacement.Id);
        result.Success.Should().BeTrue();
        result.CashDue.Should().Be(30m);
    }

    [Fact]
    public async Task Exchange_Downgrade_RestoresAccountedValueOnly()
    {
        var card = await IssueAndRedeemAsync(50m, 50m);
        var replacement = await CreateProductAsync(30m, 5, "EX-30");
        var result = await ExchangeAsync(card.Id, card.LinkedProducts[0].SaleId, replacement.Id);
        result.Success.Should().BeTrue();
        result.CashDue.Should().Be(0m);
        using var scope = _factory.Services.CreateScope();
        var remainder = await scope.ServiceProvider.GetRequiredService<IGiftCardRepository>()
            .GetAccountedRemainderAsync(card.Id);
        remainder.Should().Be(70m);
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        (await ctx.GiftCards.Where(g => g.Id == card.Id).Select(g => g.SpendableBalance).FirstAsync()).Should().Be(0m);
    }

    [Fact]
    public async Task Exchange_MultipleLines_OneRequest()
    {
        var issued = await Issue100Async();
        var p50 = await CreateProductAsync(50m, 5, "EX-M50");
        var p60 = await CreateProductAsync(60m, 5, "EX-M60");
        await BulkAsync(new[] { (p50.Id, 1), (p60.Id, 1) }, issued.Code, fullyCovered: false);
        using var scope = _factory.Services.CreateScope();
        var giftCards = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        var detail = await giftCards.GetDetailAsync(issued.Id, _operator.Id, false);
        detail!.LinkedProducts.Should().HaveCount(2);
        var newA = await CreateProductAsync(55m, 5, "EX-NEW-A");
        var newB = await CreateProductAsync(65m, 5, "EX-NEW-B");
        var sut = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        var result = await sut.ExchangeAsync(issued.Id, new ExchangeGiftCardRequest
        {
            PointOfSaleId = _pos.Id,
            PaymentMethodId = _cash.Id,
            ReturnCategory = ReturnCategory.Defectuoso,
            ReturnLines = detail.LinkedProducts.Select(l => new GiftCardExchangeLineRequest
            {
                SaleId = l.SaleId,
                Quantity = 1
            }).ToList(),
            NewProducts = new List<GiftCardExchangeNewProductRequest>
            {
                new() { ProductId = newA.Id, Quantity = 1 },
                new() { ProductId = newB.Id, Quantity = 1 }
            }
        }, _operator.Id, false, null);
        result.Success.Should().BeTrue();
        result.ReturnIds.Should().HaveCount(2);
        result.NewSaleIds.Should().HaveCount(2);
    }

    [Fact]
    public async Task Exchange_SameIdempotencyKey_DoesNotDuplicate()
    {
        var card = await IssueAndRedeemAsync(50m, 50m);
        var replacement = await CreateProductAsync(80m, 5, "EX-IDEM");
        var request = new ExchangeGiftCardRequest
        {
            PointOfSaleId = _pos.Id,
            PaymentMethodId = _cash.Id,
            ReturnCategory = ReturnCategory.Defectuoso,
            ReturnLines = new List<GiftCardExchangeLineRequest>
            {
                new() { SaleId = card.LinkedProducts[0].SaleId, Quantity = 1 }
            },
            NewProducts = new List<GiftCardExchangeNewProductRequest>
            {
                new() { ProductId = replacement.Id, Quantity = 1 }
            }
        };
        using var scope = _factory.Services.CreateScope();
        var sut = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var first = await sut.ExchangeAsync(card.Id, request, _operator.Id, false, "ex-idem-1");
        var second = await sut.ExchangeAsync(card.Id, request, _operator.Id, false, "ex-idem-1");
        second.NewSaleIds.Should().BeEquivalentTo(first.NewSaleIds);
        (await ctx.Returns.CountAsync()).Should().Be(1);
        (await ctx.Sales.CountAsync(s => first.NewSaleIds.Contains(s.Id))).Should().Be(1);
    }

    private async Task<GiftCardDetailDto> IssueAndRedeemAsync(decimal productPrice, decimal coverageExpected)
    {
        var issued = await Issue100Async();
        var product = await CreateProductAsync(productPrice, 5, $"EX-{productPrice}");
        var bulk = await BulkAsync(new[] { (product.Id, 1) }, issued.Code, productPrice <= 100);
        bulk.Success.Should().BeTrue();
        bulk.Sales![0].GiftCardCoverageAmount.Should().Be(coverageExpected);
        using var scope = _factory.Services.CreateScope();
        var giftCards = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        return (await giftCards.GetDetailAsync(issued.Id, _operator.Id, false))!;
    }

    private async Task<ExchangeGiftCardResult> ExchangeAsync(Guid cardId, Guid saleId, Guid newProductId)
    {
        using var scope = _factory.Services.CreateScope();
        var sut = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        return await sut.ExchangeAsync(cardId, new ExchangeGiftCardRequest
        {
            PointOfSaleId = _pos.Id,
            PaymentMethodId = _cash.Id,
            ReturnCategory = ReturnCategory.Defectuoso,
            ReturnLines = new List<GiftCardExchangeLineRequest>
            {
                new() { SaleId = saleId, Quantity = 1 }
            },
            NewProducts = new List<GiftCardExchangeNewProductRequest>
            {
                new() { ProductId = newProductId, Quantity = 1 }
            }
        }, _operator.Id, false, null);
    }

    private async Task<GiftCardDetailDto> Issue100Async()
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

    private async Task<Product> CreateProductAsync(decimal price, int stock, string sku)
    {
        using var mother = new TestDataMother(_factory.Services);
        var product = await mother.Product().WithSku(sku).WithName($"Product {sku}").WithPrice(price).CreateAsync();
        await mother.Inventory().WithProduct(product.Id).WithPointOfSale(_pos.Id).WithQuantity(stock).CreateAsync();
        return product;
    }

    private async Task<CreateBulkSalesResult> BulkAsync(
        IEnumerable<(Guid ProductId, int Qty)> lines,
        string cardCode,
        bool fullyCovered)
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

    private static async Task EnsureCashAssignedAsync(ApplicationDbContext ctx, Guid posId, Guid cashId)
    {
        if (!await ctx.PointOfSalePaymentMethods.AnyAsync(a => a.PointOfSaleId == posId && a.PaymentMethodId == cashId))
        {
            ctx.PointOfSalePaymentMethods.Add(new PointOfSalePaymentMethod
            {
                PointOfSaleId = posId,
                PaymentMethodId = cashId,
                IsActive = true
            });
            await ctx.SaveChangesAsync();
        }
    }
}
