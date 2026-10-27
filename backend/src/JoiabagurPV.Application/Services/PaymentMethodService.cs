using JoiabagurPV.Application.DTOs.PaymentMethods;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Constants;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Exceptions;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.Extensions.Logging;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Service for payment method management operations.
/// </summary>
public class PaymentMethodService : IPaymentMethodService
{
    private readonly IPaymentMethodRepository _paymentMethodRepository;
    private readonly IPointOfSalePaymentMethodRepository _posPaymentMethodRepository;
    private readonly IPointOfSaleRepository _pointOfSaleRepository;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<PaymentMethodService> _logger;

    public PaymentMethodService(
        IPaymentMethodRepository paymentMethodRepository,
        IPointOfSalePaymentMethodRepository posPaymentMethodRepository,
        IPointOfSaleRepository pointOfSaleRepository,
        IUnitOfWork unitOfWork,
        ILogger<PaymentMethodService> logger)
    {
        _paymentMethodRepository = paymentMethodRepository;
        _posPaymentMethodRepository = posPaymentMethodRepository;
        _pointOfSaleRepository = pointOfSaleRepository;
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    /// <inheritdoc/>
    public async Task<List<PaymentMethodDto>> GetAllAsync(bool includeInactive = true)
    {
        var paymentMethods = await _paymentMethodRepository.GetAllAsync(includeInactive);
        return paymentMethods.Select(MapToDto).ToList();
    }

    /// <inheritdoc/>
    public async Task<PaymentMethodDto?> GetByIdAsync(Guid paymentMethodId)
    {
        var paymentMethod = await _paymentMethodRepository.GetByIdAsync(paymentMethodId);
        return paymentMethod != null ? MapToDto(paymentMethod) : null;
    }

    /// <inheritdoc/>
    public async Task<PaymentMethodDto> CreateAsync(CreatePaymentMethodRequest request)
    {
        // Validate code uniqueness
        if (await _paymentMethodRepository.CodeExistsAsync(request.Code))
        {
            throw new DomainException("El código de método de pago ya está en uso");
        }

        var paymentMethod = new PaymentMethod
        {
            Code = request.Code.ToUpperInvariant(),
            Name = request.Name,
            Description = request.Description,
            IsActive = true
        };

        await _paymentMethodRepository.AddAsync(paymentMethod);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Payment method {Code} created successfully", paymentMethod.Code);

        return MapToDto(paymentMethod);
    }

    /// <inheritdoc/>
    public async Task<PaymentMethodDto> UpdateAsync(Guid paymentMethodId, UpdatePaymentMethodRequest request)
    {
        var paymentMethod = await _paymentMethodRepository.GetByIdAsync(paymentMethodId);
        if (paymentMethod == null)
        {
            throw new DomainException("Método de pago no encontrado");
        }

        paymentMethod.Name = request.Name;
        paymentMethod.Description = request.Description;

        await _paymentMethodRepository.UpdateAsync(paymentMethod);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Payment method {Code} updated successfully", paymentMethod.Code);

        return MapToDto(paymentMethod);
    }

    /// <inheritdoc/>
    public async Task<PaymentMethodDto> ChangeStatusAsync(Guid paymentMethodId, bool isActive)
    {
        var paymentMethod = await _paymentMethodRepository.GetByIdAsync(paymentMethodId);
        if (paymentMethod == null)
        {
            throw new DomainException("Método de pago no encontrado");
        }

        if (!isActive && paymentMethod.Code == GiftCardConstants.GiftCardPaymentMethodCode)
        {
            throw new DomainException("No se puede desactivar el método de pago de tarjeta regalo del sistema");
        }

        paymentMethod.IsActive = isActive;

        await _paymentMethodRepository.UpdateAsync(paymentMethod);
        await _unitOfWork.SaveChangesAsync();

        var action = isActive ? "activated" : "deactivated";
        _logger.LogInformation("Payment method {Code} {Action} successfully", paymentMethod.Code, action);

        return MapToDto(paymentMethod);
    }

    /// <inheritdoc/>
    public async Task<List<PointOfSalePaymentMethodDto>> GetByPointOfSaleAsync(
        Guid pointOfSaleId,
        bool includeInactive = false,
        bool excludeGiftCardFromSales = false)
    {
        // Verify point of sale exists
        if (!await _pointOfSaleRepository.ExistsAsync(pointOfSaleId))
        {
            throw new DomainException("Punto de venta no encontrado");
        }

        var assignments = await _posPaymentMethodRepository.GetByPointOfSaleAsync(pointOfSaleId, includeInactive);
        var dtos = assignments.Select(MapAssignmentToDto).ToList();
        if (excludeGiftCardFromSales)
        {
            dtos = dtos
                .Where(a => a.PaymentMethod.Code != GiftCardConstants.GiftCardPaymentMethodCode)
                .ToList();
        }

        return dtos;
    }

    /// <inheritdoc/>
    public async Task<PointOfSalePaymentMethodDto> AssignToPointOfSaleAsync(Guid pointOfSaleId, Guid paymentMethodId)
    {
        // Verify point of sale exists
        if (!await _pointOfSaleRepository.ExistsAsync(pointOfSaleId))
        {
            throw new DomainException("Punto de venta no encontrado");
        }

        // Verify payment method exists
        var paymentMethod = await _paymentMethodRepository.GetByIdAsync(paymentMethodId);
        if (paymentMethod == null)
        {
            throw new DomainException("Método de pago no encontrado");
        }

        // Check if already assigned
        var existingAssignment = await _posPaymentMethodRepository.GetAssignmentAsync(pointOfSaleId, paymentMethodId);
        if (existingAssignment != null)
        {
            if (existingAssignment.IsActive)
            {
                throw new DomainException("El método de pago ya está asignado a este punto de venta");
            }

            // Reactivate existing assignment
            existingAssignment.IsActive = true;
            existingAssignment.DeactivatedAt = null;
            await _posPaymentMethodRepository.UpdateAsync(existingAssignment);
            await _unitOfWork.SaveChangesAsync();

            _logger.LogInformation("Payment method {PaymentMethodId} reactivated for point of sale {PointOfSaleId}", 
                paymentMethodId, pointOfSaleId);

            return MapAssignmentToDto(existingAssignment);
        }

        var assignment = new PointOfSalePaymentMethod
        {
            PointOfSaleId = pointOfSaleId,
            PaymentMethodId = paymentMethodId,
            IsActive = true,
            PaymentMethod = paymentMethod
        };

        await _posPaymentMethodRepository.AddAsync(assignment);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Payment method {PaymentMethodId} assigned to point of sale {PointOfSaleId}", 
            paymentMethodId, pointOfSaleId);

        return MapAssignmentToDto(assignment);
    }

    /// <inheritdoc/>
    public async Task UnassignFromPointOfSaleAsync(Guid pointOfSaleId, Guid paymentMethodId)
    {
        var assignment = await _posPaymentMethodRepository.GetAssignmentAsync(pointOfSaleId, paymentMethodId);
        if (assignment == null)
        {
            throw new DomainException("Asignación de método de pago no encontrada");
        }

        var paymentMethod = assignment.PaymentMethod
            ?? await _paymentMethodRepository.GetByIdAsync(paymentMethodId);
        if (paymentMethod?.Code == GiftCardConstants.GiftCardPaymentMethodCode)
        {
            throw new DomainException("No se puede desasignar el método de pago de tarjeta regalo del sistema");
        }

        // Business rule: Ensure at least one active payment method per point of sale
        var activeAssignments = await _posPaymentMethodRepository.GetByPointOfSaleAsync(pointOfSaleId, includeInactive: false);
        if (activeAssignments.Count <= 1)
        {
            throw new DomainException("El punto de venta debe tener al menos un método de pago asignado");
        }

        await _posPaymentMethodRepository.DeleteAsync(assignment.Id);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Payment method {PaymentMethodId} unassigned from point of sale {PointOfSaleId}", 
            paymentMethodId, pointOfSaleId);
    }

    /// <inheritdoc/>
    public async Task<PointOfSalePaymentMethodDto> ChangeAssignmentStatusAsync(Guid pointOfSaleId, Guid paymentMethodId, bool isActive)
    {
        var assignment = await _posPaymentMethodRepository.GetAssignmentAsync(pointOfSaleId, paymentMethodId);
        if (assignment == null)
        {
            throw new DomainException("Asignación de método de pago no encontrada");
        }

        var paymentMethod = assignment.PaymentMethod
            ?? await _paymentMethodRepository.GetByIdAsync(paymentMethodId);
        if (!isActive && paymentMethod?.Code == GiftCardConstants.GiftCardPaymentMethodCode)
        {
            throw new DomainException("No se puede desactivar el método de pago de tarjeta regalo del sistema");
        }

        // Business rule: Ensure at least one active payment method per point of sale
        if (!isActive && assignment.IsActive)
        {
            var activeAssignments = await _posPaymentMethodRepository.GetByPointOfSaleAsync(pointOfSaleId, includeInactive: false);
            if (activeAssignments.Count <= 1)
            {
                throw new DomainException("El punto de venta debe tener al menos un método de pago activo");
            }
        }

        assignment.IsActive = isActive;
        assignment.DeactivatedAt = isActive ? null : DateTime.UtcNow;

        await _posPaymentMethodRepository.UpdateAsync(assignment);
        await _unitOfWork.SaveChangesAsync();

        var action = isActive ? "activated" : "deactivated";
        _logger.LogInformation("Payment method assignment {PaymentMethodId} for point of sale {PointOfSaleId} {Action}", 
            paymentMethodId, pointOfSaleId, action);

        return MapAssignmentToDto(assignment);
    }

    /// <inheritdoc/>
    public async Task<bool> IsPaymentMethodAvailableAsync(Guid pointOfSaleId, Guid paymentMethodId)
    {
        return await _posPaymentMethodRepository.IsActiveForPointOfSaleAsync(pointOfSaleId, paymentMethodId);
    }

    private static PaymentMethodDto MapToDto(PaymentMethod paymentMethod)
    {
        return new PaymentMethodDto
        {
            Id = paymentMethod.Id,
            Code = paymentMethod.Code,
            Name = paymentMethod.Name,
            Description = paymentMethod.Description,
            IsActive = paymentMethod.IsActive,
            CreatedAt = paymentMethod.CreatedAt,
            UpdatedAt = paymentMethod.UpdatedAt
        };
    }

    private static PointOfSalePaymentMethodDto MapAssignmentToDto(PointOfSalePaymentMethod assignment)
    {
        return new PointOfSalePaymentMethodDto
        {
            Id = assignment.Id,
            PointOfSaleId = assignment.PointOfSaleId,
            PaymentMethodId = assignment.PaymentMethodId,
            PaymentMethod = MapToDto(assignment.PaymentMethod),
            IsActive = assignment.IsActive,
            CreatedAt = assignment.CreatedAt,
            DeactivatedAt = assignment.DeactivatedAt
        };
    }
}
