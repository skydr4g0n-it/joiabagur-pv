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

// ──────────────────────────────────────────────────────────────────────────────────────────────
// C18b — enumerating and dissolving families, which the review screen cannot work without
// ──────────────────────────────────────────────────────────────────────────────────────────────

/// <summary>
/// Narrowing and paging for the family listing.
/// </summary>
/// <remarks>
/// Retrieval by identifier was the only read this controller offered, which is enough for a
/// product's sibling list and useless for review: a person working through the catalogue's
/// families has no identifier to start from, and no other operation produces the set.
/// </remarks>
public class ProductFamilyQueryParameters
{
    /// <summary>Largest page this endpoint will serve, matching the rest of the catalogue.</summary>
    public const int MaxPageSize = 50;

    /// <summary>Page number, 1-based.</summary>
    public int Page { get; set; } = 1;

    /// <summary>Items per page. Capped at <see cref="MaxPageSize"/>.</summary>
    public int PageSize { get; set; } = MaxPageSize;

    /// <summary>Restrict to families of one origin: <c>Manual</c> or <c>AiApproved</c>.</summary>
    public string? Origin { get; set; }

    /// <summary>Restrict to families whose members share one closed-vocabulary piece type.</summary>
    /// <remarks>
    /// Resolved through the AI profiles of the members, because the piece type is an enriched
    /// attribute of the product and not a column on the family. A family whose members carry no
    /// piece type simply never matches.
    /// </remarks>
    public string? PieceType { get; set; }

    /// <summary>Restrict to families holding at least one product judged and rejected.</summary>
    /// <remarks>
    /// Named after what the reviewer is looking for rather than after the audit: the audit's
    /// flags are recomputed on demand and live in no table, so the durable trace of "somebody
    /// looked at this family and found something wrong" is a rejected verdict against one of its
    /// members.
    /// </remarks>
    public bool? HasRejectedMembers { get; set; }
}

/// <summary>
/// A family as it appears in a listing: enough to decide, without loading every member.
/// </summary>
/// <param name="Id">The family.</param>
/// <param name="Name">What it is called.</param>
/// <param name="Description">Free-form note, when there is one.</param>
/// <param name="Origin">Whether it was created by hand or approved from a suggestion.</param>
/// <param name="MemberCount">How many products it holds.</param>
/// <param name="ApprovedByUserId">Who approved it, when it came from a suggestion.</param>
/// <param name="ApprovedAt">When that approval happened.</param>
/// <param name="ReviewedMemberCount">How many of its members carry a human verdict.</param>
/// <param name="RejectedMemberCount">How many of those verdicts rejected the membership.</param>
/// <remarks>
/// The two review counts are what make the listing a work queue rather than a catalogue dump:
/// without them a reviewer cannot tell a family nobody has opened from one already worked through,
/// and the 156 families this catalogue holds all look identical on every other column.
/// </remarks>
public record ProductFamilyListItemDto(
    Guid Id,
    string Name,
    string? Description,
    string Origin,
    int MemberCount,
    Guid? ApprovedByUserId,
    DateTime? ApprovedAt,
    int ReviewedMemberCount,
    int RejectedMemberCount);
