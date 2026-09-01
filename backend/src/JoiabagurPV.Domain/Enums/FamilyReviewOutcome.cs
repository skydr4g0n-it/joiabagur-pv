namespace JoiabagurPV.Domain.Enums;

/// <summary>
/// What a person decided about one product's relationship with one family.
/// </summary>
/// <remarks>
/// <para>
/// The two values read the same on either side of the membership line, which is the point: a
/// flagged member and an orphan candidate are the same question — <em>does this product belong to
/// that family?</em> — asked about a product that is currently inside and one that is currently
/// outside. Recording both as one verdict is what lets a single row serve as the dismissal list,
/// the review queue's memory, and the per-item approval stamp that batch approval could not give.
/// </para>
/// <para>
/// One-based like <see cref="FamilyOrigin"/>, so that a default-valued zero is never mistaken for
/// a real decision.
/// </para>
/// </remarks>
public enum FamilyReviewOutcome
{
    /// <summary>
    /// The product belongs with the family. On a flagged member this confirms the membership the
    /// vectors questioned; on a candidate it is the judgement that precedes adding it.
    /// </summary>
    Confirmed = 1,

    /// <summary>
    /// The product does not belong with the family. On a candidate this is the dismissal that
    /// keeps it out of every later audit; on a member it records the reason it was removed.
    /// </summary>
    Rejected = 2
}
