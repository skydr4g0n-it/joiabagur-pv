using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.EntityFrameworkCore;

namespace JoiabagurPV.Infrastructure.Data.Repositories;

/// <summary>
/// Repository implementation for InventoryMovement entities.
/// </summary>
public class InventoryMovementRepository : Repository<InventoryMovement>, IInventoryMovementRepository
{
    public InventoryMovementRepository(ApplicationDbContext context) : base(context)
    {
    }

    /// <inheritdoc/>
    public async Task<List<InventoryMovement>> FindByInventoryAsync(Guid inventoryId, int limit = 50)
    {
        return await _dbSet
            .Include(m => m.User)
            .Where(m => m.InventoryId == inventoryId)
            .OrderByDescending(m => m.MovementDate)
            .Take(limit)
            .ToListAsync();
    }

    /// <inheritdoc/>
    public async Task<(List<InventoryMovement> Movements, int TotalCount)> FindByFiltersAsync(
        Guid? productId = null,
        Guid? pointOfSaleId = null,
        DateTime? startDate = null,
        DateTime? endDate = null,
        int page = 1,
        int pageSize = 50)
    {
        var query = _dbSet
            .Include(m => m.User)
            .Include(m => m.Inventory)
                .ThenInclude(i => i.Product)
            .Include(m => m.Inventory)
                .ThenInclude(i => i.PointOfSale)
            .AsQueryable();

        // Apply filters
        if (productId.HasValue)
        {
            query = query.Where(m => m.Inventory.ProductId == productId.Value);
        }

        if (pointOfSaleId.HasValue)
        {
            query = query.Where(m => m.Inventory.PointOfSaleId == pointOfSaleId.Value);
        }

        if (startDate.HasValue)
        {
            query = query.Where(m => m.MovementDate >= startDate.Value);
        }

        if (endDate.HasValue)
        {
            query = query.Where(m => m.MovementDate <= endDate.Value);
        }

        // Get total count before pagination
        var totalCount = await query.CountAsync();

        // Apply pagination
        var movements = await query
            .OrderByDescending(m => m.MovementDate)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync();

        return (movements, totalCount);
    }

    /// <inheritdoc/>
    public async Task<List<MovementSummaryProjection>> GetMovementSummaryByProductAsync(
        DateTime startDate,
        DateTime endDate,
        Guid? pointOfSaleId = null,
        string? productSearch = null)
    {
        var query = _dbSet
            .Where(m => m.MovementDate >= startDate && m.MovementDate <= endDate);

        if (pointOfSaleId.HasValue)
        {
            query = query.Where(m => m.Inventory.PointOfSaleId == pointOfSaleId.Value);
        }

        if (!string.IsNullOrWhiteSpace(productSearch))
        {
            var search = productSearch.Trim().ToLower();
            query = query.Where(m =>
                m.Inventory.Product.Name.ToLower().Contains(search)
                || m.Inventory.Product.SKU.ToLower().Contains(search));
        }

        var rows = await query
            .Select(m => new
            {
                m.Inventory.ProductId,
                ProductName = m.Inventory.Product.Name,
                ProductSku = m.Inventory.Product.SKU,
                m.QuantityChange
            })
            .ToListAsync();

        return rows
            .GroupBy(m => new { m.ProductId, m.ProductName, m.ProductSku })
            .Select(g =>
            {
                var additions = g.Sum(m => m.QuantityChange > 0 ? m.QuantityChange : 0);
                var subtractions = g.Sum(m => m.QuantityChange < 0 ? -m.QuantityChange : 0);
                return new MovementSummaryProjection(
                    g.Key.ProductId,
                    g.Key.ProductName,
                    g.Key.ProductSku,
                    additions,
                    subtractions,
                    additions - subtractions);
            })
            .ToList();
    }

    /// <inheritdoc/>
    public async Task<(List<MovementDetailProjection> Items, int TotalCount)> GetMovementDetailRowsAsync(
        DateTime startDate,
        DateTime endDate,
        Guid? pointOfSaleId = null,
        string? productSearch = null,
        int? page = null,
        int? pageSize = null)
    {
        var query = _dbSet
            .Where(m => m.MovementDate >= startDate && m.MovementDate <= endDate);

        if (pointOfSaleId.HasValue)
        {
            query = query.Where(m => m.Inventory.PointOfSaleId == pointOfSaleId.Value);
        }

        if (!string.IsNullOrWhiteSpace(productSearch))
        {
            var search = productSearch.Trim().ToLower();
            query = query.Where(m =>
                m.Inventory.Product.Name.ToLower().Contains(search)
                || m.Inventory.Product.SKU.ToLower().Contains(search));
        }

        var ordered = query
            .OrderByDescending(m => m.MovementDate)
            .ThenByDescending(m => m.Id);

        var totalCount = await ordered.CountAsync();
        var paged = page.HasValue && pageSize.HasValue
            ? ordered.Skip((page.Value - 1) * pageSize.Value).Take(pageSize.Value)
            : ordered;

        var items = await paged
            .Select(m => new MovementDetailProjection(
                m.Id,
                m.InventoryId,
                m.Inventory.ProductId,
                m.Inventory.Product.Name,
                m.Inventory.Product.SKU,
                m.Inventory.PointOfSaleId,
                m.Inventory.PointOfSale.Name,
                m.MovementType,
                m.QuantityChange,
                m.QuantityBefore,
                m.QuantityAfter,
                m.UserId,
                m.User.FullName,
                m.Reason,
                m.MovementDate,
                m.SaleId,
                m.ReturnId))
            .ToListAsync();

        return (items, totalCount);
    }
}

