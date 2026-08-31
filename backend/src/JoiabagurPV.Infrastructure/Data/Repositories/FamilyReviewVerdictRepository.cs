using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.EntityFrameworkCore;

namespace JoiabagurPV.Infrastructure.Data.Repositories;

/// <summary>
/// Repository implementation for family review verdict operations.
/// </summary>
public class FamilyReviewVerdictRepository
    : Repository<FamilyReviewVerdict>, IFamilyReviewVerdictRepository
{
    private readonly ApplicationDbContext _context;

    public FamilyReviewVerdictRepository(ApplicationDbContext context) : base(context)
    {
        _context = context;
    }

    /// <inheritdoc/>
    public async Task<List<(Guid ProductId, Guid FamilyId)>> GetJudgedPairsAsync()
    {
        var rows = await _context.FamilyReviewVerdicts
            .AsNoTracking()
            .Select(verdict => new { verdict.ProductId, verdict.ProductFamilyId })
            .ToListAsync();

        return rows.Select(row => (row.ProductId, row.ProductFamilyId)).ToList();
    }

    /// <inheritdoc/>
    public async Task<List<FamilyReviewVerdict>> GetByPairsAsync(
        IReadOnlyCollection<(Guid ProductId, Guid FamilyId)> pairs)
    {
        if (pairs.Count == 0)
        {
            return [];
        }

        // Filtered by the two columns separately and then narrowed in memory, rather than by a
        // composite `Contains` over tuples, which PostgreSQL's provider cannot translate. The
        // candidate set is bounded by one batch, so the widening is small and the alternative is
        // one round trip per pair.
        var productIds = pairs.Select(pair => pair.ProductId).Distinct().ToList();
        var familyIds = pairs.Select(pair => pair.FamilyId).Distinct().ToList();

        var candidates = await _context.FamilyReviewVerdicts
            .Where(verdict => productIds.Contains(verdict.ProductId)
                && familyIds.Contains(verdict.ProductFamilyId))
            .ToListAsync();

        var wanted = pairs.ToHashSet();

        return candidates
            .Where(verdict => wanted.Contains((verdict.ProductId, verdict.ProductFamilyId)))
            .ToList();
    }
}
