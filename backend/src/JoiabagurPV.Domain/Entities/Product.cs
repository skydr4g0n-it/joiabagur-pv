using JoiabagurPV.Domain.Enums;

namespace JoiabagurPV.Domain.Entities;

/// <summary>
/// Represents a product in the jewelry catalog.
/// </summary>
public class Product : BaseEntity
{
    /// <summary>
    /// Unique Stock Keeping Unit identifier for the product.
    /// </summary>
    public required string SKU { get; set; }

    /// <summary>
    /// Display name of the product.
    /// </summary>
    public required string Name { get; set; }

    /// <summary>
    /// Optional description of the product.
    /// </summary>
    public string? Description { get; set; }

    /// <summary>
    /// Product price. Must be greater than zero.
    /// </summary>
    public decimal Price { get; set; }

    /// <summary>
    /// Optional foreign key to the collection this product belongs to.
    /// </summary>
    public Guid? CollectionId { get; set; }

    /// <summary>
    /// Navigation property for the associated collection.
    /// </summary>
    public Collection? Collection { get; set; }

    /// <summary>
    /// Whether the product is currently active in the catalog.
    /// </summary>
    public bool IsActive { get; set; } = true;

    /// <summary>
    /// When set, the product is a system product excluded from the jewelry catalog.
    /// </summary>
    public SystemProductKind? SystemProductKind { get; set; }

    /// <summary>
    /// Navigation property for product photos.
    /// </summary>
    public ICollection<ProductPhoto> Photos { get; set; } = new List<ProductPhoto>();

    /// <summary>
    /// Validates that the price is greater than zero.
    /// </summary>
    /// <returns>True if price is valid, false otherwise.</returns>
    public bool IsPriceValid() => Price > 0;

    /// <summary>
    /// Validates that the SKU is not empty or whitespace.
    /// </summary>
    /// <returns>True if SKU is valid, false otherwise.</returns>
    public bool IsSkuValid() => !string.IsNullOrWhiteSpace(SKU);
}




