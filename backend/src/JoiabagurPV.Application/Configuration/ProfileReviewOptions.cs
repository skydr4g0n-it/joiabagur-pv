namespace JoiabagurPV.Application.Configuration;

/// <summary>
/// Thresholds governing the hybrid per-field review policy.
/// Bound from the "ProfileReview" section and validated at application start.
/// </summary>
/// <remarks>
/// In configuration rather than as constants for one concrete reason: these numbers are meant to
/// be recalibrated against the evaluation golden set once it exists, and a threshold compiled
/// into the code is a threshold nobody recalibrates. The values below are a documented starting
/// point, not a finding.
/// </remarks>
public class ProfileReviewOptions
{
    /// <summary>Configuration section name.</summary>
    public const string SectionName = "ProfileReview";

    /// <summary>
    /// Confidence at or above which commercial tags — colour, style, occasion — are approved
    /// without a person looking at them.
    /// </summary>
    /// <remarks>
    /// Applies only to tags because their failure mode is cheap: a wrongly tagged piece ranks
    /// slightly worse. The sensitive attributes are never auto-approved on confidence alone,
    /// however high, because their failure mode is an operator telling a customer that a steel
    /// ring is silver.
    /// </remarks>
    public double TagAutoApproveThreshold { get; set; } = 0.80;

    /// <summary>
    /// Confidence below which any field is sent to review, whatever its kind.
    /// </summary>
    /// <remarks>
    /// The floor beneath the rule above. A rule-sourced field is exempt from review by
    /// provenance, so this only ever bites on inferred values.
    /// </remarks>
    public double MinimumFieldConfidence { get; set; } = 0.50;
}
