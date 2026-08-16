namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// How a batch decides the review status of the profiles it produces.
/// </summary>
public enum ProfileReviewMode
{
    /// <summary>
    /// The hybrid policy decides: sensitive inferred fields send the profile to review.
    /// </summary>
    Routed = 1,

    /// <summary>
    /// Everything is approved and stamped as bulk-approved, so the catalog can be indexed.
    /// </summary>
    /// <remarks>
    /// The declared shortcut of the design, not a loophole. Reviewing every inferred sensitive
    /// field of ~1.000 products is not possible before the delivery date, and indexing only
    /// what a person approved would leave the corpus empty. What keeps this honest is that the
    /// per-field confidence and provenance are still written: afterwards it can be said, with a
    /// number, what share of the corpus nobody looked at and which fields would have needed it.
    /// </remarks>
    AutoBulk = 2
}

/// <summary>
/// Request to enrich a batch of products.
/// </summary>
public class EnrichBatchRequest
{
    /// <summary>Products to enrich. At most <see cref="AiEnrichRequest.MaxBatchSize"/>.</summary>
    public List<Guid> ProductIds { get; set; } = [];

    /// <summary>How to decide the resulting review status. Routed unless stated otherwise.</summary>
    public ProfileReviewMode ReviewMode { get; set; } = ProfileReviewMode.Routed;

    /// <summary>
    /// Re-enrich even when the product inputs have not changed since the stored profile.
    /// </summary>
    /// <remarks>
    /// Off by default, and that default is the guard: without it, a repeated batch pays for
    /// every model call again and overwrites profiles a person had already reviewed.
    /// </remarks>
    public bool Force { get; set; }
}

/// <summary>
/// What happened to one product in a batch.
/// </summary>
/// <param name="ProductId">The product.</param>
/// <param name="ReviewStatus">Status its profile ended in, or null when it was skipped.</param>
/// <param name="FieldsPendingReview">Fields that still need a person, in stable order.</param>
public record EnrichBatchProfileResult(
    Guid ProductId,
    string? ReviewStatus,
    IReadOnlyList<string> FieldsPendingReview);

/// <summary>
/// Outcome of a batch.
/// </summary>
/// <param name="Requested">Products asked for.</param>
/// <param name="Enriched">Products whose profile was written.</param>
/// <param name="SkippedUnchanged">Products skipped because their inputs had not changed.</param>
/// <param name="Failed">Products the service returned no proposal for.</param>
/// <param name="Profiles">Per-product detail.</param>
public record EnrichBatchResponse(
    int Requested,
    int Enriched,
    int SkippedUnchanged,
    int Failed,
    IReadOnlyList<EnrichBatchProfileResult> Profiles);
