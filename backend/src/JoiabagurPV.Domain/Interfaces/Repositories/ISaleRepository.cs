using JoiabagurPV.Domain.Commission;
using JoiabagurPV.Domain.Entities;

namespace JoiabagurPV.Domain.Interfaces.Repositories;

/// <summary>
/// Repository interface for Sale entity operations.
/// </summary>
public interface ISaleRepository : IRepository<Sale>
{
    /// <summary>
    /// Gets a sale by ID with all related entities loaded.
    /// </summary>
    /// <param name="id">The sale ID.</param>
    /// <returns>The sale with related data, or null if not found.</returns>
    Task<Sale?> GetByIdWithDetailsAsync(Guid id);

    /// <summary>
    /// Gets sales for a specific point of sale with pagination and filtering.
    /// </summary>
    /// <param name="pointOfSaleId">The point of sale ID.</param>
    /// <param name="startDate">Optional start date filter.</param>
    /// <param name="endDate">Optional end date filter.</param>
    /// <param name="productId">Optional product filter.</param>
    /// <param name="userId">Optional user filter.</param>
    /// <param name="paymentMethodId">Optional payment method filter.</param>
    /// <param name="skip">Number of records to skip.</param>
    /// <param name="take">Number of records to take (max 50).</param>
    /// <returns>Paginated list of sales.</returns>
    Task<(List<Sale> Sales, int TotalCount)> GetByPointOfSaleAsync(
        Guid pointOfSaleId,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? productId = null,
        Guid? userId = null,
        Guid? paymentMethodId = null,
        int skip = 0,
        int take = 50);

    /// <summary>
    /// Gets all sales with pagination and filtering (admin only).
    /// </summary>
    /// <param name="startDate">Optional start date filter.</param>
    /// <param name="endDate">Optional end date filter.</param>
    /// <param name="pointOfSaleId">Optional point of sale filter.</param>
    /// <param name="productId">Optional product filter.</param>
    /// <param name="userId">Optional user filter.</param>
    /// <param name="paymentMethodId">Optional payment method filter.</param>
    /// <param name="skip">Number of records to skip.</param>
    /// <param name="take">Number of records to take (max 50).</param>
    /// <returns>Paginated list of sales.</returns>
    Task<(List<Sale> Sales, int TotalCount)> GetAllSalesAsync(
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? pointOfSaleId = null,
        Guid? productId = null,
        Guid? userId = null,
        Guid? paymentMethodId = null,
        int skip = 0,
        int take = 50);

    /// <summary>
    /// Gets sales for multiple points of sale (for operators with multiple POS assignments).
    /// </summary>
    /// <param name="pointOfSaleIds">List of point of sale IDs.</param>
    /// <param name="startDate">Optional start date filter.</param>
    /// <param name="endDate">Optional end date filter.</param>
    /// <param name="productId">Optional product filter.</param>
    /// <param name="userId">Optional user filter.</param>
    /// <param name="paymentMethodId">Optional payment method filter.</param>
    /// <param name="skip">Number of records to skip.</param>
    /// <param name="take">Number of records to take (max 50).</param>
    /// <returns>Paginated list of sales.</returns>
    Task<(List<Sale> Sales, int TotalCount)> GetByPointOfSalesAsync(
        IEnumerable<Guid> pointOfSaleIds,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? productId = null,
        Guid? userId = null,
        Guid? paymentMethodId = null,
        int skip = 0,
        int take = 50);

    /// <summary>
    /// Gets sales for the report with extended filters and pagination.
    /// Includes Product.Collection navigation for collection name.
    /// </summary>
    Task<(List<Sale> Sales, int TotalCount)> GetSalesForReportAsync(
        IEnumerable<Guid>? pointOfSaleIds,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? pointOfSaleId = null,
        Guid? productId = null,
        Guid? userId = null,
        Guid? paymentMethodId = null,
        string? search = null,
        decimal? amountMin = null,
        decimal? amountMax = null,
        bool? hasPhoto = null,
        bool? priceWasOverridden = null,
        int skip = 0,
        int take = 20);

    /// <summary>
    /// Gets aggregate totals for the sales report (count, total quantity, total amount) 
    /// over the full filtered result set without pagination.
    /// </summary>
    Task<(int TotalCount, int TotalQuantity, decimal TotalAmount)> GetSalesReportAggregatesAsync(
        IEnumerable<Guid>? pointOfSaleIds,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? pointOfSaleId = null,
        Guid? productId = null,
        Guid? userId = null,
        Guid? paymentMethodId = null,
        string? search = null,
        decimal? amountMin = null,
        decimal? amountMax = null,
        bool? hasPhoto = null,
        bool? priceWasOverridden = null);

    Task<List<SaleReportLine>> GetSaleLinesForCommissionReportAsync(
        IEnumerable<Guid>? pointOfSaleIds,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? pointOfSaleId = null,
        Guid? productId = null,
        Guid? userId = null,
        Guid? paymentMethodId = null,
        string? search = null,
        decimal? amountMin = null,
        decimal? amountMax = null,
        bool? hasPhoto = null,
        bool? priceWasOverridden = null);

    Task<List<SaleYtdEvent>> GetSaleYtdEventsForPosYearAsync(
        Guid pointOfSaleId,
        DateTime yearStartUtc,
        DateTime yearEndUtc);
}
