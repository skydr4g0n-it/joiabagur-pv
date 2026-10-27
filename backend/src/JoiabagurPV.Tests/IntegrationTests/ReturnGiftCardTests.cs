using FluentAssertions;
using JoiabagurPV.Application.DTOs.GiftCards;
using JoiabagurPV.Application.DTOs.Returns;
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
public class ReturnGiftCardTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private PointOfSale _pos = null!;
    private User _operator = null!;
    private PaymentMethod _cash = null!;
    private PaymentMethod _giftPay = null!;

    public ReturnGiftCardTests(ApiWebApplicationFactory factory) => _factory = factory;

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();
        using var mother = new TestDataMother(_factory.Services);
        _pos = await mother.PointOfSale().WithCode("RET-GC").WithName("Return GC POS").CreateAsync();
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
        _operator = await mother.User().WithUsername("retgc").AsOperator().AssignedTo(_pos.Id).CreateAsync();
    }

    public Task DisposeAsync() => Task.CompletedTask;

    [Fact]
    public async Task CreateReturn_GiftCardLinkedSale_ReturnsBadRequest()
    {
        var saleId = await RedeemProductSaleIdAsync();
        using var scope = _factory.Services.CreateScope();
        var returns = scope.ServiceProvider.GetRequiredService<IReturnService>();
        var productId = await scope.ServiceProvider.GetRequiredService<ApplicationDbContext>()
            .Sales.Where(s => s.Id == saleId).Select(s => s.ProductId).FirstAsync();
        var result = await returns.CreateReturnAsync(new CreateReturnRequest
        {
            ProductId = productId,
            PointOfSaleId = _pos.Id,
            Quantity = 1,
            Category = ReturnCategory.Defectuoso,
            SaleAssociations = new List<SaleAssociationRequest>
            {
                new() { SaleId = saleId, Quantity = 1 }
            }
        }, _operator.Id, false);
        result.Success.Should().BeFalse();
        result.ErrorMessage.Should().Contain("tarjeta regalo");
    }

    [Fact]
    public async Task CreateReturn_IssuanceSale_ReturnsBadRequest()
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
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var sysProductId = await ctx.Products.Where(p => p.SystemProductKind == SystemProductKind.GiftCard)
            .Select(p => p.Id).FirstAsync();
        var returns = scope.ServiceProvider.GetRequiredService<IReturnService>();
        var result = await returns.CreateReturnAsync(new CreateReturnRequest
        {
            ProductId = sysProductId,
            PointOfSaleId = _pos.Id,
            Quantity = 1,
            Category = ReturnCategory.Defectuoso,
            SaleAssociations = new List<SaleAssociationRequest>
            {
                new() { SaleId = issued.Card!.IssuanceSaleId, Quantity = 1 }
            }
        }, _operator.Id, false);
        result.Success.Should().BeFalse();
    }

    [Fact]
    public async Task GetEligible_CoveredSale_IsOmitted()
    {
        var saleId = await RedeemProductSaleIdAsync();
        using var scope = _factory.Services.CreateScope();
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var productId = await ctx.Sales.Where(s => s.Id == saleId).Select(s => s.ProductId).FirstAsync();
        var returns = scope.ServiceProvider.GetRequiredService<IReturnService>();
        var eligible = await returns.GetEligibleSalesAsync(productId, _pos.Id, _operator.Id, false);
        eligible!.EligibleSales.Should().NotContain(s => s.SaleId == saleId);
    }

    [Fact]
    public async Task GetEligible_IssuanceSale_IsOmitted()
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
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var sysProductId = await ctx.Products.Where(p => p.SystemProductKind == SystemProductKind.GiftCard)
            .Select(p => p.Id).FirstAsync();
        var returns = scope.ServiceProvider.GetRequiredService<IReturnService>();
        var eligible = await returns.GetEligibleSalesAsync(sysProductId, _pos.Id, _operator.Id, false);
        eligible!.EligibleSales.Should().NotContain(s => s.SaleId == issued.Card!.IssuanceSaleId);
    }

    private async Task<Guid> RedeemProductSaleIdAsync()
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
        var product = await mother.Product().WithSku("RET-PRD").WithName("Return product").WithPrice(80m).CreateAsync();
        await mother.Inventory().WithProduct(product.Id).WithPointOfSale(_pos.Id).WithQuantity(5).CreateAsync();
        var sales = scope.ServiceProvider.GetRequiredService<ISalesService>();
        var bulk = await sales.CreateBulkSalesAsync(new CreateBulkSalesRequest
        {
            PointOfSaleId = _pos.Id,
            PaymentMethodId = _giftPay.Id,
            GiftCardCodes = new List<string> { issued.Card!.Code },
            Lines = new List<BulkSaleLineRequest> { new() { ProductId = product.Id, Quantity = 1 } }
        }, _operator.Id, false);
        bulk.Success.Should().BeTrue();
        return bulk.Sales![0].Id;
    }
}
