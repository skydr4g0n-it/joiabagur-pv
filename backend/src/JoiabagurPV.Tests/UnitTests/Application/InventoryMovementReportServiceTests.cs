using FluentAssertions;
using JoiabagurPV.Application.DTOs.Inventory;
using JoiabagurPV.Application.Services;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Moq;

namespace JoiabagurPV.Tests.UnitTests.Application;

public class InventoryMovementReportServiceTests
{
    private readonly Mock<IInventoryMovementRepository> _movementRepositoryMock = new();
    private readonly InventoryMovementReportService _service;

    public InventoryMovementReportServiceTests()
    {
        _service = new InventoryMovementReportService(_movementRepositoryMock.Object);
    }

    [Fact]
    public async Task GetReportAsync_OutputModelOmitted_ReturnsSummaryRows()
    {
        var productId = Guid.NewGuid();
        _movementRepositoryMock
            .Setup(r => r.GetMovementSummaryByProductAsync(
                It.IsAny<DateTime>(),
                It.IsAny<DateTime>(),
                null,
                null))
            .ReturnsAsync(new List<MovementSummaryProjection>
            {
                new(productId, "Anillo", "JOY-001", 5, 2, 3)
            });

        var result = await _service.GetReportAsync(CreateRequest(outputModel: null));

        result.Items.Should().ContainSingle();
        result.Items[0].Should().BeOfType<InventoryMovementSummaryRow>()
            .Which.ProductId.Should().Be(productId);
    }

    [Fact]
    public async Task GetReportAsync_ProductSearchProvided_PassesSearchToSummaryRepository()
    {
        var request = CreateRequest(productSearch: "ring");
        _movementRepositoryMock
            .Setup(r => r.GetMovementSummaryByProductAsync(
                request.StartDate!.Value,
                request.EndDate!.Value,
                null,
                "ring"))
            .ReturnsAsync(new List<MovementSummaryProjection>());

        await _service.GetReportAsync(request);

        _movementRepositoryMock.Verify(r => r.GetMovementSummaryByProductAsync(
            request.StartDate!.Value,
            request.EndDate!.Value,
            null,
            "ring"), Times.Once);
    }

    [Fact]
    public async Task GetReportAsync_DetailOutput_ReturnsSaleAndReturnIds()
    {
        var saleId = Guid.NewGuid();
        var movementId = Guid.NewGuid();
        _movementRepositoryMock
            .Setup(r => r.GetMovementDetailRowsAsync(
                It.IsAny<DateTime>(),
                It.IsAny<DateTime>(),
                null,
                null,
                1,
                20))
            .ReturnsAsync((new List<MovementDetailProjection>
            {
                new(
                    movementId,
                    Guid.NewGuid(),
                    Guid.NewGuid(),
                    "Anillo",
                    "JOY-001",
                    Guid.NewGuid(),
                    "Centro",
                    MovementType.Sale,
                    -1,
                    10,
                    9,
                    Guid.NewGuid(),
                    "Admin User",
                    null,
                    DateTime.UtcNow,
                    saleId,
                    null)
            }, 1));

        var result = await _service.GetReportAsync(CreateRequest(outputModel: "detail"));

        result.Items.Should().ContainSingle();
        var detail = result.Items[0].Should().BeOfType<InventoryMovementDetailRow>().Subject;
        detail.Id.Should().Be(movementId);
        detail.SaleId.Should().Be(saleId);
        detail.ReturnId.Should().BeNull();
    }

    [Fact]
    public async Task ExportReportAsync_DetailOutput_IgnoresSummarySorting()
    {
        _movementRepositoryMock
            .Setup(r => r.GetMovementDetailRowsAsync(
                It.IsAny<DateTime>(),
                It.IsAny<DateTime>(),
                null,
                null,
                null,
                null))
            .ReturnsAsync((new List<MovementDetailProjection>(), 0));

        await _service.ExportReportAsync(CreateRequest(outputModel: "detail", sortBy: "difference"));

        _movementRepositoryMock.Verify(r => r.GetMovementSummaryByProductAsync(
            It.IsAny<DateTime>(),
            It.IsAny<DateTime>(),
            It.IsAny<Guid?>(),
            It.IsAny<string?>()), Times.Never);
    }

    private static InventoryMovementReportFilterRequest CreateRequest(
        string? outputModel = "summary",
        string? productSearch = null,
        string? sortBy = null)
    {
        return new InventoryMovementReportFilterRequest
        {
            OutputModel = outputModel,
            ProductSearch = productSearch,
            StartDate = new DateTime(2025, 1, 1, 0, 0, 0, DateTimeKind.Utc),
            EndDate = new DateTime(2025, 1, 31, 23, 59, 59, DateTimeKind.Utc),
            Page = 1,
            PageSize = 20,
            SortBy = sortBy,
            SortDirection = "desc"
        };
    }
}
