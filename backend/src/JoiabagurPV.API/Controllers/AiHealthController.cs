using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JoiabagurPV.API.Controllers;

/// <summary>
/// State of the jbg-ai service. Exposes exactly one operation: reading its health report.
/// </summary>
/// <remarks>
/// <para>
/// This endpoint exists because the browser <strong>cannot</strong> ask jbg-ai directly. The AI
/// service is private by design — it publishes no port, and the demo security group opens only
/// the two the reverse proxy serves — so without this hop there is no status card at all.
/// </para>
/// <para>
/// Administrator only. The report describes infrastructure: whether a database is reachable, how
/// many documents are indexed, whether a provider credential is configured. An operator has no
/// reason to see any of it.
/// </para>
/// <para>
/// It is <em>not</em> the same thing as <c>api/health</c>, which is anonymous and answers for
/// this API's own liveness. This one answers for a different service, and answering it requires
/// crossing a trust boundary.
/// </para>
/// <para>
/// One controller per capability, like the rest of <c>api/ai</c>, and no route version for the
/// same reason they carry none: versioning belongs at the boundary with the separately deployed
/// jbg-ai, not between a SPA and an API that ship together.
/// </para>
/// </remarks>
[ApiController]
[Route("api/ai/health")]
[Authorize(Roles = "Administrator")]
public class AiHealthController : ControllerBase
{
    private readonly IAiGatewayClient _gateway;
    private readonly ILogger<AiHealthController> _logger;

    public AiHealthController(
        IAiGatewayClient gateway,
        ILogger<AiHealthController> logger)
    {
        _gateway = gateway;
        _logger = logger;
    }

    /// <summary>
    /// Reads the health report of the jbg-ai service.
    /// </summary>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>
    /// The report on success, or 503 with a reason when the service cannot be reached.
    /// </returns>
    /// <remarks>
    /// The 503 body says only that the service did not answer. It carries no address, no
    /// connection string and no exception detail — the same discipline the response itself
    /// follows: nothing here may become a credential leak on an administrator's screen.
    /// </remarks>
    [HttpGet]
    [ProducesResponseType(typeof(AiHealthResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status503ServiceUnavailable)]
    public async Task<IActionResult> Get(CancellationToken cancellationToken)
    {
        try
        {
            // The gateway's health client carries no circuit breaker: an open retrieval circuit
            // must not stop the card from reporting, because that is exactly when somebody is
            // looking at it.
            var report = await _gateway.HealthAsync(cancellationToken);
            return Ok(report);
        }
        catch (AiUnavailableException ex)
        {
            // Logged with the exception, answered without it. The log is for whoever operates
            // the system; the body is for a browser.
            _logger.LogWarning(ex, "ai_health_probe_unavailable");

            return StatusCode(
                StatusCodes.Status503ServiceUnavailable,
                new { message = "El servicio de IA no está disponible." });
        }
    }
}
