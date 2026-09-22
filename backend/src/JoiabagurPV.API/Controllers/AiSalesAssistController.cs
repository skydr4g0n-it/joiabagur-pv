using FluentValidation;
using JoiabagurPV.API.Extensions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace JoiabagurPV.API.Controllers;

/// <summary>
/// The two routes of the sale card, both anchored to one product: its sale assistance and its
/// substitutes (C34).
/// </summary>
/// <remarks>
/// <para>
/// No free question without a product and no agent route: in both, the generated argument speaks
/// about several pieces with the same price and stock placeholders, so there is no single product
/// to resolve them against. The fix belongs to the AI service.
/// </para>
/// <para>
/// Two routes rather than one because they cost different things — substitutes answer in under a
/// second, the argument in about four — so the card asks for both at once and paints the
/// substitutes while the argument is still on its way.
/// </para>
/// <para>
/// Neither ever answers a server error because of the AI: the assistance degrades to the card read
/// from the catalog, and substitutes say which of four things happened.
/// </para>
/// </remarks>
[ApiController]
[Route("api/ai/products")]
[Authorize]
public class AiSalesAssistController : ControllerBase
{
    private readonly ISalesAssistService _salesAssistService;
    private readonly ISubstitutesService _substitutesService;
    private readonly ICurrentUserService _currentUserService;
    private readonly IValidator<SalesAssistRequest> _salesAssistValidator;
    private readonly IValidator<SubstitutesRequest> _substitutesValidator;

    public AiSalesAssistController(
        ISalesAssistService salesAssistService,
        ISubstitutesService substitutesService,
        ICurrentUserService currentUserService,
        IValidator<SalesAssistRequest> salesAssistValidator,
        IValidator<SubstitutesRequest> substitutesValidator)
    {
        _salesAssistService = salesAssistService;
        _substitutesService = substitutesService;
        _currentUserService = currentUserService;
        _salesAssistValidator = salesAssistValidator;
        _substitutesValidator = substitutesValidator;
    }

    /// <summary>
    /// The sale assistance of a product: its group, warnings, citations and argument.
    /// </summary>
    /// <param name="productId">The anchored product.</param>
    /// <param name="request">Point of sale and optional question, in the body.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <remarks>
    /// A write-free POST, and the question travels in the body only: it is free text about a
    /// customer, and a URL is recorded by proxies, browsers and caches. Nothing in the query
    /// string is read.
    /// </remarks>
    [HttpPost("{productId:guid}/sales-assist")]
    [EnableRateLimiting(RateLimitPolicies.AiSalesAssist)]
    [ProducesResponseType(typeof(SalesAssistResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status429TooManyRequests)]
    public async Task<IActionResult> SalesAssist(
        Guid productId,
        [FromBody] SalesAssistRequest? request,
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
            return BadRequest(new { errors = new[] { "La petición de asistencia es obligatoria." } });
        }

        // Validated explicitly: validators are registered but no automatic pipeline runs them, and
        // an uninvoked validator is worse than none — it looks like validation.
        var validation = await _salesAssistValidator.ValidateAsync(request, cancellationToken);
        if (!validation.IsValid)
        {
            return BadRequest(new { errors = validation.Errors.Select(e => e.ErrorMessage) });
        }

        var result = await _salesAssistService.AssistAsync(
            productId,
            request,
            _currentUserService.UserId.Value,
            _currentUserService.Role ?? "Operator",
            _currentUserService.IsAdmin,
            cancellationToken);

        return Map(result.Outcome) ?? Ok(result.Response);
    }

    /// <summary>
    /// The substitutes of a product that the point of sale can sell today.
    /// </summary>
    /// <param name="productId">The product a substitute is wanted for.</param>
    /// <param name="request">Point of sale and optional page size, in the query string.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <remarks>
    /// Rate-limited by the assisted search policy: this route calls no model provider.
    /// </remarks>
    [HttpGet("{productId:guid}/substitutes")]
    [EnableRateLimiting(RateLimitPolicies.AiSearch)]
    [ProducesResponseType(typeof(SubstitutesResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status429TooManyRequests)]
    public async Task<IActionResult> Substitutes(
        Guid productId,
        [FromQuery] SubstitutesRequest request,
        CancellationToken cancellationToken)
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized(new { message = "User not authenticated." });
        }

        var validation = await _substitutesValidator.ValidateAsync(request, cancellationToken);
        if (!validation.IsValid)
        {
            return BadRequest(new { errors = validation.Errors.Select(e => e.ErrorMessage) });
        }

        var result = await _substitutesService.GetSubstitutesAsync(
            productId,
            request,
            _currentUserService.UserId.Value,
            _currentUserService.Role ?? "Operator",
            _currentUserService.IsAdmin,
            cancellationToken);

        return Map(result.Outcome) ?? Ok(result.Response);
    }

    /// <summary>The refusals both routes share, or null when the request was served.</summary>
    private IActionResult? Map(SalesCardAccessOutcome outcome) => outcome switch
    {
        // Assigned elsewhere. Administrators are granted the exception inside the service,
        // explicitly and only for active points of sale.
        SalesCardAccessOutcome.PointOfSaleForbidden => Forbid(),

        // Unknown or inactive point of sale: nobody, whatever their role, uses a closed shop.
        SalesCardAccessOutcome.PointOfSaleUnavailable => BadRequest(new
        {
            errors = new[] { "El punto de venta no existe o no está activo." }
        }),

        // The same for every role: the request is scoped to one shop, and an inventory assignment
        // is what makes a product belong to it.
        SalesCardAccessOutcome.ProductNotFound => NotFound(new
        {
            errors = new[] { "La pieza no está asignada a este punto de venta." }
        }),

        _ => null
    };
}
