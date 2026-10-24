namespace JoiabagurPV.Domain.Entities;

/// <summary>
/// Represents a point of sale location in the system.
/// </summary>
public class PointOfSale : BaseEntity
{
    /// <summary>
    /// Display name of the point of sale.
    /// </summary>
    public required string Name { get; set; }

    /// <summary>
    /// Unique code identifier for the point of sale.
    /// </summary>
    public required string Code { get; set; }

    /// <summary>
    /// Physical address of the point of sale.
    /// </summary>
    public string? Address { get; set; }

    /// <summary>
    /// Contact phone number.
    /// </summary>
    public string? Phone { get; set; }

    /// <summary>
    /// Contact email address.
    /// </summary>
    public string? Email { get; set; }

    /// <summary>
    /// Whether the point of sale is currently active.
    /// </summary>
    public bool IsActive { get; set; } = true;

    /// <summary>
    /// Whether operators can manually edit sale prices at this point of sale.
    /// Only configurable by administrators.
    /// </summary>
    public bool AllowManualPriceEdit { get; set; } = false;

    /// <summary>
    /// Navigation property for operator assignments.
    /// </summary>
    public ICollection<UserPointOfSale> OperatorAssignments { get; set; } = new List<UserPointOfSale>();

    /// <summary>
    /// Navigation property for payment method assignments.
    /// </summary>
    public ICollection<PointOfSalePaymentMethod> PaymentMethodAssignments { get; set; } = new List<PointOfSalePaymentMethod>();

    /// <summary>
    /// Annual sales commission tiers for this point of sale.
    /// </summary>
    public ICollection<PointOfSaleCommissionTier> CommissionTiers { get; set; } = new List<PointOfSaleCommissionTier>();
}
