using FluentValidation;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JoiabagurPV.API.Controllers;

/// <summary>
/// Assisted-search telemetry. Exposes exactly one operation: recording the selection an
/// operator made on a search the backend already stored.
/// </summary>
/// <remarks>
/// <para>
/// The search half of the event is not written through HTTP. It is written by the search
/// endpoint itself, which is the only place that knows the result origin, the trace identifier,
/// the real retrieval latency and the list that was actually returned.
/// </para>
/// <para>
/// There is deliberately no read route — no retrieval by identifier, no listing, no
/// aggregation. These events are analysed with direct SQL. That is also why this controller
/// does not derive from <c>BaseController</c>, whose creation helper builds a location header
/// pointing at a <c>GetById</c> that does not exist here.
/// </para>
/// <para>
/// The route carries no version, like the other eighteen controllers. Versioning is applied at
/// the boundary that needs it — the frozen <c>/v1</c> contract with <c>jbg-ai</c>, which is a
/// separately deployed service — and not between a SPA and an API that ship together.
/// </para>
/// </remarks>
[ApiController]
[Route("api/ai/search-events")]
[Authorize]
public class AiSearchEventsController : ControllerBase
{
    private readonly IProductSearchEventService _searchEventService;
    private readonly ICurrentUserService _currentUserService;
    private readonly IValidator<RecordSearchSelectionRequest> _selectionValidator;

    public AiSearchEventsController(
        IProductSearchEventService searchEventService,
        ICurrentUserService currentUserService,
        IValidator<RecordSearchSelectionRequest> selectionValidator)
    {
        _searchEventService = searchEventService;
        _currentUserService = currentUserService;
        _selectionValidator = selectionValidator;
    }

    /// <summary>
    /// Records the product the operator selected from the results of a search event.
    /// </summary>
    /// <param name="id">The search event the selection belongs to.</param>
    /// <param name="request">The selected product.</param>
    /// <returns>No content on success.</returns>
    [HttpPost("{id:guid}/selection")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> RecordSelection(
        Guid id,
        [FromBody] RecordSearchSelectionRequest request)
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized(new { message = "User not authenticated." });
        }

        // Validated explicitly: this project registers validators but wires no automatic
        // pipeline, so an uninvoked validator is worse than none — it looks like validation.
        // Without it an empty product identifier would persist a junk row with a null rank.
        var validationResult = await _selectionValidator.ValidateAsync(request);
        if (!validationResult.IsValid)
        {
            return BadRequest(new { errors = validationResult.Errors.Select(e => e.ErrorMessage) });
        }

        var outcome = await _searchEventService.RecordSelectionAsync(
            id,
            _currentUserService.UserId.Value,
            request.ProductId);

        return outcome switch
        {
            SelectionOutcome.EventNotFound => NotFound(),

            // No administrator exception, unlike the point-of-sale checks elsewhere. A search
            // event records what one specific person did; letting anyone else complete it would
            // allow corrupting the data without leaving a trace.
            SelectionOutcome.NotOwner => Forbid(),

            _ => NoContent()
        };
    }
}
