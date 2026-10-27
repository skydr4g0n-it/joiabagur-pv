using JoiabagurPV.Application.DTOs.PaymentMethods;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>
/// Service interface for payment method management operations.
/// </summary>
public interface IPaymentMethodService
{
    /// <summary>
    /// Gets all payment methods.
    /// </summary>
    /// <param name="includeInactive">Whether to include inactive payment methods.</param>
    /// <returns>List of payment method DTOs.</returns>
    Task<List<PaymentMethodDto>> GetAllAsync(bool includeInactive = true);

    /// <summary>
    /// Gets a payment method by ID.
    /// </summary>
    /// <param name="paymentMethodId">The payment method ID.</param>
    /// <returns>The payment method DTO if found.</returns>
    Task<PaymentMethodDto?> GetByIdAsync(Guid paymentMethodId);

    /// <summary>
    /// Creates a new payment method.
    /// </summary>
    /// <param name="request">The create payment method request.</param>
    /// <returns>The created payment method DTO.</returns>
    Task<PaymentMethodDto> CreateAsync(CreatePaymentMethodRequest request);

    /// <summary>
    /// Updates an existing payment method.
    /// </summary>
    /// <param name="paymentMethodId">The payment method ID to update.</param>
    /// <param name="request">The update payment method request.</param>
    /// <returns>The updated payment method DTO.</returns>
    Task<PaymentMethodDto> UpdateAsync(Guid paymentMethodId, UpdatePaymentMethodRequest request);

    /// <summary>
    /// Changes the status (active/inactive) of a payment method.
    /// </summary>
    /// <param name="paymentMethodId">The payment method ID.</param>
    /// <param name="isActive">The new active status.</param>
    /// <returns>The updated payment method DTO.</returns>
    Task<PaymentMethodDto> ChangeStatusAsync(Guid paymentMethodId, bool isActive);

    /// <summary>
    /// Gets payment methods assigned to a point of sale.
    /// </summary>
    /// <param name="pointOfSaleId">The point of sale ID.</param>
    /// <param name="includeInactive">Whether to include inactive assignments.</param>
    /// <returns>List of payment method assignment DTOs.</returns>
    Task<List<PointOfSalePaymentMethodDto>> GetByPointOfSaleAsync(
        Guid pointOfSaleId,
        bool includeInactive = false,
        bool excludeGiftCardFromSales = false);

    /// <summary>
    /// Assigns a payment method to a point of sale.
    /// </summary>
    /// <param name="pointOfSaleId">The point of sale ID.</param>
    /// <param name="paymentMethodId">The payment method ID.</param>
    /// <returns>The created assignment DTO.</returns>
    Task<PointOfSalePaymentMethodDto> AssignToPointOfSaleAsync(Guid pointOfSaleId, Guid paymentMethodId);

    /// <summary>
    /// Unassigns a payment method from a point of sale.
    /// </summary>
    /// <param name="pointOfSaleId">The point of sale ID.</param>
    /// <param name="paymentMethodId">The payment method ID.</param>
    Task UnassignFromPointOfSaleAsync(Guid pointOfSaleId, Guid paymentMethodId);

    /// <summary>
    /// Changes the status of a payment method assignment for a point of sale.
    /// </summary>
    /// <param name="pointOfSaleId">The point of sale ID.</param>
    /// <param name="paymentMethodId">The payment method ID.</param>
    /// <param name="isActive">The new active status.</param>
    /// <returns>The updated assignment DTO.</returns>
    Task<PointOfSalePaymentMethodDto> ChangeAssignmentStatusAsync(Guid pointOfSaleId, Guid paymentMethodId, bool isActive);

    /// <summary>
    /// Validates if a payment method is available for a point of sale.
    /// </summary>
    /// <param name="pointOfSaleId">The point of sale ID.</param>
    /// <param name="paymentMethodId">The payment method ID.</param>
    /// <returns>True if the payment method is active and assigned to the point of sale.</returns>
    Task<bool> IsPaymentMethodAvailableAsync(Guid pointOfSaleId, Guid paymentMethodId);
}
