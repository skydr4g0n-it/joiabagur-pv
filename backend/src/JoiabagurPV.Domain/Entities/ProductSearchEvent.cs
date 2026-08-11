using JoiabagurPV.Domain.Enums;

namespace JoiabagurPV.Domain.Entities;

/// <summary>
/// One executed assisted search and, if it happened, the selection the operator made on it.
/// </summary>
/// <remarks>
/// The row is written in two steps by two different authors, split by what each one can
/// actually observe. The backend writes everything except the three selection columns while
/// it serves the search: the origin of the results, the trace identifier, the real retrieval
/// latency and the list that was truly returned exist only there. The browser reports the
/// selection, which is the only thing it knows first-hand.
///
/// The entity declares no navigation properties on purpose. This capability exposes no read
/// path, and a model that offers no traversal is a model nobody accidentally reads through.
/// </remarks>
public class ProductSearchEvent : BaseEntity
{
    /// <summary>
    /// Operator who ran the search. Taken from the validated call scope, never from a request body.
    /// </summary>
    public Guid UserId { get; set; }

    /// <summary>
    /// Point of sale the search was scoped to.
    /// </summary>
    public Guid PointOfSaleId { get; set; }

    /// <summary>
    /// Groups every query of one search episode, so a reformulation can be told apart from an
    /// abandonment: a row with no selection that has later siblings in the same episode is a
    /// reformulation; one without siblings is a genuine abandonment.
    /// </summary>
    public Guid SearchSessionId { get; set; }

    /// <summary>
    /// The natural-language query the operator typed. Bounded to the length the frozen
    /// <c>ai-service/openapi.json</c> contract declares for the query field.
    /// </summary>
    public required string SearchText { get; set; }

    /// <summary>
    /// The filters actually sent to retrieval, as a JSON document. Not the UI state, which may
    /// differ. An empty object when no filter was applied — never null, so queries need no
    /// null handling.
    /// </summary>
    public required string FiltersJson { get; set; }

    /// <summary>
    /// The result list as displayed, in display order, projected to what cannot be recovered
    /// later by joining the catalog. An empty array when nothing was found.
    /// </summary>
    public required string ResultsJson { get; set; }

    /// <summary>
    /// How many results were actually displayed, independently of how many were stored.
    /// Answers the most-used KPI without parsing the JSON document, and makes truncation
    /// detectable by comparing it against the stored array length.
    /// </summary>
    public int ResultsCount { get; set; }

    /// <summary>
    /// Whether the results came from the AI service or from the degraded lexical path.
    /// </summary>
    public SearchOrigin SearchOrigin { get; set; }

    /// <summary>
    /// Correlation identifier of the .NET to Python hop, so a row can be tied back to the logs
    /// of both services.
    /// </summary>
    public string? TraceId { get; set; }

    /// <summary>
    /// Milliseconds spent obtaining the candidate list, whatever its source. Agnostic of origin
    /// on purpose, so the assisted and degraded paths stay comparable to each other.
    /// </summary>
    public int? RetrievalMs { get; set; }

    /// <summary>
    /// Milliseconds from receiving the request to having the final list ready to return.
    /// The difference against <see cref="RetrievalMs"/> is what hydration costs.
    /// </summary>
    public int? TotalMs { get; set; }

    /// <summary>
    /// Product the operator picked, if any.
    /// </summary>
    public Guid? SelectedProductId { get; set; }

    /// <summary>
    /// One-based position of the selected product within the stored result list, derived by the
    /// server. Null when the selected product does not appear in that list, which always
    /// indicates a defect and is recorded rather than rejected: a null does not lie, a missing
    /// row does.
    /// </summary>
    public int? SelectedFromRank { get; set; }

    /// <summary>
    /// When the selection arrived, stamped by the server.
    /// </summary>
    /// <remarks>
    /// Deliberately not <see cref="BaseEntity.UpdatedAt"/>, which is an audit column the context
    /// overwrites on every save. Reusing it would make this KPI start lying, silently, the first
    /// time any later write touched the row.
    /// </remarks>
    public DateTime? SelectedAt { get; set; }
}
