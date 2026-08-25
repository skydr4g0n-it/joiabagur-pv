using JoiabagurPV.Domain.Entities;

namespace JoiabagurPV.Domain.Interfaces.Repositories;

/// <summary>
/// Repository interface for Product entity operations.
/// </summary>
public interface IProductRepository : IRepository<Product>
{
    /// <summary>
    /// Gets a product by its unique SKU.
    /// </summary>
    /// <param name="sku">The SKU to search for.</param>
    /// <returns>The product if found, null otherwise.</returns>
    Task<Product?> GetBySkuAsync(string sku);

    /// <summary>
    /// Checks if a SKU is already in use.
    /// </summary>
    /// <param name="sku">The SKU to check.</param>
    /// <param name="excludeId">Optional ID to exclude from the check.</param>
    /// <returns>True if SKU exists, false otherwise.</returns>
    Task<bool> SkuExistsAsync(string sku, Guid? excludeId = null);

    /// <summary>
    /// Gets a product with its photos loaded.
    /// </summary>
    /// <param name="id">The product ID.</param>
    /// <returns>The product with photos, or null if not found.</returns>
    Task<Product?> GetWithPhotosAsync(Guid id);

    /// <summary>
    /// Gets all products in a specific collection.
    /// </summary>
    /// <param name="collectionId">The collection ID.</param>
    /// <param name="includeInactive">Whether to include inactive products.</param>
    /// <returns>List of products in the collection.</returns>
    Task<List<Product>> GetByCollectionAsync(Guid collectionId, bool includeInactive = false);

    /// <summary>
    /// Gets all products with optional filtering.
    /// </summary>
    /// <param name="includeInactive">Whether to include inactive products.</param>
    /// <returns>List of products.</returns>
    Task<List<Product>> GetAllAsync(bool includeInactive = true);

    /// <summary>
    /// Gets multiple products by their SKUs.
    /// </summary>
    /// <param name="skus">Collection of SKUs to search for.</param>
    /// <returns>Dictionary mapping SKUs to products.</returns>
    Task<Dictionary<string, Product>> GetBySkusAsync(IEnumerable<string> skus);

    /// <summary>
    /// Adds multiple products in a batch.
    /// </summary>
    /// <param name="products">The products to add.</param>
    Task AddRangeAsync(IEnumerable<Product> products);

    /// <summary>
    /// Updates multiple products in a batch.
    /// </summary>
    /// <param name="products">The products to update.</param>
    Task UpdateRangeAsync(IEnumerable<Product> products);

    /// <summary>
    /// Writes <c>UpdatedAt</c> on the given products in SQL, bypassing the store-generated
    /// column metadata that would otherwise drop the value from an EF UPDATE.
    /// </summary>
    Task StampUpdatedAtAsync(IEnumerable<Guid> productIds);
}




