using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>
/// Records the query-to-selection cycle of assisted search.
/// </summary>
/// <remarks>
/// Two write paths, split by what each author can actually observe. The search half is written
/// here by the backend, which is the only place that knows the result origin, the trace
/// identifier, the real retrieval latency and the list that was truly returned. The selection
/// half arrives from the browser, which is the only place that knows what the operator picked.
///
/// There is no read path. Search events are analysed with direct SQL, outside the application.
/// </remarks>
public interface IProductSearchEventService
{
    /// <summary>
    /// Records a search that has just been served, and returns the identifier of the stored
    /// event so the caller can hand it to the client.
    /// </summary>
    /// <returns>
    /// The identifier of the persisted event, or <c>null</c> when it could not be persisted.
    /// </returns>
    /// <remarks>
    /// <strong>This method never throws.</strong> A telemetry problem must not be able to
    /// surface as a failed search, and making that a guarantee of the callee rather than an
    /// obligation on every caller is the only way it survives. Callers only have to tolerate a
    /// null.
    /// </remarks>
    Task<Guid?> RecordSearchAsync(RecordSearchRequest request);

    /// <summary>
    /// Records the product the operator selected on a previously stored search event.
    /// </summary>
    /// <param name="searchEventId">The event the selection belongs to.</param>
    /// <param name="userId">Who is recording it. Must own the event.</param>
    /// <param name="selectedProductId">The product the operator picked.</param>
    /// <remarks>
    /// The rank is derived here from the stored result list and is deliberately not accepted
    /// from the caller: the KPI asks about the quality of retrieval, and a rank reported by the
    /// interface would answer a different question. Repeated calls keep the last selection.
    /// </remarks>
    Task<SelectionOutcome> RecordSelectionAsync(Guid searchEventId, Guid userId, Guid selectedProductId);
}
