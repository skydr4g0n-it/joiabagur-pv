using JoiabagurPV.Application.DTOs.Dashboard;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JoiabagurPV.API.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class DashboardController : ControllerBase
{
    private readonly IDashboardService _dashboardService;
    private readonly ICurrentUserService _currentUserService;
    private readonly ILogger<DashboardController> _logger;

    public DashboardController(
        IDashboardService dashboardService,
        ICurrentUserService currentUserService,
        ILogger<DashboardController> logger)
    {
        _dashboardService = dashboardService;
        _currentUserService = currentUserService;
        _logger = logger;
    }

    [HttpGet("stats")]
    [ProducesResponseType(typeof(DashboardStatsDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    public async Task<ActionResult<DashboardStatsDto>> GetStats([FromQuery] Guid? posId)
    {
        if (!_currentUserService.UserId.HasValue)
            return Unauthorized(new { message = "Usuario no autenticado." });

        var userId = _currentUserService.UserId.Value;
        var isAdmin = _currentUserService.IsAdmin;

        try
        {
            if (posId.HasValue)
            {
                var stats = await _dashboardService.GetPosStatsAsync(posId.Value, userId, isAdmin);
                return Ok(stats);
            }

            if (!isAdmin)
                return Forbid();

            var globalStats = await _dashboardService.GetGlobalStatsAsync();
            return Ok(globalStats);
        }
        catch (UnauthorizedAccessException)
        {
            return Forbid();
        }
    }

    [HttpGet("low-stock")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(PaginatedLowStockResult), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    public async Task<ActionResult<PaginatedLowStockResult>> GetLowStock(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 10)
    {
        pageSize = Math.Clamp(pageSize, 1, 50);
        page = Math.Max(1, page);

        var result = await _dashboardService.GetLowStockAsync(page, pageSize);
        return Ok(result);
    }
}
