using JoiabagurPV.Application.DTOs.PointOfSales;

namespace JoiabagurPV.Application.Interfaces;

public interface IPointOfSaleCommissionTierService
{
    Task<List<CommissionTierDto>> GetTiersAsync(Guid pointOfSaleId);
    Task<List<CommissionTierDto>> ReplaceTiersAsync(Guid pointOfSaleId, ReplaceCommissionTiersRequest request);
}
