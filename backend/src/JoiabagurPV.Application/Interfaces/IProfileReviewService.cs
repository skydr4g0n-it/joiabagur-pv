using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>
/// Human review of the AI product profiles, and the figures it produces.
/// </summary>
/// <remarks>
/// <para>
/// A separate service from the one that enriches, because that one's own contract already says
/// so: it exposes a single operation and its documentation assigns reading, approving and
/// measuring to the review capability. Growing a read route onto a write-only surface "just for
/// a counter" is how it ends up with three.
/// </para>
/// <para>
/// <strong>The queue is drawn by origin, not by status.</strong> The indexing feed selects
/// approved profiles, so opening a batch into a pending status would withdraw those documents
/// from the vector index for the length of a review session and force them to be re-embedded on
/// re-approval — degrading the very corpus the demo runs on. Status governs what is indexed;
/// origin governs what these metrics count, and the two are independent by spec.
/// </para>
/// </remarks>
public interface IProfileReviewService
{
    /// <summary>
    /// Draws the stratified batch a reviewer works through. Writes nothing.
    /// </summary>
    /// <param name="request">Stratum filter, page, and the seed and quota overrides.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The batch, with what each stratum holds and what it contributed.</returns>
    Task<ProfileReviewQueueDto> GetQueueAsync(
        ProfileReviewQueueRequest request,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Records one reviewer's judgement on one profile, with the time it took.
    /// </summary>
    /// <param name="request">The values in force after the review, and the measured duration.</param>
    /// <param name="reviewerId">The reviewer, taken from the authenticated caller.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The direction of every reviewed field.</returns>
    /// <exception cref="ArgumentException">The duration is absent, or the profile does not exist.</exception>
    Task<RecordProfileReviewResponse> RecordReviewAsync(
        RecordProfileReviewRequest request,
        Guid reviewerId,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Approves one field across many profiles of one stratum.
    /// </summary>
    /// <param name="request">The field, the stratum, and the profiles.</param>
    /// <param name="reviewerId">The reviewer, taken from the authenticated caller.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>What was marked.</returns>
    /// <exception cref="ArgumentException">
    /// The selection names more than one field or spans more than one stratum. Nothing is
    /// modified: unbounded, this operation is how a batch stops containing any evidence.
    /// </exception>
    Task<BulkApproveProfilesResponse> BulkApproveAsync(
        BulkApproveProfilesRequest request,
        Guid reviewerId,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Lists the rejected profiles, to be asked the inverted question.
    /// </summary>
    /// <param name="page">Page, one-based.</param>
    /// <param name="pageSize">Items per page.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The rejected profiles. They consume no stratum's quota.</returns>
    Task<RejectedProfilesDto> GetRejectedAsync(
        int page,
        int pageSize,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Returns a wrongly rejected profile to approved, recording who decided it.
    /// </summary>
    /// <param name="request">The product, and the duration when the judgement was timed.</param>
    /// <param name="reviewerId">The reviewer, taken from the authenticated caller.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>What the profile now claims.</returns>
    /// <exception cref="ArgumentException">The profile does not exist or is not rejected.</exception>
    Task<RecordProfileReviewResponse> RestoreRejectedAsync(
        RestoreRejectedProfileRequest request,
        Guid reviewerId,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// The correction rate and the review times, computed from the stored columns.
    /// </summary>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The rate per field, per stratum and per direction, and the two time populations.</returns>
    Task<ProfileReviewMetricsDto> GetMetricsAsync(CancellationToken cancellationToken = default);
}
