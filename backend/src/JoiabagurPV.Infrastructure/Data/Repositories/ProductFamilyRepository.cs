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
}
