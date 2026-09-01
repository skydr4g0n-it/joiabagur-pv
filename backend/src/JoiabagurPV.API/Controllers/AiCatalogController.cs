using FluentValidation;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JoiabagurPV.API.Controllers;

/// <summary>
/// Catalog enrichment. Exposes exactly one operation: proposing AI profiles for a batch of
/// products and persisting the result with its review status.
/// </summary>
/// <remarks>
/// <para>
/// There is deliberately no read route — no profile retrieval, no review queue, no metrics.
/// Reading and approving profiles belong to the review capability, and the indexing feed to its
/// own. A write-only surface that grows a route "just for a counter" is how it ends up with
/// three.
/// </para>
/// <para>
/// Administrator only. Enrichment rewrites what the catalog claims about a piece, and it spends
/// money on a model provider; neither is an operator's call.
/// </para>
/// </remarks>
[ApiController]
[Route("api/ai/catalog")]
[Authorize(Roles = "Administrator")]
public class AiCatalogController : ControllerBase
{
    private readonly IProductAiProfileService _profileService;
    private readonly IFamilySuggestionService _familySuggestionService;
    private readonly IFamilyAuditService _familyAuditService;
    private readonly ICurrentUserService _currentUserService;
    private readonly IValidator<EnrichBatchRequest> _validator;
    private readonly IValidator<ApplyFamilySuggestionsRequest> _applyValidator;
    private readonly IValidator<RecordFamilyVerdictsRequest> _verdictsValidator;
    private readonly ILogger<AiCatalogController> _logger;

    public AiCatalogController(
        IProductAiProfileService profileService,
        IFamilySuggestionService familySuggestionService,
        IFamilyAuditService familyAuditService,
        ICurrentUserService currentUserService,
        IValidator<EnrichBatchRequest> validator,
        IValidator<ApplyFamilySuggestionsRequest> applyValidator,
        IValidator<RecordFamilyVerdictsRequest> verdictsValidator,
        ILogger<AiCatalogController> logger)
    {
        _profileService = profileService;
        _familySuggestionService = familySuggestionService;
        _familyAuditService = familyAuditService;
        _currentUserService = currentUserService;
        _validator = validator;
        _applyValidator = applyValidator;
        _verdictsValidator = verdictsValidator;
        _logger = logger;
    }

    /// <summary>
    /// Enriches a batch of products and stores their AI profiles.
    /// </summary>
    /// <param name="request">Products, review mode and whether to ignore the input hash.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Counters and the per-product outcome.</returns>
    [HttpPost("enrich-batch")]
    [ProducesResponseType(typeof(EnrichBatchResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status503ServiceUnavailable)]
    public async Task<IActionResult> EnrichBatch(
        [FromBody] EnrichBatchRequest? request,
        CancellationToken cancellationToken)
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized(new { message = "User not authenticated." });
        }

        // SuppressModelStateInvalidFilter is on: a body that does not bind still
        // reaches the action as null, and FluentValidation then throws ArgumentNullException.
        if (request is null)
        {
            return BadRequest(new { errors = new[] { "A batch body is required." } });
        }

        // Validated explicitly: this project registers validators but wires no automatic
        // pipeline, so an uninvoked validator is worse than none — it looks like validation.
        var validationResult = await _validator.ValidateAsync(request, cancellationToken);
        if (!validationResult.IsValid)
        {
            return BadRequest(new { errors = validationResult.Errors.Select(e => e.ErrorMessage) });
        }

        try
        {
            var response = await _profileService.EnrichBatchAsync(
                request,
                _currentUserService.UserId.Value,
                _currentUserService.Role ?? "Administrator",
                cancellationToken);

            return Ok(response);
        }
        catch (AiNotImplementedException exception)
        {
            // 503 rather than a degraded answer. There is no fallback for enrichment: unlike
            // search, which can drop to the lexical index, producing attributes without the
            // extractor would mean inventing catalog data.
            _logger.LogWarning(exception, "enrich_batch_not_implemented");

            return StatusCode(
                StatusCodes.Status503ServiceUnavailable,
                new
                {
                    message = "Catalog enrichment is not available yet: the AI service has no "
                        + "implementation for it. It is delivered by C09 "
                        + "(add-catalog-enrichment-pipeline)."
                });
        }
        catch (AiUnavailableException exception)
        {
            _logger.LogWarning(exception, "enrich_batch_ai_unavailable");

            return StatusCode(
                StatusCodes.Status503ServiceUnavailable,
                new { message = "The AI service is unavailable. No profile was created or modified." });
        }
    }

    /// <summary>
    /// Asks jbg-ai to propose product families. Writes nothing.
    /// </summary>
    /// <param name="request">Optional narrowing by piece type.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Proposals, refused groups and excluded products.</returns>
    [HttpPost("family-suggestions")]
    [ProducesResponseType(typeof(AiFamilySuggestResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status503ServiceUnavailable)]
    public async Task<IActionResult> SuggestFamilies(
        [FromBody] FamilySuggestionsRequest? request,
        CancellationToken cancellationToken)
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized(new { message = "User not authenticated." });
        }

        try
        {
            var response = await _familySuggestionService.SuggestAsync(
                request ?? new FamilySuggestionsRequest(),
                _currentUserService.UserId.Value,
                _currentUserService.Role ?? "Administrator",
                cancellationToken);

            return Ok(response);
        }
        catch (AiNotImplementedException exception)
        {
            _logger.LogWarning(exception, "family_suggestions_not_implemented");

            return StatusCode(
                StatusCodes.Status503ServiceUnavailable,
                new
                {
                    message = "Family suggestion is not available yet: the AI service has no "
                        + "implementation for it."
                });
        }
        catch (AiUnavailableException exception)
        {
            // 503 and no degraded answer. Unlike search, which drops to the lexical index,
            // proposing groupings without the vector index would mean inventing catalog structure.
            _logger.LogWarning(exception, "family_suggestions_ai_unavailable");

            return StatusCode(
                StatusCodes.Status503ServiceUnavailable,
                new { message = "The AI service is unavailable. No family was proposed." });
        }
    }

    /// <summary>
    /// Creates the families an administrator accepted from a suggestion.
    /// </summary>
    /// <param name="request">The accepted subset, returned by the caller.</param>
    /// <returns>Counts of what was created, and the families a conflict skipped.</returns>
    /// <remarks>
    /// The only write path of the assisted flow, and it goes through the family service because
    /// that service is the one thing that keeps the incremental catalog feed's watermark
    /// coherent — here through the new family's own <c>UpdatedAt</c>, which the feed joins on for
    /// current members, and on a later replace through the stamp it puts on entering and leaving
    /// products. It does not reach jbg-ai at all: the proposal already travelled.
    /// </remarks>
    [HttpPost("family-suggestions/apply")]
    [ProducesResponseType(typeof(ApplyFamilySuggestionsResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    public async Task<IActionResult> ApplyFamilySuggestions(
        [FromBody] ApplyFamilySuggestionsRequest? request)
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized(new { message = "User not authenticated." });
        }

        if (request is null)
        {
            return BadRequest(new { errors = new[] { "A batch body is required." } });
        }

        // Validated explicitly: this project registers validators but wires no automatic
        // pipeline, so an uninvoked validator is worse than none — it looks like validation.
        var validationResult = await _applyValidator.ValidateAsync(request);
        if (!validationResult.IsValid)
        {
            return BadRequest(new { errors = validationResult.Errors.Select(e => e.ErrorMessage) });
        }

        var response = await _familySuggestionService.ApplyAsync(
            request, _currentUserService.UserId.Value);

        return Ok(response);
    }

    /// <summary>
    /// Audits the families that exist, and nominates the products that look like their members.
    /// </summary>
    /// <param name="request">Optional narrowing, thresholds and candidate cap.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Flagged memberships, orphan candidates, and what the run still refuses.</returns>
    /// <remarks>
    /// <para>
    /// Reads and writes nothing. Recording a judgement is <c>family-verdicts</c>, and keeping the
    /// two apart is what lets a test assert that auditing changed nothing at all.
    /// </para>
    /// <para>
    /// The pairs a person already ruled on are read from this side and sent along, because the AI
    /// service holds no verdict: a store of judgements beside the index would be state nothing
    /// invalidates.
    /// </para>
    /// </remarks>
    [HttpPost("family-audit")]
    [ProducesResponseType(typeof(AiFamilyAuditResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status503ServiceUnavailable)]
    public async Task<IActionResult> AuditFamilies(
        [FromBody] FamilyAuditQueryRequest? request,
        CancellationToken cancellationToken)
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized(new { message = "User not authenticated." });
        }

        try
        {
            var response = await _familyAuditService.AuditAsync(
                request ?? new FamilyAuditQueryRequest(),
                _currentUserService.UserId.Value,
                _currentUserService.Role ?? "Administrator",
                cancellationToken);

            return Ok(response);
        }
        catch (AiNotImplementedException exception)
        {
            _logger.LogWarning(exception, "family_audit_not_implemented");

            return StatusCode(
                StatusCodes.Status503ServiceUnavailable,
                new
                {
                    message = "Family audit is not available yet: the AI service has no "
                        + "implementation for it."
                });
        }
        catch (AiUnavailableException exception)
        {
            // 503 and never an empty result. This feeds a catalog-quality screen, where an empty
            // answer reads as 'the catalog is clean' — asserting by accident the very conclusion
            // the review exists to establish with evidence.
            _logger.LogWarning(exception, "family_audit_ai_unavailable");

            return StatusCode(
                StatusCodes.Status503ServiceUnavailable,
                new { message = "The AI service is unavailable. No audit was produced." });
        }
    }

    /// <summary>
    /// Lists the recorded judgements, each with the membership change it still implies.
    /// </summary>
    /// <returns>Every verdict, ordered so the widest margins come first.</returns>
    /// <remarks>
    /// Exists because a decision nobody acted on is otherwise invisible. The audit omits judged
    /// pairs on purpose -- that is what makes a dismissal stick -- so a rejected member that
    /// was never removed stops appearing anywhere and reads as work already finished.
    /// </remarks>
    /// <summary>
    /// The human-review figures the delivery checklist asks for.
    /// </summary>
    /// <returns>Correction rates per population, average review time, and what is still pending.</returns>
    /// <remarks>
    /// Computed from the stored judgements rather than tallied in a screen: an average that lives
    /// in component state is gone when the tab closes.
    /// </remarks>
    [HttpGet("family-review-metrics")]
    [ProducesResponseType(typeof(FamilyReviewMetricsDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    public async Task<IActionResult> GetFamilyReviewMetrics() =>
        Ok(await _familyAuditService.GetMetricsAsync());

    [HttpGet("family-verdicts")]
    [ProducesResponseType(typeof(List<FamilyVerdictDto>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    public async Task<IActionResult> ListFamilyVerdicts() =>
        Ok(await _familyAuditService.ListVerdictsAsync());

    /// <summary>
    /// Records what an administrator decided about a batch of product and family pairs.
    /// </summary>
    /// <param name="request">The judgements.</param>
    /// <returns>How many were recorded for the first time, and how many corrected an earlier one.</returns>
    /// <remarks>
    /// Idempotent per pair. Judging the same pair again replaces the standing record rather than
    /// adding a second contradictory one, which is the invariant the unique index also enforces.
    /// </remarks>
    [HttpPost("family-verdicts")]
    [ProducesResponseType(typeof(RecordFamilyVerdictsResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    public async Task<IActionResult> RecordFamilyVerdicts(
        [FromBody] RecordFamilyVerdictsRequest? request)
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized(new { message = "User not authenticated." });
        }

        if (request is null)
        {
            return BadRequest(new { errors = new[] { "A verdict body is required." } });
        }

        // Validated explicitly: this project registers validators but wires no automatic
        // pipeline, so an uninvoked validator is worse than none — it looks like validation.
        var validationResult = await _verdictsValidator.ValidateAsync(request);
        if (!validationResult.IsValid)
        {
            return BadRequest(new { errors = validationResult.Errors.Select(e => e.ErrorMessage) });
        }

        try
        {
            var response = await _familyAuditService.RecordVerdictsAsync(
                request, _currentUserService.UserId.Value);

            return Ok(response);
        }
        catch (ArgumentException exception)
        {
            return BadRequest(new { errors = new[] { exception.Message } });
        }
    }
}
