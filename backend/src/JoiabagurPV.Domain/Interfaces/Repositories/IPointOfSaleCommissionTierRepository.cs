using JoiabagurPV.Domain.Entities;

namespace JoiabagurPV.Domain.Interfaces.Repositories;

public interface IPointOfSaleCommissionTierRepository : IRepository<PointOfSaleCommissionTier>
{
    Task<List<PointOfSaleCommissionTier>> GetByPointOfSaleIdAsync(Guid pointOfSaleId);

    Task<List<PointOfSaleCommissionTier>> GetByPointOfSaleIdsAsync(IEnumerable<Guid> pointOfSaleIds);

    Task ReplaceForPointOfSaleAsync(Guid pointOfSaleId, IReadOnlyList<PointOfSaleCommissionTier> tiers);
}
