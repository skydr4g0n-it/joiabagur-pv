using JoiabagurPV.Application.DTOs.Sales;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JoiabagurPV.API.Controllers;

[ApiController]
[Route("api/reports/sales")]
[Authorize]
public class SalesReportController : ControllerBase
{
    private readonly ISalesService _salesService;
    private readonly ICurrentUserService _currentUserService;
    private readonly ILogger<SalesReportController> _logger;

    public SalesReportController(
        ISalesService salesService,
        ICurrentUserService currentUserService,
        ILogger<SalesReportController> logger)
    {
        _salesService = salesService;
        _currentUserService = currentUserService;
        _logger = logger;
    }

    [HttpGet]
    [ProducesResponseType(typeof(SalesReportResponse), StatusCodes.Status200OK)]
    public async Task<IActionResult> GetSalesReport([FromQuery] SalesReportFilterRequest request)
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized(new { message = "Usuario no autenticado." });
        }

        if (request.StartDate.HasValue)
            request.StartDate = DateTime.SpecifyKind(request.StartDate.Value, DateTimeKind.Utc);
        if (request.EndDate.HasValue)
            request.EndDate = DateTime.SpecifyKind(request.EndDate.Value.Date.AddDays(1).AddTicks(-1), DateTimeKind.Utc);

        var result = await _salesService.GetSalesReportAsync(
            request,
            _currentUserService.UserId.Value,
            _currentUserService.IsAdmin);

        return Ok(result);
    }

    [HttpGet("export")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> ExportSalesReport([FromQuery] SalesReportFilterRequest request)
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized(new { message = "Usuario no autenticado." });
        }

        if (request.StartDate.HasValue)
            request.StartDate = DateTime.SpecifyKind(request.StartDate.Value, DateTimeKind.Utc);
        if (request.EndDate.HasValue)
            request.EndDate = DateTime.SpecifyKind(request.EndDate.Value.Date.AddDays(1).AddTicks(-1), DateTimeKind.Utc);

        try
        {
            var (stream, _) = await _salesService.ExportSalesReportAsync(
                request,
                _currentUserService.UserId.Value,
                _currentUserService.IsAdmin);

            var fileName = $"reporte-ventas-{DateTime.UtcNow:yyyy-MM-dd-HH-mm}.xlsx";
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
                message = "Hay más de 10.000 ventas. Ajuste los filtros para exportar.",
                totalCount
            });
        }
    }
}
