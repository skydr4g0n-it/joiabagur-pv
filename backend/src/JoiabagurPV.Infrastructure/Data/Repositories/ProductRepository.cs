using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.EntityFrameworkCore;

namespace JoiabagurPV.Infrastructure.Data.Repositories;

/// <summary>
/// Repository implementation for Product entity operations.
/// </summary>
public class ProductRepository : Repository<Product>, IProductRepository
{
    private readonly ApplicationDbContext _context;

    public ProductRepository(ApplicationDbContext context) : base(context)
    {
        _context = context;
    }

    /// <inheritdoc/>
    public async Task<Product?> GetBySkuAsync(string sku)
    {
        var normalizedSku = (sku ?? string.Empty).Trim().ToUpperInvariant();
        return await _context.Products
            .FirstOrDefaultAsync(p => p.SKU.ToUpper() == normalizedSku);
    }

    /// <inheritdoc/>
    public async Task<bool> SkuExistsAsync(string sku, Guid? excludeId = null)
    {
        var normalizedSku = (sku ?? string.Empty).Trim().ToUpperInvariant();
        if (excludeId.HasValue)
        {
            return await _context.Products
                .AnyAsync(p => p.SKU.ToUpper() == normalizedSku && p.Id != excludeId.Value);
        }

        return await _context.Products
            .AnyAsync(p => p.SKU.ToUpper() == normalizedSku);
    }

    /// <inheritdoc/>
    public async Task<Product?> GetWithPhotosAsync(Guid id)
    {
        return await _context.Products
            .Include(p => p.Photos.OrderBy(pp => pp.DisplayOrder))
            .Include(p => p.Collection)
            .FirstOrDefaultAsync(p => p.Id == id);
    }

    /// <inheritdoc/>
    public async Task<List<Product>> GetByCollectionAsync(Guid collectionId, bool includeInactive = false)
    {
        var query = _context.Products
            .Where(p => p.CollectionId == collectionId);

        if (!includeInactive)
        {
            query = query.Where(p => p.IsActive);
        }

        return await query
            .OrderBy(p => p.Name)
            .ToListAsync();
    }

    /// <inheritdoc/>
    public async Task<List<Product>> GetAllAsync(bool includeInactive = true)
    {
        var query = _context.Products
            .Include(p => p.Photos)
            .Include(p => p.Collection)
            .AsQueryable();

        if (!includeInactive)
        {
            query = query.Where(p => p.IsActive);
        }

        return await query
            .OrderBy(p => p.Name)
            .ToListAsync();
    }

    /// <inheritdoc/>
    public async Task<Dictionary<string, Product>> GetBySkusAsync(IEnumerable<string> skus)
    {
        var skuList = skus
            .Where(s => !string.IsNullOrWhiteSpace(s))
            .Select(s => s.Trim().ToUpperInvariant())
            .ToList();

        var products = await _context.Products
            .Where(p => skuList.Contains(p.SKU.ToUpper()))
            .ToListAsync();

        return products.ToDictionary(p => p.SKU.ToUpperInvariant(), p => p);
    }

    /// <inheritdoc/>
    public async Task AddRangeAsync(IEnumerable<Product> products)
    {
        await _context.Products.AddRangeAsync(products);
    }

    /// <inheritdoc/>
    public Task UpdateRangeAsync(IEnumerable<Product> products)
    {
        _context.Products.UpdateRange(products);
        return Task.CompletedTask;
    }

    /// <inheritdoc/>
    public async Task StampUpdatedAtAsync(IEnumerable<Guid> productIds)
    {
        var ids = productIds.Distinct().ToList();
        if (ids.Count == 0)
        {
            return;
        }

        var now = DateTime.UtcNow;
        await _context.Products
            .Where(product => ids.Contains(product.Id))
            .ExecuteUpdateAsync(setters => setters.SetProperty(product => product.UpdatedAt, now));
    }
}



