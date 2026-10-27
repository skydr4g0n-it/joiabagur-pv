using FluentValidation;
using JoiabagurPV.API.Infrastructure;
using JoiabagurPV.Application.DTOs.Sales;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JoiabagurPV.API.Controllers;

/// <summary>
/// Controller for sales management operations.
/// </summary>
[ApiController]
[Route("api/[controller]")]
[Authorize]
public class SalesController : ControllerBase
{
    private readonly ISalesService _salesService;
    private readonly IImageCompressionService _imageCompressionService;
    private readonly ICurrentUserService _currentUserService;
    private readonly IValidator<CreateSaleRequest> _createValidator;
    private readonly IValidator<CreateBulkSalesRequest> _createBulkValidator;
    private readonly ILogger<SalesController> _logger;

    public SalesController(
        ISalesService salesService,
        IImageCompressionService imageCompressionService,
        ICurrentUserService currentUserService,
        IValidator<CreateSaleRequest> createValidator,
        IValidator<CreateBulkSalesRequest> createBulkValidator,
        ILogger<SalesController> logger)
    {
        _salesService = salesService;
        _imageCompressionService = imageCompressionService;
        _currentUserService = currentUserService;
        _createValidator = createValidator;
        _createBulkValidator = createBulkValidator;
        _logger = logger;
    }

    /// <summary>
    /// Creates a new sale with optional photo attachment.
    /// Validates stock, payment method, and operator access.
    /// </summary>
    /// <param name="request">Sale creation request.</param>
    /// <returns>Created sale with warnings if applicable.</returns>
    [HttpPost]
    [ProducesResponseType(typeof(CreateSaleResult), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<ActionResult<CreateSaleResult>> CreateSale([FromBody] CreateSaleRequest request)
    {
        // Validate request
        var validationResult = await _createValidator.ValidateAsync(request);
        if (!validationResult.IsValid)
        {
            return BadRequest(new { errors = validationResult.Errors.Select(e => e.ErrorMessage) });
        }

        // Get current user
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized(new { message = "Usuario no autenticado." });
        }

        var userId = _currentUserService.UserId.Value;

        // Compress photo if provided
        if (!string.IsNullOrEmpty(request.PhotoBase64))
        {
            try
            {
                var photoBytes = Convert.FromBase64String(request.PhotoBase64);
                
                // Validate image
                var (isValid, errorMessage) = await _imageCompressionService.ValidateImageAsync(photoBytes);
                if (!isValid)
                {
                    return BadRequest(new { message = errorMessage });
                }

                // Compress image
                var compressedBytes = await _imageCompressionService.CompressImageAsync(photoBytes);
                request.PhotoBase64 = Convert.ToBase64String(compressedBytes);
            }
            catch (ArgumentException ex)
            {
                return BadRequest(new { message = ex.Message });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to process sale photo");
                return BadRequest(new { message = "No se pudo procesar la foto. Inténtalo de nuevo." });
            }
        }

        // Create sale (admins can sell from any POS)
        var result = await _salesService.CreateSaleAsync(request, userId, _currentUserService.IsAdmin);

        if (!result.Success)
        {
            return BadRequest(new { message = result.ErrorMessage });
        }

        // Return with warnings if applicable
        var response = new
        {
            sale = result.Sale,
            warning = result.WarningMessage,
            isLowStock = result.IsLowStock,
            remainingStock = result.RemainingStock
        };

        return CreatedAtAction(nameof(GetSaleById), new { id = result.Sale!.Id }, response);
    }

    /// <summary>
    /// Creates multiple sales atomically in a single transaction.
    /// Supports an optional Idempotency-Key header to prevent duplicate submissions.
    /// </summary>
    [HttpPost("bulk")]
    [ProducesResponseType(typeof(CreateBulkSalesResult), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<ActionResult<CreateBulkSalesResult>> CreateBulkSales(
        [FromBody] CreateBulkSalesRequest request,
        [FromHeader(Name = "Idempotency-Key")] string? idempotencyKey)
    {
        var validationResult = await _createBulkValidator.ValidateAsync(request);
        if (!validationResult.IsValid)
        {
            return BadRequest(new { errors = validationResult.Errors.Select(e => e.ErrorMessage) });
        }

        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized(new { message = "Usuario no autenticado." });
        }

        if (!string.IsNullOrWhiteSpace(idempotencyKey))
        {
            var (exists, previousResult) = IdempotencyStore.TryGet(idempotencyKey);
            if (exists)
            {
                if (previousResult != null)
                {
                    return Ok(previousResult);
                }
                return Conflict(new { message = "Ya se está procesando una petición con esta clave de idempotencia." });
            }
            IdempotencyStore.Reserve(idempotencyKey);
        }

        foreach (var line in request.Lines)
        {
            if (!string.IsNullOrEmpty(line.PhotoBase64))
            {
                try
                {
                    var photoBytes = Convert.FromBase64String(line.PhotoBase64);
                    var (isValid, errorMessage) = await _imageCompressionService.ValidateImageAsync(photoBytes);
                    if (!isValid)
                    {
                        if (!string.IsNullOrWhiteSpace(idempotencyKey))
                            IdempotencyStore.Remove(idempotencyKey);
                        return BadRequest(new { message = errorMessage });
                    }
                    var compressedBytes = await _imageCompressionService.CompressImageAsync(photoBytes);
                    line.PhotoBase64 = Convert.ToBase64String(compressedBytes);
                }
                catch (ArgumentException ex)
                {
                    if (!string.IsNullOrWhiteSpace(idempotencyKey))
                        IdempotencyStore.Remove(idempotencyKey);
                    return BadRequest(new { message = ex.Message });
                }
                catch (Exception ex)
                {
                    if (!string.IsNullOrWhiteSpace(idempotencyKey))
                        IdempotencyStore.Remove(idempotencyKey);
                    _logger.LogError(ex, "Failed to process bulk sale photo");
                    return BadRequest(new { message = "No se pudo procesar la foto. Inténtalo de nuevo." });
                }
            }
        }

        var userId = _currentUserService.UserId.Value;
        var result = await _salesService.CreateBulkSalesAsync(request, userId, _currentUserService.IsAdmin);

        if (!result.Success)
        {
            if (!string.IsNullOrWhiteSpace(idempotencyKey))
            {
                IdempotencyStore.Remove(idempotencyKey);
            }
            return BadRequest(new { message = result.ErrorMessage });
        }

        if (!string.IsNullOrWhiteSpace(idempotencyKey))
        {
            IdempotencyStore.Store(idempotencyKey, result);
        }

        return CreatedAtAction(nameof(GetSaleById), new { id = result.Sales.FirstOrDefault()?.Id }, result);
    }

    /// <summary>
    /// Gets a sale by ID.
    /// Admins can view all sales, operators can only view sales from their assigned points of sale.
    /// </summary>
    /// <param name="id">Sale ID.</param>
    /// <returns>Sale details if found and authorized.</returns>
    [HttpGet("{id}")]
    [ProducesResponseType(typeof(SaleDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    public async Task<ActionResult<SaleDto>> GetSaleById(Guid id)
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized();
        }

        var sale = await _salesService.GetSaleByIdAsync(
            id,
            _currentUserService.UserId.Value,
            _currentUserService.IsAdmin);

        if (sale == null)
        {
            return NotFound(new { message = "Venta no encontrada o acceso denegado." });
        }

        return Ok(sale);
    }

    /// <summary>
    /// Gets sales history with filtering and pagination.
    /// Admins see all sales, operators see only sales from their assigned points of sale.
    /// </summary>
    /// <param name="startDate">Optional start date filter.</param>
    /// <param name="endDate">Optional end date filter.</param>
    /// <param name="pointOfSaleId">Optional point of sale filter.</param>
    /// <param name="productId">Optional product filter.</param>
    /// <param name="userId">Optional user filter.</param>
    /// <param name="paymentMethodId">Optional payment method filter.</param>
    /// <param name="page">Page number (1-based).</param>
    /// <param name="pageSize">Page size (max 50).</param>
    /// <returns>Paginated sales history.</returns>
    [HttpGet]
    [ProducesResponseType(typeof(SalesHistoryResponse), StatusCodes.Status200OK)]
    public async Task<ActionResult<SalesHistoryResponse>> GetSalesHistory(
        [FromQuery] DateTime? startDate,
        [FromQuery] DateTime? endDate,
        [FromQuery] Guid? pointOfSaleId,
        [FromQuery] Guid? productId,
        [FromQuery] Guid? userId,
        [FromQuery] Guid? paymentMethodId,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20)
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized();
        }

        // Convert dates to UTC to avoid PostgreSQL "Kind=Unspecified" error
        DateTime? startDateUtc = startDate.HasValue 
            ? DateTime.SpecifyKind(startDate.Value, DateTimeKind.Utc) 
            : null;
        DateTime? endDateUtc = endDate.HasValue 
            ? DateTime.SpecifyKind(endDate.Value.Date.AddDays(1).AddTicks(-1), DateTimeKind.Utc) 
            : null;

        var request = new SalesHistoryFilterRequest
        {
            StartDate = startDateUtc,
            EndDate = endDateUtc,
            PointOfSaleId = pointOfSaleId,
            ProductId = productId,
            UserId = userId,
            PaymentMethodId = paymentMethodId,
            Page = page,
            PageSize = pageSize
        };

        var result = await _salesService.GetSalesHistoryAsync(
            request,
            _currentUserService.UserId.Value,
            _currentUserService.IsAdmin);

        return Ok(result);
    }

    /// <summary>
    /// Gets the photo file for a sale.
    /// </summary>
    /// <param name="id">Sale ID.</param>
    /// <returns>Photo file if exists.</returns>
    [HttpGet("{id}/photo/file")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetSalePhoto(Guid id)
    {
        // Verify user has access to this sale
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized();
        }

        var sale = await _salesService.GetSaleByIdAsync(
            id,
            _currentUserService.UserId.Value,
            _currentUserService.IsAdmin);

        if (sale == null)
        {
            return NotFound(new { message = "Venta no encontrada o acceso denegado." });
        }

        if (!sale.HasPhoto)
        {
            return NotFound(new { message = "Esta venta no tiene foto adjunta." });
        }

        var photoResult = await _salesService.GetSalePhotoStreamAsync(id);
        if (photoResult == null)
        {
            _logger.LogWarning("Photo file not found for sale {SaleId}", id);
            return NotFound(new { message = "Archivo de foto no encontrado." });
        }

        // Set caching headers
        Response.Headers.Append("Cache-Control", "private, max-age=86400"); // Cache for 24 hours
        Response.Headers.Append("Content-Disposition", $"inline; filename=\"{photoResult.Value.FileName}\"");

        return File(photoResult.Value.Stream, photoResult.Value.ContentType);
    }
}
