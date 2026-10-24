using FluentValidation;
using JoiabagurPV.Application.DTOs.PaymentMethods;
using JoiabagurPV.Application.DTOs.PointOfSales;
using JoiabagurPV.Application.DTOs.Users;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Exceptions;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JoiabagurPV.API.Controllers;

/// <summary>
/// Controller for point of sale management operations.
/// </summary>
[ApiController]
[Route("api/point-of-sales")]
[Authorize]
public class PointOfSalesController : ControllerBase
{
    private readonly IPointOfSaleService _pointOfSaleService;
    private readonly IUserPointOfSaleService _userPointOfSaleService;
    private readonly IPaymentMethodService _paymentMethodService;
    private readonly IPointOfSaleCommissionTierService _commissionTierService;
    private readonly ICurrentUserService _currentUserService;
    private readonly IValidator<CreatePointOfSaleRequest> _createValidator;
    private readonly IValidator<UpdatePointOfSaleRequest> _updateValidator;
    private readonly IValidator<ReplaceCommissionTiersRequest> _commissionTiersValidator;
    private readonly ILogger<PointOfSalesController> _logger;

    public PointOfSalesController(
        IPointOfSaleService pointOfSaleService,
        IUserPointOfSaleService userPointOfSaleService,
        IPaymentMethodService paymentMethodService,
        IPointOfSaleCommissionTierService commissionTierService,
        ICurrentUserService currentUserService,
        IValidator<CreatePointOfSaleRequest> createValidator,
        IValidator<UpdatePointOfSaleRequest> updateValidator,
        IValidator<ReplaceCommissionTiersRequest> commissionTiersValidator,
        ILogger<PointOfSalesController> logger)
    {
        _pointOfSaleService = pointOfSaleService;
        _userPointOfSaleService = userPointOfSaleService;
        _paymentMethodService = paymentMethodService;
        _commissionTierService = commissionTierService;
        _currentUserService = currentUserService;
        _createValidator = createValidator;
        _updateValidator = updateValidator;
        _commissionTiersValidator = commissionTiersValidator;
        _logger = logger;
    }

    /// <summary>
    /// Gets all points of sale. Administrators see all (active and inactive), operators see only assigned.
    /// </summary>
    /// <returns>List of points of sale.</returns>
    [HttpGet]
    [ProducesResponseType(typeof(List<PointOfSaleDto>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    public async Task<IActionResult> GetAll()
    {
        _logger.LogInformation("GetAll called. IsAdmin: {IsAdmin}", _currentUserService.IsAdmin);

        if (_currentUserService.IsAdmin)
        {
            // Administrators always see all points of sale (active and inactive)
            var pointOfSales = await _pointOfSaleService.GetAllAsync(includeInactive: true);
            _logger.LogInformation("Admin user getting {Count} POS (all, including inactive)", pointOfSales.Count);
            return Ok(pointOfSales);
        }
        else
        {
            // Operators only see their assigned points of sale
            var userId = _currentUserService.UserId;
            if (!userId.HasValue)
            {
                return Unauthorized(new { error = "Usuario no autenticado" });
            }

            var pointOfSales = await _pointOfSaleService.GetByUserAsync(userId.Value);
            _logger.LogInformation("Operator user {UserId} getting {Count} assigned POS", userId.Value, pointOfSales.Count);
            return Ok(pointOfSales);
        }
    }

    /// <summary>
    /// Gets a point of sale by ID.
    /// </summary>
    /// <param name="id">The point of sale ID.</param>
    /// <returns>The point of sale details.</returns>
    [HttpGet("{id:guid}")]
    [ProducesResponseType(typeof(PointOfSaleDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetById(Guid id)
    {
        // Check access for non-admin users
        if (!_currentUserService.IsAdmin)
        {
            var userId = _currentUserService.UserId;
            if (!userId.HasValue)
            {
                return Unauthorized(new { error = "Usuario no autenticado" });
            }

            var hasAccess = await _pointOfSaleService.UserHasAccessAsync(userId.Value, id);
            if (!hasAccess)
            {
                return Forbid();
            }
        }

        var pointOfSale = await _pointOfSaleService.GetByIdAsync(id);

        if (pointOfSale == null)
        {
            return NotFound(new { error = "Punto de venta no encontrado" });
        }

        return Ok(pointOfSale);
    }

    /// <summary>
    /// Creates a new point of sale. Administrator only.
    /// </summary>
    /// <param name="request">The point of sale creation request.</param>
    /// <returns>The created point of sale.</returns>
    [HttpPost]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(PointOfSaleDto), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> Create([FromBody] CreatePointOfSaleRequest request)
    {
        var validationResult = await _createValidator.ValidateAsync(request);
        if (!validationResult.IsValid)
        {
            return BadRequest(new { errors = validationResult.Errors.Select(e => e.ErrorMessage) });
        }

        try
        {
            var pointOfSale = await _pointOfSaleService.CreateAsync(request);
            return CreatedAtAction(nameof(GetById), new { id = pointOfSale.Id }, pointOfSale);
        }
        catch (DomainException ex) when (ex.Message.Contains("en uso"))
        {
            return Conflict(new { error = ex.Message });
        }
        catch (DomainException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Updates an existing point of sale. Administrator only.
    /// </summary>
    /// <param name="id">The point of sale ID to update.</param>
    /// <param name="request">The update request.</param>
    /// <returns>The updated point of sale.</returns>
    [HttpPut("{id:guid}")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(PointOfSaleDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> Update(Guid id, [FromBody] UpdatePointOfSaleRequest request)
    {
        var validationResult = await _updateValidator.ValidateAsync(request);
        if (!validationResult.IsValid)
        {
            return BadRequest(new { errors = validationResult.Errors.Select(e => e.ErrorMessage) });
        }

        try
        {
            var pointOfSale = await _pointOfSaleService.UpdateAsync(id, request);
            return Ok(pointOfSale);
        }
        catch (DomainException ex) when (ex.Message.Contains("no encontrado"))
        {
            return NotFound(new { error = ex.Message });
        }
        catch (DomainException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Changes the status (activate/deactivate) of a point of sale. Administrator only.
    /// </summary>
    /// <param name="id">The point of sale ID.</param>
    /// <param name="request">The status change request.</param>
    /// <returns>The updated point of sale.</returns>
    [HttpPatch("{id:guid}/status")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(PointOfSaleDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> ChangeStatus(Guid id, [FromBody] ChangeStatusRequest request)
    {
        try
        {
            var pointOfSale = await _pointOfSaleService.ChangeStatusAsync(id, request.IsActive);
            return Ok(pointOfSale);
        }
        catch (DomainException ex) when (ex.Message.Contains("no encontrado"))
        {
            return NotFound(new
            {
                error = new
                {
                    message = ex.Message,
                    type = ex.GetType().Name,
                    statusCode = 404
                },
                timestamp = DateTime.UtcNow
            });
        }
        catch (DomainException ex)
        {
            _logger.LogWarning(ex, "Domain exception caught by controller: {Message}", ex.Message);
            return BadRequest(new
            {
                error = new
                {
                    message = ex.Message,
                    type = ex.GetType().Name,
                    statusCode = 400
                },
                timestamp = DateTime.UtcNow
            });
        }
    }

    #region Operator Assignments

    /// <summary>
    /// Gets operators assigned to a point of sale.
    /// </summary>
    /// <param name="id">The point of sale ID.</param>
    /// <returns>List of operator assignments.</returns>
    [HttpGet("{id:guid}/operators")]
    [ProducesResponseType(typeof(List<UserPointOfSaleDto>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetOperators(Guid id)
    {
        // Verify point of sale exists
        var pointOfSale = await _pointOfSaleService.GetByIdAsync(id);
        if (pointOfSale == null)
        {
            return NotFound(new { error = "Punto de venta no encontrado" });
        }

        var operators = await _userPointOfSaleService.GetByPointOfSaleAsync(id);
        return Ok(operators);
    }

    /// <summary>
    /// Assigns an operator to a point of sale. Administrator only.
    /// </summary>
    /// <param name="id">The point of sale ID.</param>
    /// <param name="userId">The user ID to assign.</param>
    /// <returns>The assignment details.</returns>
    [HttpPost("{id:guid}/operators/{userId:guid}")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> AssignOperator(Guid id, Guid userId)
    {
        // Verify point of sale exists
        var pointOfSale = await _pointOfSaleService.GetByIdAsync(id);
        if (pointOfSale == null)
        {
            return NotFound(new { error = "Punto de venta no encontrado" });
        }

        try
        {
            var assignment = await _userPointOfSaleService.AssignAsync(userId, id);
            _logger.LogInformation("Operator {UserId} assigned to point of sale {PointOfSaleId}", userId, id);
            return CreatedAtAction(nameof(GetById), new { id }, assignment);
        }
        catch (DomainException ex) when (ex.Message.Contains("no encontrado"))
        {
            return NotFound(new { error = ex.Message });
        }
        catch (DomainException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Unassigns an operator from a point of sale. Administrator only.
    /// </summary>
    /// <param name="id">The point of sale ID.</param>
    /// <param name="userId">The user ID to unassign.</param>
    /// <returns>No content on success.</returns>
    [HttpDelete("{id:guid}/operators/{userId:guid}")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> UnassignOperator(Guid id, Guid userId)
    {
        // Verify point of sale exists
        var pointOfSale = await _pointOfSaleService.GetByIdAsync(id);
        if (pointOfSale == null)
        {
            return NotFound(new { error = "Punto de venta no encontrado" });
        }

        try
        {
            await _userPointOfSaleService.UnassignAsync(userId, id);
            _logger.LogInformation("Operator {UserId} unassigned from point of sale {PointOfSaleId}", userId, id);
            return NoContent();
        }
        catch (DomainException ex) when (ex.Message.Contains("no encontrado") || ex.Message.Contains("desasignado"))
        {
            return NotFound(new { error = ex.Message });
        }
        catch (DomainException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    #endregion

    #region Payment Method Assignments

    /// <summary>
    /// Gets payment methods assigned to a point of sale.
    /// </summary>
    /// <param name="id">The point of sale ID.</param>
    /// <param name="includeInactive">Whether to include inactive assignments.</param>
    /// <returns>List of payment method assignments.</returns>
    [HttpGet("{id:guid}/payment-methods")]
    [ProducesResponseType(typeof(List<PointOfSalePaymentMethodDto>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetPaymentMethods(Guid id, [FromQuery] bool includeInactive = false)
    {
        // Check access for non-admin users
        if (!_currentUserService.IsAdmin)
        {
            var userId = _currentUserService.UserId;
            if (!userId.HasValue)
            {
                return Unauthorized(new { error = "Usuario no autenticado" });
            }

            var hasAccess = await _pointOfSaleService.UserHasAccessAsync(userId.Value, id);
            if (!hasAccess)
            {
                return Forbid();
            }
        }

        try
        {
            var paymentMethods = await _paymentMethodService.GetByPointOfSaleAsync(id, includeInactive);
            return Ok(paymentMethods);
        }
        catch (DomainException ex) when (ex.Message.Contains("no encontrado"))
        {
            return NotFound(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Assigns a payment method to a point of sale. Administrator only.
    /// </summary>
    /// <param name="id">The point of sale ID.</param>
    /// <param name="paymentMethodId">The payment method ID to assign.</param>
    /// <returns>The assignment details.</returns>
    [HttpPost("{id:guid}/payment-methods/{paymentMethodId:guid}")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(PointOfSalePaymentMethodDto), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> AssignPaymentMethod(Guid id, Guid paymentMethodId)
    {
        try
        {
            var assignment = await _paymentMethodService.AssignToPointOfSaleAsync(id, paymentMethodId);
            _logger.LogInformation("Payment method {PaymentMethodId} assigned to point of sale {PointOfSaleId}", paymentMethodId, id);
            return CreatedAtAction(nameof(GetPaymentMethods), new { id }, assignment);
        }
        catch (DomainException ex) when (ex.Message.Contains("no encontrado"))
        {
            return NotFound(new { error = ex.Message });
        }
        catch (DomainException ex) when (ex.Message.Contains("ya está asignado"))
        {
            return Conflict(new { error = ex.Message });
        }
        catch (DomainException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Unassigns a payment method from a point of sale. Administrator only.
    /// </summary>
    /// <param name="id">The point of sale ID.</param>
    /// <param name="paymentMethodId">The payment method ID to unassign.</param>
    /// <returns>No content on success.</returns>
    [HttpDelete("{id:guid}/payment-methods/{paymentMethodId:guid}")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> UnassignPaymentMethod(Guid id, Guid paymentMethodId)
    {
        try
        {
            await _paymentMethodService.UnassignFromPointOfSaleAsync(id, paymentMethodId);
            _logger.LogInformation("Payment method {PaymentMethodId} unassigned from point of sale {PointOfSaleId}", paymentMethodId, id);
            return NoContent();
        }
        catch (DomainException ex) when (ex.Message.Contains("no encontrada"))
        {
            return NotFound(new { error = ex.Message });
        }
        catch (DomainException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Changes the status of a payment method assignment for a point of sale. Administrator only.
    /// </summary>
    /// <param name="id">The point of sale ID.</param>
    /// <param name="paymentMethodId">The payment method ID.</param>
    /// <param name="request">The status change request.</param>
    /// <returns>The updated assignment.</returns>
    [HttpPatch("{id:guid}/payment-methods/{paymentMethodId:guid}/status")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(PointOfSalePaymentMethodDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> ChangePaymentMethodStatus(Guid id, Guid paymentMethodId, [FromBody] ChangeStatusRequest request)
    {
        try
        {
            var assignment = await _paymentMethodService.ChangeAssignmentStatusAsync(id, paymentMethodId, request.IsActive);
            var action = request.IsActive ? "activated" : "deactivated";
            _logger.LogInformation("Payment method {PaymentMethodId} {Action} for point of sale {PointOfSaleId}", paymentMethodId, action, id);
            return Ok(assignment);
        }
        catch (DomainException ex) when (ex.Message.Contains("no encontrada"))
        {
            return NotFound(new { error = ex.Message });
        }
        catch (DomainException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    #endregion

    #region Commission Tiers

    [HttpGet("{id:guid}/commission-tiers")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(List<CommissionTierDto>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetCommissionTiers(Guid id)
    {
        try
        {
            var tiers = await _commissionTierService.GetTiersAsync(id);
            return Ok(tiers);
        }
        catch (DomainException ex) when (ex.Message.Contains("no encontrado"))
        {
            return NotFound(new { error = ex.Message });
        }
    }

    [HttpPut("{id:guid}/commission-tiers")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(List<CommissionTierDto>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> ReplaceCommissionTiers(Guid id, [FromBody] ReplaceCommissionTiersRequest request)
    {
        var validationResult = await _commissionTiersValidator.ValidateAsync(request);
        if (!validationResult.IsValid)
        {
            return BadRequest(new { errors = validationResult.Errors.Select(e => e.ErrorMessage) });
        }

        try
        {
            var tiers = await _commissionTierService.ReplaceTiersAsync(id, request);
            return Ok(tiers);
        }
        catch (DomainException ex) when (ex.Message.Contains("no encontrado"))
        {
            return NotFound(new { error = ex.Message });
        }
        catch (DomainException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    #endregion
}

/// <summary>
/// Request DTO for changing point of sale status.
/// </summary>
public class ChangeStatusRequest
{
    /// <summary>
    /// The new active status.
    /// </summary>
    public bool IsActive { get; set; }
}
