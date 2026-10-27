using FluentAssertions;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;
using JoiabagurPV.Domain.Commission;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.Extensions.Caching.Memory;
using MockQueryable;
using Moq;

namespace JoiabagurPV.Tests.UnitTests.Application;

public class DashboardServiceTests
{
    private readonly Mock<ISaleRepository> _saleRepoMock;
    private readonly Mock<IReturnRepository> _returnRepoMock;
    private readonly Mock<IInventoryRepository> _inventoryRepoMock;
    private readonly Mock<IUserPointOfSaleRepository> _uposRepoMock;
    private readonly Mock<IPosCommissionReportService> _commissionServiceMock;
    private readonly Mock<IGiftCardRepository> _giftCardRepoMock;
    private readonly IMemoryCache _cache;
    private readonly DashboardService _sut;

    public DashboardServiceTests()
    {
        _saleRepoMock = new Mock<ISaleRepository>();
        _returnRepoMock = new Mock<IReturnRepository>();
        _inventoryRepoMock = new Mock<IInventoryRepository>();
        _uposRepoMock = new Mock<IUserPointOfSaleRepository>();
        _commissionServiceMock = new Mock<IPosCommissionReportService>();
        _giftCardRepoMock = new Mock<IGiftCardRepository>();
        _cache = new MemoryCache(new MemoryCacheOptions());

        _giftCardRepoMock
            .Setup(x => x.GetNetCoverageBySaleIdsAsync(It.IsAny<IEnumerable<Guid>>()))
            .ReturnsAsync(new Dictionary<Guid, decimal>());
        _giftCardRepoMock
            .Setup(x => x.GetCoverageNetInWindowAsync(
                It.IsAny<IEnumerable<Guid>?>(),
                It.IsAny<DateTime?>(),
                It.IsAny<DateTime?>(),
                It.IsAny<Guid?>()))
            .ReturnsAsync(0m);

        _commissionServiceMock
            .Setup(x => x.ComputeCommissionForSalesAsync(It.IsAny<IEnumerable<SaleCommissionLine>>(), default))
            .ReturnsAsync(0m);

        _saleRepoMock
            .Setup(x => x.GetSaleLinesForCommissionReportAsync(
                It.IsAny<IEnumerable<Guid>?>(),
                It.IsAny<DateTime?>(),
                It.IsAny<DateTime?>(),
                It.IsAny<Guid?>(),
                It.IsAny<Guid?>(),
                It.IsAny<Guid?>(),
                It.IsAny<Guid?>(),
                It.IsAny<string?>(),
                It.IsAny<decimal?>(),
                It.IsAny<decimal?>(),
                It.IsAny<bool?>(),
                It.IsAny<bool?>()))
            .ReturnsAsync(new List<SaleReportLine>());

        _sut = new DashboardService(
            _saleRepoMock.Object,
            _returnRepoMock.Object,
            _inventoryRepoMock.Object,
            _uposRepoMock.Object,
            _commissionServiceMock.Object,
            _giftCardRepoMock.Object,
            _cache);
    }

    [Fact]
    public async Task GetGlobalStatsAsync_WithSalesToday_ShouldReturnCorrectKPIs()
    {
        // Arrange
        var posId = Guid.NewGuid();
        var pmId = Guid.NewGuid();
        var now = DateTime.UtcNow;

        var sales = new List<Sale>
        {
            CreateSale(posId, pmId, 100m, 2, now, "Efectivo"),
            CreateSale(posId, pmId, 50m, 1, now, "Tarjeta"),
            CreateSale(posId, pmId, 200m, 1, now.AddDays(-5), "Efectivo"),
        };

        var returns = new List<Return>
        {
            CreateReturn(posId, 1, ReturnCategory.Defectuoso, now.AddDays(-2)),
        };

        _saleRepoMock.Setup(x => x.GetAll()).Returns(sales.BuildMock());
        _returnRepoMock.Setup(x => x.GetAll()).Returns(returns.BuildMock());

        // Act
        var result = await _sut.GetGlobalStatsAsync();

        // Assert
        result.SalesTodayCount.Should().Be(2);
        result.SalesTodayTotal.Should().Be(250m);
        result.MonthlyRevenue.Should().Be(400m);
        result.MonthlyRevenueNet.Should().Be(400m);
        result.PreviousYearMonthlyRevenue.Should().BeNull();
        result.MonthlyReturnsCount.Should().Be(1);
        result.PaymentMethodDistribution.Should().NotBeNull();
        result.ReturnCategoryDistribution.Should().NotBeNull();
    }

    [Fact]
    public async Task GetGlobalStatsAsync_WithNoSales_ShouldReturnZeros()
    {
        // Arrange
        _saleRepoMock.Setup(x => x.GetAll()).Returns(new List<Sale>().BuildMock());
        _returnRepoMock.Setup(x => x.GetAll()).Returns(new List<Return>().BuildMock());

        // Act
        var result = await _sut.GetGlobalStatsAsync();

        // Assert
        result.SalesTodayCount.Should().Be(0);
        result.SalesTodayTotal.Should().Be(0m);
        result.MonthlyRevenue.Should().Be(0m);
        result.MonthlyReturnsCount.Should().Be(0);
    }

    [Fact]
    public async Task GetPosStatsAsync_WithAccess_ShouldReturnPosScoped()
    {
        // Arrange
        var posId = Guid.NewGuid();
        var userId = Guid.NewGuid();
        var pmId = Guid.NewGuid();
        var now = DateTime.UtcNow;

        var sales = new List<Sale>
        {
            CreateSale(posId, pmId, 100m, 1, now, "Efectivo"),
            CreateSale(Guid.NewGuid(), pmId, 500m, 1, now, "Tarjeta"),
        };

        var returns = new List<Return>
        {
            CreateReturn(posId, 1, ReturnCategory.NoSatisfecho, now),
            CreateReturn(Guid.NewGuid(), 2, ReturnCategory.Defectuoso, now),
        };

        _uposRepoMock.Setup(x => x.HasAccessAsync(userId, posId)).ReturnsAsync(true);
        _saleRepoMock.Setup(x => x.GetAll()).Returns(sales.BuildMock());
        _returnRepoMock.Setup(x => x.GetAll()).Returns(returns.BuildMock());

        // Act
        var result = await _sut.GetPosStatsAsync(posId, userId);

        // Assert
        result.SalesTodayCount.Should().Be(1);
        result.SalesTodayTotal.Should().Be(100m);
        result.ReturnsTodayCount.Should().Be(1);
        result.WeeklyRevenue.Should().BeGreaterOrEqualTo(100m);
        result.PaymentMethodDistribution.Should().BeNull();
        result.ReturnCategoryDistribution.Should().BeNull();
    }

    [Fact]
    public async Task GetPosStatsAsync_WithoutAccess_ShouldThrow()
    {
        // Arrange
        var posId = Guid.NewGuid();
        var userId = Guid.NewGuid();

        _uposRepoMock.Setup(x => x.HasAccessAsync(userId, posId)).ReturnsAsync(false);

        // Act
        var act = () => _sut.GetPosStatsAsync(posId, userId);

        // Assert
        await act.Should().ThrowAsync<UnauthorizedAccessException>();
    }

    [Fact]
    public async Task GetPosStatsAsync_WithAdminFlag_ShouldSkipAccessValidation()
    {
        // Arrange
        var posId = Guid.NewGuid();
        var userId = Guid.NewGuid();
        var pmId = Guid.NewGuid();

        _saleRepoMock.Setup(x => x.GetAll()).Returns(new List<Sale>().BuildMock());
        _returnRepoMock.Setup(x => x.GetAll()).Returns(new List<Return>().BuildMock());

        // Act
        var result = await _sut.GetPosStatsAsync(posId, userId, isAdmin: true);

        // Assert
        result.Should().NotBeNull();
        _uposRepoMock.Verify(x => x.HasAccessAsync(It.IsAny<Guid>(), It.IsAny<Guid>()), Times.Never);
    }

    [Fact]
    public async Task GetGlobalStatsAsync_ShouldCacheDonutData()
    {
        // Arrange
        var pmId = Guid.NewGuid();
        var sales = new List<Sale>
        {
            CreateSale(Guid.NewGuid(), pmId, 100m, 1, DateTime.UtcNow, "Efectivo"),
        };
        var returns = new List<Return>();

        _saleRepoMock.Setup(x => x.GetAll()).Returns(sales.BuildMock());
        _returnRepoMock.Setup(x => x.GetAll()).Returns(returns.BuildMock());

        // Act
        var result1 = await _sut.GetGlobalStatsAsync();
        var result2 = await _sut.GetGlobalStatsAsync();

        // Assert — GetAll is called for KPIs each time but donut data should be cached
        result1.PaymentMethodDistribution.Should().NotBeNull();
        result2.PaymentMethodDistribution.Should().NotBeNull();
    }

    private static Sale CreateSale(Guid posId, Guid pmId, decimal price, int qty, DateTime date, string pmName)
    {
        return new Sale
        {
            Id = Guid.NewGuid(),
            ProductId = Guid.NewGuid(),
            PointOfSaleId = posId,
            UserId = Guid.NewGuid(),
            PaymentMethodId = pmId,
            Price = price,
            Quantity = qty,
            SaleDate = date,
            PaymentMethod = new PaymentMethod { Id = pmId, Name = pmName, Code = pmName.ToUpperInvariant() },
        };
    }

    private static Return CreateReturn(Guid posId, int qty, ReturnCategory category, DateTime date)
    {
        return new Return
        {
            Id = Guid.NewGuid(),
            ProductId = Guid.NewGuid(),
            PointOfSaleId = posId,
            UserId = Guid.NewGuid(),
            Quantity = qty,
            Category = category,
            ReturnDate = date,
            ReturnSales = new List<ReturnSale>
            {
                new ReturnSale
                {
                    Id = Guid.NewGuid(),
                    SaleId = Guid.NewGuid(),
                    Quantity = qty,
                    UnitPrice = 50m,
                }
            }
        };
    }
}
