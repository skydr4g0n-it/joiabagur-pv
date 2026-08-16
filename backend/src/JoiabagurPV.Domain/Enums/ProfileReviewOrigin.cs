namespace JoiabagurPV.Domain.Enums;

/// <summary>
/// Who put an AI profile in its current <see cref="ProfileReviewStatus"/>.
/// </summary>
/// <remarks>
/// This exists so the project can state, with a number rather than an impression, what share of
/// the catalog a person actually looked at. The design accepts up front that reviewing every
/// inferred sensitive field of ~1.000 products is not possible before the delivery date, and
/// resolves it with two declared paths instead of one silent one: a reviewed batch, and a bulk
/// one. Both are indexable; only one counts as human review, and telling them apart has to be a
/// property of the data, not a note in a document.
/// </remarks>
public enum ProfileReviewOrigin
{
    /// <summary>
    /// Produced by batch enrichment without anyone looking at it.
    /// </summary>
    AutoBulk = 1,

    /// <summary>
    /// A person reviewed this profile and left it in its current status.
    /// </summary>
    Human = 2
}
