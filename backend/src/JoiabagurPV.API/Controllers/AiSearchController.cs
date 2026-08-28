using FluentValidation;
using JoiabagurPV.API.Extensions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace JoiabagurPV.API.Controllers;

/// <summary>
/// Assisted catalog search. Exposes exactly one operation: running a natural-language search
/// for one point of sale.
/// </summary>
/// <remarks>
/// <para>
/// The AI service proposes candidates; this endpoint applies the truth. Price, stock and what
/// the shop actually carries come from the transactional catalog, never from the AI response —
/// which is contractually forbidden from carrying them.
/// </para>
/// <para>
/// The search never fails because of the AI. Every failure mode of the gateway degrades to a
/// lexical searcher and is reported through <c>aiAvailable</c>, so the caller can say so on
/// screen rather than showing an error.
/// </para>
/// <para>
/// The route carries no version, like the other controllers under <c>api/ai</c>. Versioning is
/// applied at the boundary that needs it — the frozen contract with the separately deployed
/// <c>jbg-ai</c> — and not between a SPA and an API that ship together.
/// </para>
/// </remarks>
[ApiController]
[Route("api/ai/search")]
[Authorize]
[EnableRateLimiting(RateLimitPolicies.AiSearch)]
public class AiSearchController : ControllerBase
{
    private readonly IAssistedSearchService _searchService;
    private readonly ICurrentUserService _currentUserService;
    private readonly IValidator<AssistedSearchRequest> _validator;

    public AiSearchController(
        IAssistedSearchService searchService,
        ICurrentUserService currentUserService,
        IValidator<AssistedSearchRequest> validator)
    {
        _searchService = searchService;
        _currentUserService = currentUserService;
        _validator = validator;
    }

    /// <summary>
    /// Runs an assisted search for a point of sale.
    /// </summary>
    /// <param name="request">Query, point of sale, page size, episode and quick filters.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Results in retrieval order, plus the state of the assisted path.</returns>
    [HttpPost]
    [ProducesResponseType(typeof(AssistedSearchResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status429TooManyRequests)]
    public async Task<IActionResult> Search(
        [FromBody] AssistedSearchRequest? request,
        CancellationToken cancellationToken)
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized(new { message = "User not authenticated." });
        }

        // SuppressModelStateInvalidFilter is on, so a body that fails to bind still reaches the
        // action as null and FluentValidation would throw on it.
        if (request is null)
        {
            return BadRequest(new { errors = new[] { "La petición de búsqueda es obligatoria." } });
        }

        // Validated explicitly: this project registers validators but wires no automatic
        // pipeline, so an uninvoked validator is worse than none — it looks like validation.
        var validationResult = await _validator.ValidateAsync(request, cancellationToken);
        if (!validationResult.IsValid)
        {
            return BadRequest(new { errors = validationResult.Errors.Select(e => e.ErrorMessage) });
        }

        var result = await _searchService.SearchAsync(
            request,
            _currentUserService.UserId.Value,
            _currentUserService.Role ?? "Operator",
            _currentUserService.IsAdmin,
            cancellationToken);

        return result.Outcome switch
        {
            // The point of sale exists but this operator is not assigned to it. Administrators
            // are granted the exception inside the service, explicitly and only for active
            // points of sale.
            AssistedSearchOutcome.PointOfSaleForbidden => Forbid(),

            // Unknown or inactive point of sale. A validation problem rather than an
            // authorisation one: nobody, whatever their role, can search a shop that is closed.
            AssistedSearchOutcome.PointOfSaleUnavailable => BadRequest(new
            {
                errors = new[] { "El punto de venta no existe o no está activo." }
            }),

            _ => Ok(result.Response)
        };
    }
}
