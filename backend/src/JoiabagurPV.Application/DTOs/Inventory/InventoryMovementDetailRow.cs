using JoiabagurPV.Domain.Enums;

namespace JoiabagurPV.Application.DTOs.Inventory;

public class InventoryMovementDetailRow
{
    public Guid Id { get; set; }
    public Guid InventoryId { get; set; }
    public Guid ProductId { get; set; }
    public string ProductName { get; set; } = string.Empty;
    public string ProductSku { get; set; } = string.Empty;
    public Guid PointOfSaleId { get; set; }
    public string PointOfSaleName { get; set; } = string.Empty;
    public MovementType MovementType { get; set; }
    public string MovementTypeName => MovementType.ToString();
    public int QuantityChange { get; set; }
    public int QuantityBefore { get; set; }
    public int QuantityAfter { get; set; }
    public Guid UserId { get; set; }
    public string UserName { get; set; } = string.Empty;
    public string? Reason { get; set; }
    public DateTime MovementDate { get; set; }
    public Guid? SaleId { get; set; }
    public Guid? ReturnId { get; set; }
}
