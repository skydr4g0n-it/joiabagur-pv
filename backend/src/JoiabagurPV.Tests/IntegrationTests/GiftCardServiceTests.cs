using FluentAssertions;
using JoiabagurPV.Application.DTOs.GiftCards;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Constants;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;

namespace JoiabagurPV.Tests.IntegrationTests;

[Collection(IntegrationTestCollection.Name)]
public class GiftCardServiceTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private PointOfSale _pos = null!;
    private PointOfSale _otherPos = null!;
    private User _operator = null!;
    private PaymentMethod _cash = null!;
    private Guid _adminId;

    public GiftCardServiceTests(ApiWebApplicationFactory factory) => _factory = factory;

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();
        using var mother = new TestDataMother(_factory.Services);
        _pos = await mother.PointOfSale().WithCode("GC-POS-A").WithName("POS A").CreateAsync();
        _otherPos = await mother.PointOfSale().WithCode("GC-POS-B").WithName("POS B").CreateAsync();
        _cash = await mother.Context.PaymentMethods.FirstAsync(pm => pm.Code == "CASH");
        var giftMethodId = await mother.Context.PaymentMethods
            .Where(pm => pm.Code == GiftCardConstants.GiftCardPaymentMethodCode)
            .Select(pm => pm.Id)
            .FirstAsync();
        await GiftCardSeedHelper.EnsureGiftCardMethodAssignedToPosAsync(mother.Context, giftMethodId, _pos.Id, NullLogger.Instance);
        await GiftCardSeedHelper.EnsureGiftCardMethodAssignedToPosAsync(mother.Context, giftMethodId, _otherPos.Id, NullLogger.Instance);
        await EnsureCashAssignedAsync(mother.Context, _pos.Id, _cash.Id);
        await EnsureCashAssignedAsync(mother.Context, _otherPos.Id, _cash.Id);
        _operator = await mother.User().WithUsername("gcop").AsOperator().AssignedTo(_pos.Id).CreateAsync();
        _adminId = await mother.Context.Users.Where(u => u.Username == "admin").Select(u => u.Id).FirstAsync();
    }

    public Task DisposeAsync() => Task.CompletedTask;

    [Fact]
    public async Task Issue_PresetOnAssignedPos_CreatesSaleAndDoesNotMoveStock()
    {
        using var scope = _factory.Services.CreateScope();
        var sut = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var stockBefore = await ctx.Inventories.SumAsync(i => i.Quantity);

        var result = await sut.IssueAsync(new IssueGiftCardRequest
        {
            PointOfSaleId = _pos.Id,
            NominalAmount = 100m,
            ExpiryDate = DateOnly.FromDateTime(DateTime.UtcNow.AddDays(30)),
            PaymentMethodId = _cash.Id,
            HolderName = "Ana"
        }, _operator.Id, isAdmin: false, idempotencyKey: null);

        result.Success.Should().BeTrue();
        result.Card!.NominalAmount.Should().Be(100m);
        result.Card.Code.Should().StartWith("GC-");

        var stockAfter = await ctx.Inventories.SumAsync(i => i.Quantity);
        stockAfter.Should().Be(stockBefore);
        (await ctx.Sales.CountAsync(s => s.Id == result.Card.IssuanceSaleId)).Should().Be(1);
    }

    [Fact]
    public async Task Issue_UnassignedPos_ReturnsForbidden()
    {
        using var scope = _factory.Services.CreateScope();
        var sut = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        var result = await sut.IssueAsync(new IssueGiftCardRequest
        {
            PointOfSaleId = _otherPos.Id,
            NominalAmount = 100m,
            ExpiryDate = DateOnly.FromDateTime(DateTime.UtcNow.AddDays(30)),
            PaymentMethodId = _cash.Id
        }, _operator.Id, isAdmin: false, idempotencyKey: null);

        result.IsForbidden.Should().BeTrue();
    }

    [Fact]
    public async Task Issue_ExpiryToday_ReturnsBadRequest()
    {
        using var scope = _factory.Services.CreateScope();
        var validator = scope.ServiceProvider.GetRequiredService<FluentValidation.IValidator<IssueGiftCardRequest>>();
        var validation = await validator.ValidateAsync(new IssueGiftCardRequest
        {
            PointOfSaleId = _pos.Id,
            NominalAmount = 100m,
            ExpiryDate = DateOnly.FromDateTime(DateTime.UtcNow),
            PaymentMethodId = _cash.Id
        });
        validation.IsValid.Should().BeFalse();
    }

    [Fact]
    public async Task Issue_SameIdempotencyKey_DoesNotDuplicate()
    {
        using var scope = _factory.Services.CreateScope();
        var sut = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var req = new IssueGiftCardRequest
        {
            PointOfSaleId = _pos.Id,
            NominalAmount = 100m,
            ExpiryDate = DateOnly.FromDateTime(DateTime.UtcNow.AddDays(30)),
            PaymentMethodId = _cash.Id
        };
        var first = await sut.IssueAsync(req, _operator.Id, false, "idem-issue-1");
        var second = await sut.IssueAsync(req, _operator.Id, false, "idem-issue-1");
        second.Card!.Id.Should().Be(first.Card!.Id);
        (await ctx.GiftCards.CountAsync()).Should().Be(1);
    }

    [Fact]
    public async Task List_Operator_OmitsOtherPos()
    {
        using var scope = _factory.Services.CreateScope();
        var sut = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        await IssueAsync(sut, _pos.Id, _operator.Id);
        await IssueAsync(sut, _otherPos.Id, _adminId, true);

        var list = await sut.ListAsync(1, 50, _operator.Id, false);
        list.Items.Should().HaveCount(1);
        list.Items[0].PointOfSaleId.Should().Be(_pos.Id);
        (await ctx.GiftCards.CountAsync()).Should().Be(2);
    }

    [Fact]
    public async Task Reassign_Admin_WritesHistoryAndKeepsIssuancePos()
    {
        using var scope = _factory.Services.CreateScope();
        var sut = scope.ServiceProvider.GetRequiredService<IGiftCardService>();
        var ctx = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var issued = await IssueAsync(sut, _pos.Id, _operator.Id);
        var issuancePosBefore = await ctx.Sales.Where(s => s.Id == issued.IssuanceSaleId).Select(s => s.PointOfSaleId).FirstAsync();

        var result = await sut.ReassignAsync(issued.Id, new ReassignGiftCardRequest { ToPointOfSaleId = _otherPos.Id }, _adminId, true);
        result.Success.Should().BeTrue();
        result.Card!.PointOfSaleId.Should().Be(_otherPos.Id);
        (await ctx.Sales.Where(s => s.Id == issued.IssuanceSaleId).Select(s => s.PointOfSaleId).FirstAsync()).Should().Be(issuancePosBefore);
        (await ctx.GiftCardReassignments.CountAsync(r => r.GiftCardId == issued.Id)).Should().Be(1);
    }

    private static async Task EnsureCashAssignedAsync(ApplicationDbContext ctx, Guid posId, Guid cashId)
    {
        var exists = await ctx.PointOfSalePaymentMethods
            .AnyAsync(a => a.PointOfSaleId == posId && a.PaymentMethodId == cashId);
        if (!exists)
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

    private async Task<GiftCardDetailDto> IssueAsync(IGiftCardService sut, Guid posId, Guid userId, bool isAdmin = false)
    {
        var result = await sut.IssueAsync(new IssueGiftCardRequest
        {
            PointOfSaleId = posId,
            NominalAmount = 100m,
            ExpiryDate = DateOnly.FromDateTime(DateTime.UtcNow.AddDays(30)),
            PaymentMethodId = _cash.Id
        }, userId, isAdmin, null);
        result.Success.Should().BeTrue();
        return result.Card!;
    }
}
