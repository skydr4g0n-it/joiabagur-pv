using JoiabagurPV.Domain.Commission;
using JoiabagurPV.Domain.Entities;

namespace JoiabagurPV.Domain.Interfaces.Repositories;

/// <summary>
/// Repository interface for Return entity operations.
/// </summary>
public interface IReturnRepository : IRepository<Return>
{
    /// <summary>
    /// Gets a return by ID with all related entities loaded.
    /// </summary>
    /// <param name="id">The return ID.</param>
    /// <returns>The return with related data, or null if not found.</returns>
    Task<Return?> GetByIdWithDetailsAsync(Guid id);

    /// <summary>
    /// Gets returns for a specific point of sale with pagination and filtering.
    /// </summary>
    /// <param name="pointOfSaleId">The point of sale ID.</param>
    /// <param name="startDate">Optional start date filter.</param>
    /// <param name="endDate">Optional end date filter.</param>
    /// <param name="productId">Optional product filter.</param>
    /// <param name="skip">Number of records to skip.</param>
    /// <param name="take">Number of records to take (max 50).</param>
    /// <returns>Paginated list of returns.</returns>
    Task<(List<Return> Returns, int TotalCount)> GetByPointOfSaleAsync(
        Guid pointOfSaleId,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? productId = null,
        int skip = 0,
        int take = 50);

    /// <summary>
    /// Gets all returns with pagination and filtering (admin only).
    /// </summary>
    /// <param name="startDate">Optional start date filter.</param>
    /// <param name="endDate">Optional end date filter.</param>
    /// <param name="pointOfSaleId">Optional point of sale filter.</param>
    /// <param name="productId">Optional product filter.</param>
    /// <param name="skip">Number of records to skip.</param>
    /// <param name="take">Number of records to take (max 50).</param>
    /// <returns>Paginated list of returns.</returns>
    Task<(List<Return> Returns, int TotalCount)> GetAllReturnsAsync(
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? pointOfSaleId = null,
        Guid? productId = null,
        int skip = 0,
        int take = 50);

    /// <summary>
    /// Gets returns for multiple points of sale (for operators with multiple POS assignments).
    /// </summary>
    /// <param name="pointOfSaleIds">List of point of sale IDs.</param>
    /// <param name="startDate">Optional start date filter.</param>
    /// <param name="endDate">Optional end date filter.</param>
    /// <param name="productId">Optional product filter.</param>
    /// <param name="skip">Number of records to skip.</param>
    /// <param name="take">Number of records to take (max 50).</param>
    /// <returns>Paginated list of returns.</returns>
    Task<(List<Return> Returns, int TotalCount)> GetByPointOfSalesAsync(
        IEnumerable<Guid> pointOfSaleIds,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? productId = null,
        int skip = 0,
        int take = 50);

    Task<decimal> GetReturnAmountTotalInWindowAsync(
        IEnumerable<Guid>? pointOfSaleIds,
        DateTime? startDate = null,
        DateTime? endDate = null,
        Guid? pointOfSaleId = null);

    Task<List<ReturnYtdEvent>> GetReturnYtdEventsForPosYearAsync(
        Guid pointOfSaleId,
        DateTime yearStartUtc,
        DateTime yearEndUtc);
}
