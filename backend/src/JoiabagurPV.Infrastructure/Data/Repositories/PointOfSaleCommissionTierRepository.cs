using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.EntityFrameworkCore;

namespace JoiabagurPV.Infrastructure.Data.Repositories;

public class PointOfSaleCommissionTierRepository : Repository<PointOfSaleCommissionTier>, IPointOfSaleCommissionTierRepository
{
    private readonly ApplicationDbContext _context;

    public PointOfSaleCommissionTierRepository(ApplicationDbContext context) : base(context)
    {
        _context = context;
    }

    public async Task<List<PointOfSaleCommissionTier>> GetByPointOfSaleIdAsync(Guid pointOfSaleId)
    {
        return await _context.PointOfSaleCommissionTiers
            .Where(t => t.PointOfSaleId == pointOfSaleId)
            .OrderBy(t => t.MinAmountInclusive)
            .ToListAsync();
    }

    public async Task<List<PointOfSaleCommissionTier>> GetByPointOfSaleIdsAsync(IEnumerable<Guid> pointOfSaleIds)
    {
        var ids = pointOfSaleIds.Distinct().ToList();
        if (ids.Count == 0)
            return new List<PointOfSaleCommissionTier>();

        return await _context.PointOfSaleCommissionTiers
            .Where(t => ids.Contains(t.PointOfSaleId))
            .OrderBy(t => t.PointOfSaleId)
            .ThenBy(t => t.MinAmountInclusive)
            .ToListAsync();
    }

    public async Task ReplaceForPointOfSaleAsync(Guid pointOfSaleId, IReadOnlyList<PointOfSaleCommissionTier> tiers)
    {
        var existing = await _context.PointOfSaleCommissionTiers
            .Where(t => t.PointOfSaleId == pointOfSaleId)
            .ToListAsync();

        _context.PointOfSaleCommissionTiers.RemoveRange(existing);

        if (tiers.Count > 0)
            await _context.PointOfSaleCommissionTiers.AddRangeAsync(tiers);
    }
}
