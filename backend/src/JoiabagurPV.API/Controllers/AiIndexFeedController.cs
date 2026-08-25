using JoiabagurPV.API.Filters;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Mvc;

namespace JoiabagurPV.API.Controllers;

/// <summary>
/// HTTP pull surface for catalog and POS indexation. Authenticated only by
/// <c>X-Index-Feed-Key</c>. There is no <c>[Authorize]</c> on purpose: a user JWT must not
/// open these routes.
/// </summary>
[ApiController]
[Route("api/ai/index-feed")]
[IndexFeedKey]
public class AiIndexFeedController : ControllerBase
{
    private readonly IIndexFeedService _feedService;

    public AiIndexFeedController(IIndexFeedService feedService)
    {
        _feedService = feedService;
    }

    /// <summary>Catalog feed, page size 50, keyset on <c>(watermark, productId)</c>.</summary>
    [HttpGet("catalog")]
    [ProducesResponseType(typeof(IndexFeedPageDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    public async Task<ActionResult<IndexFeedPageDto>> GetCatalog(
        [FromQuery] DateTime? since,
        [FromQuery] Guid? sinceId,
        CancellationToken cancellationToken)
    {
        var page = await _feedService.GetCatalogPageAsync(since, sinceId, cancellationToken);
        return Ok(page);
    }

    /// <summary>
    /// Sparse POS availability feed, page size 200, keyset on
    /// <c>(watermark, inventoryId)</c>.
    /// </summary>
    [HttpGet("pos-availability")]
    [ProducesResponseType(typeof(IndexFeedPageDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    public async Task<ActionResult<IndexFeedPageDto>> GetPosAvailability(
        [FromQuery] DateTime? since,
        [FromQuery] Guid? sinceId,
        CancellationToken cancellationToken)
    {
        var page = await _feedService.GetPosAvailabilityPageAsync(since, sinceId, cancellationToken);
        return Ok(page);
    }
}
