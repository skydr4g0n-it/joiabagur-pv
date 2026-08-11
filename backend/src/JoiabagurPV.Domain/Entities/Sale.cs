namespace JoiabagurPV.Domain.Entities;

/// <summary>
/// Represents a sale transaction in the system.
/// Provides complete audit trail for sales with automatic inventory updates.
/// </summary>
public class Sale : BaseEntity
{
    /// <summary>
    /// The product being sold.
    /// </summary>
    public Guid ProductId { get; set; }

    /// <summary>
    /// The point of sale where the transaction occurred.
    /// </summary>
    public Guid PointOfSaleId { get; set; }

    /// <summary>
    /// The user (operator) who registered the sale.
    /// </summary>
    public Guid UserId { get; set; }

    /// <summary>
    /// The payment method used for the transaction.
    /// </summary>
    public Guid PaymentMethodId { get; set; }

    /// <summary>
    /// Price snapshot at the time of sale (frozen from Product.Price).
    /// Preserves price history even if product price changes later.
    /// </summary>
    public decimal Price { get; set; }

    /// <summary>
    /// Quantity of units sold. Must be greater than zero.
    /// </summary>
    public int Quantity { get; set; }

    /// <summary>
    /// Optional notes or comments about the sale.
    /// Max 500 characters.
    /// </summary>
    public string? Notes { get; set; }

    /// <summary>
    /// Whether the sale price was manually overridden by the operator.
    /// </summary>
    public bool PriceWasOverridden { get; set; } = false;

    /// <summary>
    /// The official product price at the time of sale, stored when a manual override was applied.
    /// Null when the sale used the official product price.
    /// </summary>
    public decimal? OriginalProductPrice { get; set; }

    /// <summary>
    /// Groups sales created together in a single bulk checkout operation.
    /// Null for sales created individually.
    /// </summary>
    public Guid? BulkOperationId { get; set; }

    /// <summary>
    /// The assisted search this sale originated from, when it originated from one.
    /// </summary>
    /// <remarks>
    /// Attribution lives here rather than on the search event because the sale can declare its
    /// origin in the same insert that creates it: no follow-up call, nothing to lose between the
    /// selection and the till, and a bulk checkout attributes each line to its own search.
    ///
    /// An unknown identifier must degrade to null rather than propagate: a stale value from the
    /// client would otherwise violate the foreign key and stop the operator from selling. This
    /// change adds the column but no write path — the rule is specified for whoever wires it.
    /// </remarks>
    public Guid? SearchEventId { get; set; }

    /// <summary>
    /// When the sale occurred.
    /// </summary>
    public DateTime SaleDate { get; set; }

    // Navigation properties
    
    /// <summary>
    /// Navigation property for the sold product.
    /// </summary>
    public virtual Product Product { get; set; } = null!;

    /// <summary>
    /// Navigation property for the point of sale.
    /// </summary>
    public virtual PointOfSale PointOfSale { get; set; } = null!;

    /// <summary>
    /// Navigation property for the operator who made the sale.
    /// </summary>
    public virtual User User { get; set; } = null!;

    /// <summary>
    /// Navigation property for the payment method used.
    /// </summary>
    public virtual PaymentMethod PaymentMethod { get; set; } = null!;

    /// <summary>
    /// Navigation property for the optional photo attached to this sale.
    /// </summary>
    public virtual SalePhoto? Photo { get; set; }

    /// <summary>
    /// Navigation property for the corresponding inventory movement.
    /// </summary>
    public virtual InventoryMovement? InventoryMovement { get; set; }

    /// <summary>
    /// Navigation property for returns associated with this sale (many-to-many through ReturnSale).
    /// </summary>
    public virtual ICollection<ReturnSale> ReturnSales { get; set; } = new List<ReturnSale>();

    /// <summary>
    /// Calculates the total amount for this sale.
    /// </summary>
    /// <returns>Total amount (Price * Quantity).</returns>
    public decimal GetTotal() => Price * Quantity;

    /// <summary>
    /// Validates that the quantity is greater than zero.
    /// </summary>
    /// <returns>True if quantity is valid, false otherwise.</returns>
    public bool IsQuantityValid() => Quantity > 0;

    /// <summary>
    /// Validates that the price is greater than zero.
    /// </summary>
    /// <returns>True if price is valid, false otherwise.</returns>
    public bool IsPriceValid() => Price > 0;
}
