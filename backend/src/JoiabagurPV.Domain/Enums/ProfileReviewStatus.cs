namespace JoiabagurPV.Domain.Enums;

/// <summary>
/// Where an AI profile stands in its review lifecycle.
/// </summary>
/// <remarks>
/// Deliberately says nothing about <em>who</em> put the profile in this state — that is
/// <see cref="ProfileReviewOrigin"/>, and keeping the two apart is what lets the indexing feed
/// select by status alone while the human-review metrics select by origin alone. A single
/// combined value would make one of those two selections quietly wrong.
/// </remarks>
public enum ProfileReviewStatus
{
    /// <summary>
    /// At least one field needs a person to look at it. Not a candidate for indexing.
    /// </summary>
    Pending = 1,

    /// <summary>
    /// No field needs review, or a person approved it. Candidate for indexing.
    /// </summary>
    Approved = 2,

    /// <summary>
    /// A person discarded the proposal.
    /// </summary>
    Rejected = 3
}
