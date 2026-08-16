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
}
