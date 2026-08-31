using JoiabagurPV.Domain.Enums;

namespace JoiabagurPV.Domain.Common;

/// <summary>
/// A family reduced to what a listing needs, projected in SQL rather than loaded.
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
/// <para>
/// A domain shape rather than the application's DTO because this crosses the repository boundary,
/// and the domain project references nothing: a DTO here would invert the layering the whole
/// solution is built on. The service maps it, which is one short projection and no duplication of
/// meaning.
/// </para>
/// <para>
/// The counts are computed in the query. Hydrating 156 families with their 486 members in order to
/// count them would pull the whole catalogue across the wire for two integers per row, and the
/// listing exists precisely so a reviewer can scan the set.
/// </para>
/// </remarks>
public record ProductFamilySummary(
    Guid Id,
    string Name,
    string? Description,
    FamilyOrigin Origin,
    int MemberCount,
    Guid? ApprovedByUserId,
    DateTime? ApprovedAt,
    int ReviewedMemberCount,
    int RejectedMemberCount);

/// <summary>
/// Narrowing and paging for a family listing, in domain terms.
/// </summary>
/// <remarks>
/// Mirrors the application's query parameters. The duplication is deliberate and small: the
/// alternative is a repository signature that reaches up a layer, and the two shapes are allowed
/// to diverge — the API may grow a sort option the storage does not care about.
/// </remarks>
public record ProductFamilyQuery(
    int Page,
    int PageSize,
    FamilyOrigin? Origin,
    string? PieceType,
    bool? HasRejectedMembers);
