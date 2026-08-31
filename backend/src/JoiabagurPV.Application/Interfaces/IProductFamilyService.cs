using JoiabagurPV.Application.DTOs.Products;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>
/// Manages product families and their membership.
/// </summary>
public interface IProductFamilyService
{
    /// <summary>
    /// Creates a family, optionally with its members already declared.
    /// </summary>
    /// <exception cref="Exceptions.ProductFamilyConflictException">
    /// A declared product already belongs to another family.
    /// </exception>
    Task<ProductFamilyDto> CreateAsync(CreateProductFamilyRequest request);

    /// <summary>
    /// Creates a family from an approved suggestion, recording who approved it and when.
    /// </summary>
    /// <param name="request">The family and its declared members, as accepted.</param>
    /// <param name="approvedByUserId">Administrator who approved the batch.</param>
    /// <remarks>
    /// A separate method rather than a flag on <see cref="CreateAsync"/>: putting the origin in
    /// the request would let the manual endpoint claim an AI approval that never happened, and
    /// the whole point of the column is that the two paths stay distinguishable afterwards.
    /// Everything else — the single-family guard, the position and label rules, and the
    /// <c>Product.UpdatedAt</c> stamping the indexing feed reads — is shared with the manual path
    /// on purpose: a second write path would be a second set of invariants to keep in step.
    /// </remarks>
    /// <exception cref="Exceptions.ProductFamilyConflictException">
    /// A declared product already belongs to another family.
    /// </exception>
    Task<ProductFamilyDto> CreateFromSuggestionAsync(
        CreateProductFamilyRequest request,
        Guid approvedByUserId);

    /// <summary>
    /// Gets a family with its members, ordered. Null when no family has that identifier.
    /// </summary>
    Task<ProductFamilyDto?> GetByIdAsync(Guid id);

    /// <summary>
    /// Corrects a family's name and description, leaving its members untouched.
    /// </summary>
    /// <exception cref="KeyNotFoundException">No family has that identifier.</exception>
    Task<ProductFamilyDto> UpdateAsync(Guid id, UpdateProductFamilyRequest request);

    /// <summary>
    /// Declares the complete membership of a family.
    /// </summary>
    /// <remarks>
    /// Whatever is absent from the declaration stops being a member; an empty declaration dissolves
    /// the family without deleting it. Declaring the list a family already has writes nothing.
    /// </remarks>
    /// <exception cref="KeyNotFoundException">No family has that identifier.</exception>
    /// <exception cref="Exceptions.ProductFamilyConflictException">
    /// A declared product already belongs to another family.
    /// </exception>
    Task<ProductFamilyDto> ReplaceMembersAsync(Guid id, ReplaceFamilyMembersRequest request);

    /// <summary>
    /// Gets the family a product belongs to.
    /// </summary>
    /// <remarks>
    /// Returns null when the product exists and belongs to no family, and throws when the product
    /// itself does not exist. The two are different answers — one in seven products is an orphan by
    /// design in the generated catalogue — and collapsing them would leave callers unable to tell a
    /// quality incidence from a bad identifier.
    /// </remarks>
    /// <exception cref="KeyNotFoundException">No product has that identifier.</exception>
    Task<ProductFamilyDto?> GetByProductIdAsync(Guid productId);

    /// <summary>
    /// Lists families matching the query, with the counts a review screen needs to triage them.
    /// </summary>
    Task<PaginatedResultDto<ProductFamilyListItemDto>> ListAsync(ProductFamilyQueryParameters query);

    /// <summary>
    /// Dissolves a family: it ceases to exist and its members belong to nothing.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Not the same as declaring an empty membership. An empty family is a legitimate state for one
    /// being built and meaningless for one that was wrong, and leaving the shell behind puts a row
    /// in every listing that a reviewer has to decide about again.
    /// </para>
    /// <para>
    /// Stamps the departing products, without which an incremental index pull never emits them and
    /// their documents keep a family identifier pointing at a family that is gone — silently. The
    /// membership rows themselves go by cascade, and so do any verdicts recorded against the family.
    /// </para>
    /// </remarks>
    /// <returns><c>false</c> when no family carries that identifier.</returns>
    Task<bool> DeleteAsync(Guid id);
}
