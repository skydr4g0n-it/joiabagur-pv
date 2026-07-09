using FluentAssertions;
using JoiabagurPV.API.Controllers;
using JoiabagurPV.Application.DTOs.Inventory;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace JoiabagurPV.Tests.UnitTests.API;

public class InventoryMovementReportControllerTests
{
    private readonly Mock<IInventoryMovementReportService> _reportServiceMock = new();
    private readonly InventoryMovementReportController _controller;

    public InventoryMovementReportControllerTests()
    {
        _reportServiceMock
            .Setup(s => s.GetReportAsync(It.IsAny<InventoryMovementReportFilterRequest>()))
            .ReturnsAsync(new InventoryMovementReportResponse());
        _controller = new InventoryMovementReportController(_reportServiceMock.Object);
    }

    [Fact]
    public async Task GetReport_MissingDates_ReturnsBadRequest()
    {
        var result = await _controller.GetReport(new InventoryMovementReportFilterRequest());

        result.Should().BeOfType<BadRequestObjectResult>();
    }

    [Fact]
    public async Task GetReport_InvalidOutputModel_ReturnsBadRequest()
    {
        var request = new InventoryMovementReportFilterRequest
        {
            StartDate = new DateTime(2025, 1, 1),
            EndDate = new DateTime(2025, 1, 31),
            OutputModel = "unknown"
        };

        var result = await _controller.GetReport(request);

        result.Should().BeOfType<BadRequestObjectResult>();
    }

    [Fact]
    public async Task GetReport_OutputModelOmitted_DefaultsToSummary()
    {
        var request = new InventoryMovementReportFilterRequest
        {
            StartDate = new DateTime(2025, 1, 1),
            EndDate = new DateTime(2025, 1, 31)
        };

        await _controller.GetReport(request);

        request.OutputModel.Should().Be("summary");
    }
}
