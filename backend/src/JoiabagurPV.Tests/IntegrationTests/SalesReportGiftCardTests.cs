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
public class SalesReportGiftCardTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private PointOfSale _pos = null!;
    private User _admin = null!;
    private PaymentMethod _cash = null!;
    private PaymentMethod _giftPay = null!;

    public SalesReportGiftCardTests(ApiWebApplicationFactory factory) => _factory = factory;

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();
        using var mother = new TestDataMother(_factory.Services);
        _pos = await mother.PointOfSale().WithCode("SR-GC").WithName("Report GC POS").CreateAsync();
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
        _admin = await mother.Context.Users.FirstAsync(u => u.Username == "admin");
    }

    public Task DisposeAsync() => Task.CompletedTask;

    [Fact]
    public async Task SalesReport_CoverageOnRedemptionDay_NetsCashTopUp()
    {
        var redeemDate = DateTime.UtcNow;
        var issueDate = redeemDate.AddDays(-14);

        using var scope = _factory.Services.CreateScope();
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var giftCards = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        var operatorUser = await CreateOperatorAsync(scope);

        var issued = await giftCards.IssueAsync(new IssueGiftCardRequest
        {
            PointOfSaleId = _pos.Id,
            NominalAmount = 100m,
            ExpiryDate = DateOnly.FromDateTime(DateTime.UtcNow.AddDays(365)),
            PaymentMethodId = _cash.Id
        }, operatorUser.Id, false, null);
        await SetSaleDateAsync(ctx, issued.Card!.IssuanceSaleId, issueDate);
        (await ctx.Sales.FirstAsync(s => s.Id == issued.Card!.IssuanceSaleId)).SaleDate
            .Should().BeCloseTo(issueDate, TimeSpan.FromSeconds(1));

        using var mother = new TestDataMother(_factory.Services);
        var product = await mother.Product().WithSku("SR-150").WithName("Product 150").WithPrice(150m).CreateAsync();
        await mother.Inventory().WithProduct(product.Id).WithPointOfSale(_pos.Id).WithQuantity(5).CreateAsync();
        var sales = scope.ServiceProvider.GetRequiredService<ISalesService>();
        var bulk = await sales.CreateBulkSalesAsync(new CreateBulkSalesRequest
        {
            PointOfSaleId = _pos.Id,
            PaymentMethodId = _cash.Id,
            GiftCardCodes = new List<string> { issued.Card!.Code },
            Lines = new List<BulkSaleLineRequest> { new() { ProductId = product.Id, Quantity = 1 } }
        }, operatorUser.Id, false);
        bulk.Success.Should().BeTrue(bulk.ErrorMessage);
        await SetSaleDateAsync(ctx, bulk.Sales![0].Id, redeemDate);
        var applyEntry = await ctx.GiftCardCoverageEntries
            .FirstAsync(e => e.SaleId == bulk.Sales![0].Id && e.EntryType == GiftCardCoverageEntryType.Apply);
        applyEntry.EntryDate = redeemDate;
        var issuanceSale = await ctx.Sales.FirstAsync(s => s.Id == issued.Card!.IssuanceSaleId);
        issuanceSale.SaleDate = issueDate;
        await ctx.SaveChangesAsync();

        var dayStart = DateTime.SpecifyKind(redeemDate.Date, DateTimeKind.Utc);
        var dayEnd = dayStart.AddDays(1).AddTicks(-1);
        var report = await sales.GetSalesReportAsync(new SalesReportFilterRequest
        {
            StartDate = dayStart,
            EndDate = dayEnd,
            PointOfSaleId = _pos.Id,
            Page = 1,
            PageSize = 50
        }, _admin.Id, true);

        report.TotalAmount.Should().Be(50m);
    }

    [Fact]
    public async Task SalesReport_SameDayIssuanceAndRedemption_SubtractsCoverageOnce()
    {
        using var scope = _factory.Services.CreateScope();
        var giftCards = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        var operatorUser = await CreateOperatorAsync(scope);

        var issued = await giftCards.IssueAsync(new IssueGiftCardRequest
        {
            PointOfSaleId = _pos.Id,
            NominalAmount = 200m,
            ExpiryDate = DateOnly.FromDateTime(DateTime.UtcNow.AddDays(365)),
            PaymentMethodId = _cash.Id
        }, operatorUser.Id, false, null);
        issued.Success.Should().BeTrue(issued.ErrorMessage);

        using var mother = new TestDataMother(_factory.Services);
        var product = await mother.Product().WithSku("SR-29999").WithName("Product 29999").WithPrice(29999.05m).CreateAsync();
        await mother.Inventory().WithProduct(product.Id).WithPointOfSale(_pos.Id).WithQuantity(5).CreateAsync();
        var sales = scope.ServiceProvider.GetRequiredService<ISalesService>();
        var bulk = await sales.CreateBulkSalesAsync(new CreateBulkSalesRequest
        {
            PointOfSaleId = _pos.Id,
            PaymentMethodId = _cash.Id,
            GiftCardCodes = new List<string> { issued.Card!.Code },
            Lines = new List<BulkSaleLineRequest>
            {
                new() { ProductId = product.Id, Quantity = 1 },
                new() { ProductId = product.Id, Quantity = 1 }
            }
        }, operatorUser.Id, false);
        bulk.Success.Should().BeTrue(bulk.ErrorMessage);
        bulk.Sales.Should().HaveCount(2);
        bulk.Sales!.Sum(s => s.GiftCardCoverageAmount).Should().Be(200m);

        var dayStart = DateTime.SpecifyKind(DateTime.UtcNow.Date, DateTimeKind.Utc);
        var dayEnd = dayStart.AddDays(1).AddTicks(-1);
        var report = await sales.GetSalesReportAsync(new SalesReportFilterRequest
        {
            StartDate = dayStart,
            EndDate = dayEnd,
            PointOfSaleId = _pos.Id,
            Page = 1,
            PageSize = 50
        }, _admin.Id, true);

        report.TotalSalesCount.Should().Be(3);
        report.TotalAmount.Should().Be(59998.10m);
    }

    private static async Task SetSaleDateAsync(ApplicationDbContext ctx, Guid saleId, DateTime saleDate)
    {
        var sale = await ctx.Sales.FirstAsync(s => s.Id == saleId);
        sale.SaleDate = saleDate;
        await ctx.SaveChangesAsync();
    }

    private async Task<User> CreateOperatorAsync(IServiceScope scope)
    {
        using var mother = new TestDataMother(_factory.Services);
        return await mother.User().WithUsername("srgcop").AsOperator().AssignedTo(_pos.Id).CreateAsync();
    }
}
