namespace JoiabagurPV.Application.DTOs.Products;

/// <summary>
/// One member of a family as declared by the caller.
/// </summary>
/// <remarks>
/// There is no position here on purpose. The order comes from where the member sits in the declared
/// list, which makes gaps and duplicated positions impossible to express rather than merely invalid.
/// </remarks>
public class ProductFamilyMemberRequest
{
    /// <summary>The product joining the family.</summary>
    public Guid ProductId { get; set; }

    /// <summary>What tells this variant from its siblings. Optional while it is unknown.</summary>
    public string? VariantLabel { get; set; }
}

/// <summary>
/// Request to create a family, optionally with its members already declared.
/// </summary>
public class CreateProductFamilyRequest
{
    /// <summary>What the family is called.</summary>
    public string Name { get; set; } = string.Empty;

    /// <summary>Free-form note. Optional.</summary>
    public string? Description { get; set; }

    /// <summary>
    /// Members to create the family with. Empty is valid: a family can be created first and
    /// populated afterwards.
    /// </summary>
    public List<ProductFamilyMemberRequest> Members { get; set; } = [];
}

/// <summary>
/// Request to correct a family's name or description, leaving its members untouched.
/// </summary>
public class UpdateProductFamilyRequest
{
    /// <summary>What the family is called.</summary>
    public string Name { get; set; } = string.Empty;

    /// <summary>Free-form note. Optional.</summary>
    public string? Description { get; set; }
}

/// <summary>
/// Request declaring the complete membership of a family.
/// </summary>
/// <remarks>
/// Declarative, not incremental: whatever is absent from this list stops being a member. An empty
/// list is the way to dissolve a family without deleting it.
/// </remarks>
public class ReplaceFamilyMembersRequest
{
    /// <summary>The complete list of members the family should end up with.</summary>
    public List<ProductFamilyMemberRequest> Members { get; set; } = [];
}

/// <summary>
/// One member of a family as returned to the caller.
/// </summary>
/// <param name="ProductId">The product.</param>
/// <param name="Sku">Its SKU, so the caller need not fetch the product to identify it.</param>
/// <param name="Name">Its name.</param>
/// <param name="VariantLabel">What tells it from its siblings, when known.</param>
/// <param name="SortOrder">Its position within the family, starting at zero.</param>
/// <remarks>
/// Deliberately without photo or price. Building a photo URL needs the storage service and pulls
/// the catalog's role-based visibility into what is otherwise a domain endpoint; authoritative
/// hydration for display belongs to the assisted-sales surface, which already does it.
/// </remarks>
public record ProductFamilyMemberDto(
    Guid ProductId,
    string Sku,
    string Name,
    string? VariantLabel,
    int SortOrder);

/// <summary>
/// A family and its members, in order.
/// </summary>
/// <param name="Id">The family.</param>
/// <param name="Name">What it is called.</param>
/// <param name="Description">Free-form note, when there is one.</param>
/// <param name="Origin">Whether it was created by hand or approved from a suggestion.</param>
/// <param name="Members">Its members, ordered by position.</param>
public record ProductFamilyDto(
    Guid Id,
    string Name,
    string? Description,
    string Origin,
    IReadOnlyList<ProductFamilyMemberDto> Members);

/// <summary>
/// One product that could not join because another family already holds it.
/// </summary>
/// <param name="ProductId">The product that clashes.</param>
/// <param name="FamilyId">The family that already holds it.</param>
/// <param name="FamilyName">That family's name, so the message is readable without a second call.</param>
/// <remarks>
/// Named rather than merely counted. A rejection that only says "conflict" leaves the caller to
/// find the offending product among twenty declared members, which is the difference between an
/// error someone can act on and one they have to investigate.
/// </remarks>
public record ProductFamilyConflictDto(
    Guid ProductId,
    Guid FamilyId,
    string FamilyName);
