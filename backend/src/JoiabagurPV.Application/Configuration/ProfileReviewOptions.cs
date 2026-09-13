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

    /// <summary>
    /// Seed of the stratified sample the review queue is drawn with.
    /// </summary>
    /// <remarks>
    /// <para>
    /// In configuration rather than generated, because the batch behind a published correction
    /// rate has to be reconstructable by somebody who was not there. The seed is declared in the
    /// implementation report and the same seed always yields the same 180 products in the same
    /// order, which is what lets the sample be defended without storing it.
    /// </para>
    /// <para>
    /// A request may override it, which exists for tests rather than for reviewers: a session
    /// that silently changed seed halfway would produce a figure nobody could reproduce.
    /// </para>
    /// </remarks>
    public string SamplingSeed { get; set; } = "c28-profile-review";

    /// <summary>
    /// How many profiles each evidence stratum contributes to the batch.
    /// </summary>
    /// <remarks>
    /// Sixty is a declared coarse instrument, not a precision claim: at that size the 95 %
    /// interval around a rate of 0,35 is roughly ±0,12 — enough to separate one stratum from
    /// another if the effect is large, which is the hypothesis, and not enough for a fine
    /// interval. Equal quotas across strata of very different sizes are exactly why the reported
    /// total has to be weighted by the corpus and not by the sample.
    /// </remarks>
    public int QuotaPerStratum { get; set; } = 60;
}
