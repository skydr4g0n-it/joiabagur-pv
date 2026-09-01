using JoiabagurPV.Domain.Common;
using JoiabagurPV.Domain.Entities;

namespace JoiabagurPV.Domain.Interfaces.Repositories;

/// <summary>
/// Repository interface for ProductFamily entity operations.
/// </summary>
public interface IProductFamilyRepository : IRepository<ProductFamily>
{
    /// <summary>
    /// Gets a family with its members loaded, ordered by position within the family.
    /// </summary>
    /// <param name="id">The family ID.</param>
    /// <returns>The family with its members, or null if not found.</returns>
    Task<ProductFamily?> GetWithMembersAsync(Guid id);

    /// <summary>
    /// Gets the family a product belongs to, with every sibling loaded and ordered.
    /// </summary>
    /// <param name="productId">The product ID.</param>
    /// <returns>The family, or null when the product belongs to none.</returns>
    Task<ProductFamily?> GetByProductIdAsync(Guid productId);

    /// <summary>
    /// Finds, among the given products, those that already belong to a family other than
    /// <paramref name="excludingFamilyId"/>.
    /// </summary>
    /// <remarks>
    /// Exists so the conflict can be reported usefully. The unique index is what actually
    /// guarantees single membership; this read is what lets the service say <em>which</em> products
    /// clash and <em>which</em> family holds each of them, instead of returning a bare rejection
    /// that leaves the caller to find the offending row among twenty.
    /// </remarks>
    /// <param name="productIds">The products about to be declared as members.</param>
    /// <param name="excludingFamilyId">The family being written, whose own members are not conflicts.</param>
    /// <returns>The conflicting memberships, with their family loaded.</returns>
    Task<List<ProductFamilyMember>> GetMembershipsInOtherFamiliesAsync(
        IEnumerable<Guid> productIds,
        Guid excludingFamilyId);

    /// <summary>
    /// Marks the given memberships for deletion.
    /// </summary>
    Task RemoveMembersAsync(IEnumerable<ProductFamilyMember> members);

    /// <summary>
    /// Marks the given memberships for insertion.
    /// </summary>
    /// <remarks>
    /// Explicit on purpose, rather than relying on adding them to a tracked family's collection.
    /// <see cref="BaseEntity"/> assigns the identifier in its constructor, so a membership reached
    /// through a navigation property arrives at the change tracker with a non-empty key and is taken
    /// for an existing row: the write then goes out as an update against a row that does not exist,
    /// and fails with a concurrency error that names neither the entity nor the cause.
    /// </remarks>
    Task AddMembersAsync(IEnumerable<ProductFamilyMember> members);

    /// <summary>
    /// Writes <c>UpdatedAt</c> on a family in SQL so a metadata rename moves the catalog
    /// watermark without rewriting membership rows.
    /// </summary>
    Task StampUpdatedAtAsync(Guid familyId);

    /// <summary>
    /// Lists families matching the query, with the total that matched before paging.
    /// </summary>
    /// <remarks>
    /// Retrieval by identifier used to be the only read here, which serves a product's sibling
    /// list and is useless for review: somebody working through the catalogue's families has no
    /// identifier to start from, and no other operation produces the set.
    /// </remarks>
    Task<(List<ProductFamilySummary> Items, int TotalCount)> ListAsync(ProductFamilyQuery query);

    /// <summary>
    /// Returns the products that belong to a family, so a caller can stamp them before it is gone.
    /// </summary>
    /// <remarks>
    /// Read <em>before</em> the delete, never after: once the family is removed the membership
    /// rows go with it by cascade, and the products that left become unreachable. Without the
    /// stamp an incremental index pull never emits them, so their documents keep a family
    /// identifier pointing at a family that no longer exists — with no error anywhere.
    /// </remarks>
    Task<List<Guid>> GetMemberProductIdsAsync(Guid familyId);
}
