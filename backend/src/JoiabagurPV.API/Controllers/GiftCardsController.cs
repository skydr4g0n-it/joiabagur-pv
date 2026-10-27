using FluentValidation;
using JoiabagurPV.API.Infrastructure;
using JoiabagurPV.Application.DTOs.GiftCards;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JoiabagurPV.API.Controllers;

[ApiController]
[Route("api/gift-cards")]
[Authorize]
public class GiftCardsController : ControllerBase
{
    private readonly IGiftCardService _giftCardService;
    private readonly ICurrentUserService _currentUserService;
    private readonly IQrCodeService _qrCodeService;
    private readonly IValidator<IssueGiftCardRequest> _issueValidator;
    private readonly IValidator<ReassignGiftCardRequest> _reassignValidator;
    private readonly IValidator<ExchangeGiftCardRequest> _exchangeValidator;

    public GiftCardsController(
        IGiftCardService giftCardService,
        ICurrentUserService currentUserService,
        IQrCodeService qrCodeService,
        IValidator<IssueGiftCardRequest> issueValidator,
        IValidator<ReassignGiftCardRequest> reassignValidator,
        IValidator<ExchangeGiftCardRequest> exchangeValidator)
    {
        _giftCardService = giftCardService;
        _currentUserService = currentUserService;
        _qrCodeService = qrCodeService;
        _issueValidator = issueValidator;
        _reassignValidator = reassignValidator;
        _exchangeValidator = exchangeValidator;
    }

    [HttpPost]
    [ProducesResponseType(typeof(IssueGiftCardResult), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    public async Task<ActionResult<IssueGiftCardResult>> Issue(
        [FromBody] IssueGiftCardRequest request,
        [FromHeader(Name = "Idempotency-Key")] string? idempotencyKey)
    {
        var validation = await _issueValidator.ValidateAsync(request);
        if (!validation.IsValid)
            return BadRequest(new { errors = validation.Errors.Select(e => e.ErrorMessage) });

        if (!_currentUserService.UserId.HasValue)
            return Unauthorized();

        if (!string.IsNullOrWhiteSpace(idempotencyKey))
        {
            var (exists, previous) = IdempotencyStore.TryGet(idempotencyKey);
            if (exists && previous is IssueGiftCardResult cachedIssue)
                return StatusCode(StatusCodes.Status201Created, cachedIssue);
            IdempotencyStore.Reserve(idempotencyKey);
        }

        var result = await _giftCardService.IssueAsync(request, _currentUserService.UserId.Value, _currentUserService.IsAdmin, idempotencyKey);
        if (result.IsForbidden)
        {
            if (!string.IsNullOrWhiteSpace(idempotencyKey))
                IdempotencyStore.Remove(idempotencyKey);
            return Forbid();
        }

        if (!result.Success)
        {
            if (!string.IsNullOrWhiteSpace(idempotencyKey))
                IdempotencyStore.Remove(idempotencyKey);
            return BadRequest(new { message = result.ErrorMessage });
        }

        if (!string.IsNullOrWhiteSpace(idempotencyKey))
            IdempotencyStore.Store(idempotencyKey, result);

        return CreatedAtAction(nameof(GetById), new { id = result.Card!.Id }, result);
    }

    [HttpGet]
    [ProducesResponseType(typeof(GiftCardListResponse), StatusCodes.Status200OK)]
    public async Task<ActionResult<GiftCardListResponse>> List([FromQuery] int page = 1, [FromQuery] int pageSize = 50)
    {
        if (!_currentUserService.UserId.HasValue)
            return Unauthorized();

        var result = await _giftCardService.ListAsync(page, pageSize, _currentUserService.UserId.Value, _currentUserService.IsAdmin);
        return Ok(result);
    }

    [HttpGet("{id:guid}/qrcode")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetQrCode(Guid id)
    {
        if (!_currentUserService.UserId.HasValue)
            return Unauthorized();

        var card = await _giftCardService.GetDetailAsync(id, _currentUserService.UserId.Value, _currentUserService.IsAdmin);
        if (card == null)
            return NotFound();

        var svg = _qrCodeService.GenerateSvg(card.Code, card.Code);
        return Content(svg, "image/svg+xml");
    }

    [HttpGet("{id:guid}")]
    [ProducesResponseType(typeof(GiftCardDetailDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<GiftCardDetailDto>> GetById(Guid id)
    {
        if (!_currentUserService.UserId.HasValue)
            return Unauthorized();

        var card = await _giftCardService.GetDetailAsync(id, _currentUserService.UserId.Value, _currentUserService.IsAdmin);
        if (card == null)
            return NotFound();

        return Ok(card);
    }

    [HttpGet("by-code/{code}")]
    [ProducesResponseType(typeof(GiftCardByCodeDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<GiftCardByCodeDto>> GetByCode(string code, [FromQuery] Guid pointOfSaleId)
    {
        if (pointOfSaleId == Guid.Empty)
            return BadRequest(new { message = "El punto de venta es obligatorio." });

        var (card, error) = await _giftCardService.GetByCodeForPosAsync(code, pointOfSaleId);
        if (card == null && error == "Gift card not found.")
            return NotFound(new { message = error });

        if (card == null)
            return BadRequest(new { message = error });

        return Ok(card);
    }

    [HttpPost("{id:guid}/reassign")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(ReassignGiftCardResult), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    public async Task<ActionResult<ReassignGiftCardResult>> Reassign(Guid id, [FromBody] ReassignGiftCardRequest request)
    {
        var validation = await _reassignValidator.ValidateAsync(request);
        if (!validation.IsValid)
            return BadRequest(new { errors = validation.Errors.Select(e => e.ErrorMessage) });

        if (!_currentUserService.UserId.HasValue)
            return Unauthorized();

        var result = await _giftCardService.ReassignAsync(id, request, _currentUserService.UserId.Value, _currentUserService.IsAdmin);
        if (result.IsForbidden)
            return Forbid();
        if (!result.Success)
            return BadRequest(new { message = result.ErrorMessage });

        return Ok(result);
    }

    [HttpPost("{id:guid}/exchanges")]
    [ProducesResponseType(typeof(ExchangeGiftCardResult), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<ActionResult<ExchangeGiftCardResult>> Exchange(
        Guid id,
        [FromBody] ExchangeGiftCardRequest request,
        [FromHeader(Name = "Idempotency-Key")] string? idempotencyKey)
    {
        var validation = await _exchangeValidator.ValidateAsync(request);
        if (!validation.IsValid)
            return BadRequest(new { errors = validation.Errors.Select(e => e.ErrorMessage) });

        if (!_currentUserService.UserId.HasValue)
            return Unauthorized();

        var storeKey = string.IsNullOrWhiteSpace(idempotencyKey) ? null : $"gift-card-exchange:{idempotencyKey}";
        if (storeKey != null)
        {
            var (exists, previous) = IdempotencyStore.TryGet(storeKey);
            if (exists && previous is ExchangeGiftCardResult cachedExchange)
                return StatusCode(StatusCodes.Status201Created, cachedExchange);
            IdempotencyStore.Reserve(storeKey);
        }

        var result = await _giftCardService.ExchangeAsync(
            id, request, _currentUserService.UserId.Value, _currentUserService.IsAdmin, idempotencyKey);

        if (!result.Success)
        {
            if (storeKey != null)
                IdempotencyStore.Remove(storeKey);
            return BadRequest(new { message = result.ErrorMessage });
        }

        if (storeKey != null)
            IdempotencyStore.Store(storeKey, result);

        return StatusCode(StatusCodes.Status201Created, result);
    }
}
