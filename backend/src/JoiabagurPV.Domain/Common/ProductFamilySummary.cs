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

/// <summary>
/// A recorded judgement together with what the catalog would have to change to honour it.
/// </summary>
/// <param name="ProductId">The product judged.</param>
/// <param name="Sku">Its SKU.</param>
/// <param name="ProductName">Its name.</param>
/// <param name="FamilyId">The family judged against.</param>
/// <param name="FamilyName">That family's name.</param>
/// <param name="Outcome">What the reviewer decided.</param>
/// <param name="IsCurrentMember">Whether the product belongs to that family right now.</param>
/// <param name="MarginAtReview">The margin the audit reported when the decision was made.</param>
/// <param name="ReviewedAt">When it was decided.</param>
/// <remarks>
/// <para>
/// <strong>The judgement and the change are different things, and this is where that shows.</strong>
/// Recording a verdict says what a person concluded; it does not move a membership. A rejected
/// member is still in its family and a confirmed candidate still belongs to nothing until somebody
/// declares the new membership — through the family service, which is the only path that keeps the
/// index watermark coherent.
/// </para>
/// <para>
/// <see cref="IsCurrentMember"/> combined with <see cref="Outcome"/> is what tells the two apart: a
/// rejected current member is a removal waiting to happen, a confirmed non-member is an addition,
/// and the other two combinations are judgements the catalog already agrees with.
/// </para>
/// </remarks>
public record FamilyVerdictSummary(
    Guid ProductId,
    string Sku,
    string ProductName,
    Guid FamilyId,
    string FamilyName,
    FamilyReviewOutcome Outcome,
    bool IsCurrentMember,
    double? MarginAtReview,
    DateTime ReviewedAt);
