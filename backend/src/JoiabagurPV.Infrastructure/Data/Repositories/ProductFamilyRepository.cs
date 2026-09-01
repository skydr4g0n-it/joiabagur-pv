using JoiabagurPV.Domain.Common;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.EntityFrameworkCore;

namespace JoiabagurPV.Infrastructure.Data.Repositories;

/// <summary>
/// Repository implementation for ProductFamily entity operations.
/// </summary>
public class ProductFamilyRepository : Repository<ProductFamily>, IProductFamilyRepository
{
    private readonly ApplicationDbContext _context;

    public ProductFamilyRepository(ApplicationDbContext context) : base(context)
    {
        _context = context;
    }

    /// <inheritdoc/>
    /// <remarks>
    /// Ordered in the <c>Include</c> rather than afterwards. Sorting the loaded collection and
    /// assigning it back would replace the navigation property of a <em>tracked</em> entity, which
    /// silently detaches the change tracker from the members it is holding: the next write then
    /// tries to update rows it no longer has and fails with a concurrency error that says nothing
    /// about the real cause.
    /// </remarks>
    public async Task<ProductFamily?> GetWithMembersAsync(Guid id) =>
        await _context.ProductFamilies
            .Include(f => f.Members.OrderBy(m => m.SortOrder))
            .FirstOrDefaultAsync(f => f.Id == id);

    /// <inheritdoc/>
    public async Task<ProductFamily?> GetByProductIdAsync(Guid productId)
    {
        var familyId = await _context.ProductFamilyMembers
            .Where(m => m.ProductId == productId)
            .Select(m => (Guid?)m.ProductFamilyId)
            .FirstOrDefaultAsync();

        return familyId is null ? null : await GetWithMembersAsync(familyId.Value);
    }

    /// <inheritdoc/>
    public async Task<List<ProductFamilyMember>> GetMembershipsInOtherFamiliesAsync(
        IEnumerable<Guid> productIds,
        Guid excludingFamilyId)
    {
        var ids = productIds.Distinct().ToList();

        return await _context.ProductFamilyMembers
            .Include(m => m.Family)
            .Where(m => ids.Contains(m.ProductId) && m.ProductFamilyId != excludingFamilyId)
            .ToListAsync();
    }

    /// <inheritdoc/>
    public Task RemoveMembersAsync(IEnumerable<ProductFamilyMember> members)
    {
        _context.ProductFamilyMembers.RemoveRange(members);
        return Task.CompletedTask;
    }

    /// <inheritdoc/>
    public Task AddMembersAsync(IEnumerable<ProductFamilyMember> members)
    {
        _context.ProductFamilyMembers.AddRange(members);
        return Task.CompletedTask;
    }

    /// <inheritdoc/>
    public async Task StampUpdatedAtAsync(Guid familyId)
    {
        var now = DateTime.UtcNow;
        await _context.ProductFamilies
            .Where(family => family.Id == familyId)
            .ExecuteUpdateAsync(setters => setters.SetProperty(family => family.UpdatedAt, now));
    }

    /// <inheritdoc/>
    public async Task<(List<ProductFamilySummary> Items, int TotalCount)> ListAsync(
        ProductFamilyQuery query)
    {
        var families = _context.ProductFamilies.AsNoTracking();

        if (query.Origin is not null)
        {
            families = families.Where(family => family.Origin == query.Origin);
        }

        if (!string.IsNullOrWhiteSpace(query.PieceType))
        {
            // Resolved through the members' AI profiles: the piece type is an enriched attribute of
            // the product, not a column on the family. `Any` rather than `All` because a family
            // whose enrichment is incomplete should still be findable by the type its other
            // members carry — the alternative hides exactly the families worth reviewing.
            var pieceType = query.PieceType.Trim();
            families = families.Where(family => _context.ProductFamilyMembers
                .Where(member => member.ProductFamilyId == family.Id)
                .Any(member => _context.ProductAiProfiles
                    .Any(profile => profile.ProductId == member.ProductId
                        && profile.PieceType == pieceType)));
        }

        if (query.HasRejectedMembers == true)
        {
            families = families.Where(family => _context.FamilyReviewVerdicts
                .Any(verdict => verdict.ProductFamilyId == family.Id
                    && verdict.Outcome == FamilyReviewOutcome.Rejected));
        }
        else if (query.HasRejectedMembers == false)
        {
            families = families.Where(family => !_context.FamilyReviewVerdicts
                .Any(verdict => verdict.ProductFamilyId == family.Id
                    && verdict.Outcome == FamilyReviewOutcome.Rejected));
        }

        var totalCount = await families.CountAsync();

        var items = await families
            // Newest approvals first, then by name. A stable secondary key matters here: the 156
            // families of an assisted batch share an approval instant to the second, and without
            // it paging would return the same family on two pages and skip another.
            .OrderByDescending(family => family.ApprovedAt)
            .ThenBy(family => family.Name)
            .ThenBy(family => family.Id)
            .Skip((query.Page - 1) * query.PageSize)
            .Take(query.PageSize)
            .Select(family => new ProductFamilySummary(
                family.Id,
                family.Name,
                family.Description,
                family.Origin,
                _context.ProductFamilyMembers.Count(m => m.ProductFamilyId == family.Id),
                family.ApprovedByUserId,
                family.ApprovedAt,
                _context.FamilyReviewVerdicts.Count(v => v.ProductFamilyId == family.Id),
                _context.FamilyReviewVerdicts.Count(v => v.ProductFamilyId == family.Id
                    && v.Outcome == FamilyReviewOutcome.Rejected)))
            .ToListAsync();

        return (items, totalCount);
    }

    /// <inheritdoc/>
    public async Task<List<Guid>> GetMemberProductIdsAsync(Guid familyId) =>
        await _context.ProductFamilyMembers
            .AsNoTracking()
            .Where(member => member.ProductFamilyId == familyId)
            .Select(member => member.ProductId)
            .ToListAsync();
}
