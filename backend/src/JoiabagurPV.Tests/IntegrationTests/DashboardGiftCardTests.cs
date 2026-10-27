using FluentAssertions;
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

namespace JoiabagurPV.Tests.IntegrationTests;

[Collection(IntegrationTestCollection.Name)]
public class DashboardGiftCardTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private PointOfSale _pos = null!;
    private User _operator = null!;
    private PaymentMethod _cash = null!;
    private PaymentMethod _giftPay = null!;

    public DashboardGiftCardTests(ApiWebApplicationFactory factory) => _factory = factory;

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();
        using var mother = new TestDataMother(_factory.Services);
        _pos = await mother.PointOfSale().WithCode("DASH-GC").WithName("Dash GC").CreateAsync();
        _cash = await mother.Context.PaymentMethods.FirstAsync(pm => pm.Code == "CASH");
        _giftPay = await mother.Context.PaymentMethods.FirstAsync(pm => pm.Code == GiftCardConstants.GiftCardPaymentMethodCode);
        await GiftCardSeedHelper.EnsureGiftCardMethodAssignedToPosAsync(mother.Context, _giftPay.Id, _pos.Id, NullLogger.Instance);
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
        _operator = await mother.User().WithUsername("dashgc").AsOperator().AssignedTo(_pos.Id).CreateAsync();
    }

    public Task DisposeAsync() => Task.CompletedTask;

    [Fact]
    public async Task Dashboard_ReturnedCoveredSale_IsAbsentFromPaymentMix()
    {
        using var scope = _factory.Services.CreateScope();
        var giftCards = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        var issued = await giftCards.IssueAsync(new IssueGiftCardRequest
        {
            PointOfSaleId = _pos.Id,
            NominalAmount = 100m,
            ExpiryDate = DateOnly.FromDateTime(DateTime.UtcNow.AddDays(30)),
            PaymentMethodId = _cash.Id
        }, _operator.Id, false, null);
        using var mother = new TestDataMother(_factory.Services);
        var product = await mother.Product().WithSku("DASH-80").WithName("Dash product").WithPrice(80m).CreateAsync();
        var replacement = await mother.Product().WithSku("DASH-90").WithName("Replacement").WithPrice(90m).CreateAsync();
        await mother.Inventory().WithProduct(product.Id).WithPointOfSale(_pos.Id).WithQuantity(5).CreateAsync();
        await mother.Inventory().WithProduct(replacement.Id).WithPointOfSale(_pos.Id).WithQuantity(5).CreateAsync();
        var sales = scope.ServiceProvider.GetRequiredService<ISalesService>();
        var bulk = await sales.CreateBulkSalesAsync(new CreateBulkSalesRequest
        {
            PointOfSaleId = _pos.Id,
            PaymentMethodId = _giftPay.Id,
            GiftCardCodes = new List<string> { issued.Card!.Code },
            Lines = new List<BulkSaleLineRequest> { new() { ProductId = product.Id, Quantity = 1 } }
        }, _operator.Id, false);
        var saleId = bulk.Sales![0].Id;
        var cardId = issued.Card!.Id;
        await giftCards.ExchangeAsync(cardId, new ExchangeGiftCardRequest
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
                new() { ProductId = replacement.Id, Quantity = 1 }
            }
        }, _operator.Id, false, null);

        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        (await ctx.ReturnSales.AnyAsync(rs => rs.SaleId == saleId)).Should().BeTrue();

        var monthStart = new DateTime(DateTime.UtcNow.Year, DateTime.UtcNow.Month, 1, 0, 0, 0, DateTimeKind.Utc);
        var inPaymentMix = await ctx.Sales.AnyAsync(s =>
            s.Id == saleId
            && s.SaleDate >= monthStart
            && !s.ReturnSales.Any());
        inPaymentMix.Should().BeFalse();
    }
}
