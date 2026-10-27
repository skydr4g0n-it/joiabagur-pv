using JoiabagurPV.Application.DTOs.PointOfSales;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Constants;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Exceptions;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.Extensions.Logging;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Service for point of sale management operations.
/// </summary>
public class PointOfSaleService : IPointOfSaleService
{
    private readonly IPointOfSaleRepository _pointOfSaleRepository;
    private readonly IUserPointOfSaleRepository _userPointOfSaleRepository;
    private readonly IPaymentMethodRepository _paymentMethodRepository;
    private readonly IPaymentMethodService _paymentMethodService;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<PointOfSaleService> _logger;

    public PointOfSaleService(
        IPointOfSaleRepository pointOfSaleRepository,
        IUserPointOfSaleRepository userPointOfSaleRepository,
        IPaymentMethodRepository paymentMethodRepository,
        IPaymentMethodService paymentMethodService,
        IUnitOfWork unitOfWork,
        ILogger<PointOfSaleService> logger)
    {
        _pointOfSaleRepository = pointOfSaleRepository;
        _userPointOfSaleRepository = userPointOfSaleRepository;
        _paymentMethodRepository = paymentMethodRepository;
        _paymentMethodService = paymentMethodService;
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    /// <inheritdoc/>
    public async Task<List<PointOfSaleDto>> GetAllAsync(bool includeInactive = true)
    {
        _logger.LogInformation("PointOfSaleService.GetAllAsync called with includeInactive={IncludeInactive}", includeInactive);
        var pointOfSales = await _pointOfSaleRepository.GetAllAsync(includeInactive);
        var result = pointOfSales.Select(MapToDto).ToList();
        _logger.LogInformation("PointOfSaleService.GetAllAsync returning {Count} POS", result.Count);
        return result;
    }

    /// <inheritdoc/>
    public async Task<List<PointOfSaleDto>> GetByUserAsync(Guid userId)
    {
        var pointOfSales = await _pointOfSaleRepository.GetByUserAsync(userId, includeInactive: false);
        return pointOfSales.Select(MapToDto).ToList();
    }

    /// <inheritdoc/>
    public async Task<PointOfSaleDto?> GetByIdAsync(Guid pointOfSaleId)
    {
        var pointOfSale = await _pointOfSaleRepository.GetByIdAsync(pointOfSaleId);
        return pointOfSale != null ? MapToDto(pointOfSale) : null;
    }

    /// <inheritdoc/>
    public async Task<PointOfSaleDto> CreateAsync(CreatePointOfSaleRequest request)
    {
        // Validate code uniqueness
        if (await _pointOfSaleRepository.CodeExistsAsync(request.Code))
        {
            throw new DomainException("El código de punto de venta ya está en uso");
        }

        var pointOfSale = new PointOfSale
        {
            Name = request.Name,
            Code = request.Code.ToUpperInvariant(),
            Address = request.Address,
            Phone = request.Phone,
            Email = request.Email,
            IsActive = true,
            AllowManualPriceEdit = request.AllowManualPriceEdit
        };

        await _pointOfSaleRepository.AddAsync(pointOfSale);
        await _unitOfWork.SaveChangesAsync();

        var giftCardMethod = await _paymentMethodRepository.GetByCodeAsync(GiftCardConstants.GiftCardPaymentMethodCode);
        if (giftCardMethod != null)
        {
            try
            {
                await _paymentMethodService.AssignToPointOfSaleAsync(pointOfSale.Id, giftCardMethod.Id);
            }
            catch (DomainException ex) when (ex.Message.Contains("ya está asignado"))
            {
                // Already assigned (idempotent)
            }
        }

        _logger.LogInformation("Point of sale {Code} created successfully", pointOfSale.Code);

        return MapToDto(pointOfSale);
    }

    /// <inheritdoc/>
    public async Task<PointOfSaleDto> UpdateAsync(Guid pointOfSaleId, UpdatePointOfSaleRequest request)
    {
        var pointOfSale = await _pointOfSaleRepository.GetByIdAsync(pointOfSaleId);
        if (pointOfSale == null)
        {
            throw new DomainException("Punto de venta no encontrado");
        }

        pointOfSale.Name = request.Name;
        pointOfSale.Address = request.Address;
        pointOfSale.Phone = request.Phone;
        pointOfSale.Email = request.Email;
        pointOfSale.IsActive = request.IsActive;
        pointOfSale.AllowManualPriceEdit = request.AllowManualPriceEdit;

        await _pointOfSaleRepository.UpdateAsync(pointOfSale);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Point of sale {Code} updated successfully", pointOfSale.Code);

        return MapToDto(pointOfSale);
    }

    /// <inheritdoc/>
    public async Task<PointOfSaleDto> ChangeStatusAsync(Guid pointOfSaleId, bool isActive)
    {
        var pointOfSale = await _pointOfSaleRepository.GetByIdAsync(pointOfSaleId);
        if (pointOfSale == null)
        {
            throw new DomainException("Punto de venta no encontrado");
        }

        _logger.LogInformation("Changing status of POS {Code} from {CurrentStatus} to {NewStatus}", pointOfSale.Code, pointOfSale.IsActive, isActive);

        // If deactivating, check for active assignments
        if (!isActive && await _pointOfSaleRepository.HasActiveAssignmentsAsync(pointOfSaleId))
        {
            _logger.LogWarning("Cannot deactivate POS {Code} - has active assignments", pointOfSale.Code);
            throw new DomainException("No se puede desactivar punto de venta con operadores asignados activos");
        }

        pointOfSale.IsActive = isActive;

        await _pointOfSaleRepository.UpdateAsync(pointOfSale);
        await _unitOfWork.SaveChangesAsync();

        var action = isActive ? "activated" : "deactivated";
        _logger.LogInformation("Point of sale {Code} {Action} successfully", pointOfSale.Code, action);

        return MapToDto(pointOfSale);
    }

    /// <inheritdoc/>
    public async Task<bool> UserHasAccessAsync(Guid userId, Guid pointOfSaleId)
    {
        var assignment = await _userPointOfSaleRepository.GetAssignmentAsync(userId, pointOfSaleId);
        return assignment != null && assignment.IsActive;
    }

    private static PointOfSaleDto MapToDto(PointOfSale pointOfSale)
    {
        return new PointOfSaleDto
        {
            Id = pointOfSale.Id,
            Name = pointOfSale.Name,
            Code = pointOfSale.Code,
            Address = pointOfSale.Address,
            Phone = pointOfSale.Phone,
            Email = pointOfSale.Email,
            IsActive = pointOfSale.IsActive,
            AllowManualPriceEdit = pointOfSale.AllowManualPriceEdit,
            CreatedAt = pointOfSale.CreatedAt,
            UpdatedAt = pointOfSale.UpdatedAt
        };
    }
}
