using JoiabagurPV.Application.DTOs.Ai;
namespace JoiabagurPV.Application.Interfaces;
/// <summary>
/// Auditing the families that exist, and recording what a person decided about them.
/// </summary>
/// <remarks>
/// The counterpart of <see cref="IFamilySuggestionService"/>, and deliberately not part of it.
/// Suggestion reads products that belong to no family and empties itself as batches are approved;
/// the audit reads the families that exist and is a standing signal. They also differ in what they
/// are allowed to do: proposing writes nothing and applying writes families, whereas auditing
/// writes nothing and recording writes judgements.
/// </remarks>
public interface IFamilyAuditService
{
    /// <summary>
    /// Asks the AI service which memberships the vectors do not support, and which unassigned
    /// products look like members.
    /// </summary>
    /// <remarks>
    /// Sends the pairs already judged, read from this side's own store, because the AI service
    /// holds no verdict and must not: a store of judgements beside the index would be state
    /// nothing invalidates.
    /// </remarks>
    Task<AiFamilyAuditResponse> AuditAsync(
        FamilyAuditQueryRequest request,
        Guid userId,
        string role,
        CancellationToken cancellationToken = default);
    /// <summary>
    /// Records a batch of judgements about <c>(product, family)</c> pairs.
    /// </summary>
    /// <remarks>
    /// Idempotent per pair: judging the same pair again is a correction and replaces the standing
    /// record, never adding a second contradictory one.
    /// </remarks>
    Task<RecordFamilyVerdictsResponse> RecordVerdictsAsync(
        RecordFamilyVerdictsRequest request,
        Guid reviewedByUserId);
    /// <summary>
    /// Lists the recorded judgements, each with the membership change it still implies.
    /// </summary>
    /// <remarks>
    /// Without this a decision nobody acted on is invisible: the audit omits judged pairs — which
    /// is what makes a dismissal stick — so a rejected member that was never removed simply stops
    /// appearing anywhere and looks like work already finished.
    /// </remarks>
    Task<List<FamilyVerdictDto>> ListVerdictsAsync();
    /// <summary>
    /// The figures the delivery checklist asks for, computed from the stored judgements.
    /// </summary>
    /// <remarks>
    /// Computed rather than tallied in a screen. An average that lives in component state is gone
    /// when the tab closes, and the first review session lost its timings exactly that way.
    /// </remarks>
    Task<FamilyReviewMetricsDto> GetMetricsAsync();
}
