using JoiabagurPV.Application.DTOs.Inventory;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JoiabagurPV.API.Controllers;

[ApiController]
[Route("api/reports/inventory-movements")]
[Authorize(Roles = "Administrator")]
public class InventoryMovementReportController : ControllerBase
{
    private readonly IInventoryMovementReportService _reportService;

    public InventoryMovementReportController(IInventoryMovementReportService reportService)
    {
        _reportService = reportService;
    }

    [HttpGet]
    [ProducesResponseType(typeof(InventoryMovementReportResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<IActionResult> GetReport([FromQuery] InventoryMovementReportFilterRequest request)
    {
        var badRequest = ValidateAndNormalizeRequest(request);
        if (badRequest is not null)
        {
            return badRequest;
        }

        var result = await _reportService.GetReportAsync(request);
        return Ok(result);
    }

    [HttpGet("export")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> ExportReport([FromQuery] InventoryMovementReportFilterRequest request)
    {
        var badRequest = ValidateAndNormalizeRequest(request);
        if (badRequest is not null)
        {
            return badRequest;
        }

        try
        {
            var (stream, _) = await _reportService.ExportReportAsync(request);

            var fileName = $"reporte-movimientos-inventario-{DateTime.UtcNow:yyyy-MM-dd-HH-mm}.xlsx";
            return File(
                stream.ToArray(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                fileName);
        }
        catch (InvalidOperationException ex) when (ex.Message.StartsWith("EXPORT_LIMIT_EXCEEDED:"))
        {
            var totalCount = int.Parse(ex.Message.Split(':')[1]);
            return Conflict(new
            {
                message = "Más de 50.000 productos en el resultado. Ajuste los filtros para exportar.",
                totalCount
            });
        }
    }

    private BadRequestObjectResult? ValidateAndNormalizeRequest(InventoryMovementReportFilterRequest request)
    {
        if (!request.StartDate.HasValue || !request.EndDate.HasValue)
        {
            return BadRequest(new { message = "startDate y endDate son obligatorios." });
        }

        request.OutputModel = string.IsNullOrWhiteSpace(request.OutputModel)
            ? "summary"
            : request.OutputModel.Trim().ToLowerInvariant();

        if (request.OutputModel is not ("summary" or "detail"))
        {
            return BadRequest(new { message = "outputModel debe ser summary o detail." });
        }

        request.ProductSearch = string.IsNullOrWhiteSpace(request.ProductSearch)
            ? null
            : request.ProductSearch.Trim();
        request.StartDate = DateTime.SpecifyKind(request.StartDate.Value, DateTimeKind.Utc);
        request.EndDate = DateTime.SpecifyKind(request.EndDate.Value.Date.AddDays(1).AddTicks(-1), DateTimeKind.Utc);

        return null;
    }
}
