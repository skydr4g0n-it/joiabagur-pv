using System.Text.Json;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.Extensions.Logging;

namespace JoiabagurPV.Application.Services;

/// <inheritdoc cref="IProductSearchEventService"/>
public class ProductSearchEventService : IProductSearchEventService
{
    /// <summary>
    /// Most result entries stored on one event.
    /// </summary>
    /// <remarks>
    /// A guardrail, not a feature. With a page of ten to twenty results this is never reached in
    /// normal operation, so hitting it means something upstream passed the raw candidate set
    /// instead of the displayed one. A tight cap would instead silently discard good data.
    /// Trimming is by entry count and never by byte length: a byte-truncated JSON document is
    /// invalid, useless for the analysis this column exists for, and PostgreSQL would reject it
    /// anyway now that the column is <c>jsonb</c>.
    /// </remarks>
    public const int MaxStoredResults = 50;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        // camelCase, fixed here on purpose. It is a one-way decision: the queries that read this
        // column are written by hand, and changing the casing later breaks all of them silently.
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };

    private readonly IRepository<ProductSearchEvent> _events;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<ProductSearchEventService> _logger;

    public ProductSearchEventService(
        IRepository<ProductSearchEvent> events,
        IUnitOfWork unitOfWork,
        ILogger<ProductSearchEventService> logger)
    {
        _events = events;
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    /// <inheritdoc/>
    public async Task<Guid?> RecordSearchAsync(RecordSearchRequest request)
    {
        try
        {
            var displayed = request.DisplayedResults;
            var stored = displayed
                .Take(MaxStoredResults)
                .Select((result, index) => new StoredSearchResult(
                    result.ProductId,
                    result.Sku,
                    index + 1,
                    result.Score,
                    result.MatchReasons))
                .ToList();

            // A search event belongs to a point of sale by definition, so a catalog scope
            // reaching here is a programming error rather than a runtime condition. It is
            // raised inside the try on purpose: the guarantee that telemetry never breaks a
            // search outranks surfacing a mistake that the compiler cannot catch since the
            // scope became nullable. It is swallowed and logged like any other failure below.
            var pointOfSaleId = request.Scope.PointOfSaleId
                ?? throw new ArgumentException(
                    "A search event requires a point-of-sale scope; a catalog scope cannot produce one.",
                    nameof(request));

            var searchEvent = new ProductSearchEvent
            {
                UserId = request.Scope.UserId,
                PointOfSaleId = pointOfSaleId,
                SearchSessionId = request.SearchSessionId ?? Guid.NewGuid(),
                SearchText = request.Query,
                FiltersJson = JsonSerializer.Serialize(request.Filters, JsonOptions),
                ResultsJson = JsonSerializer.Serialize(stored, JsonOptions),
                ResultsCount = displayed.Count,
                SearchOrigin = request.Origin,
                TraceId = request.TraceId,
                RetrievalMs = request.RetrievalMs,
                TotalMs = request.TotalMs
            };

            // The query text lives at Debug and nowhere above it. It is free text an operator
            // typed, it can incidentally carry personal data, and production logs are not where
            // that should be discovered. C03 set this rule and asserts it; this honours it.
            _logger.LogDebug("search_event_query {Query}", request.Query);

            await _events.AddAsync(searchEvent);
            await _unitOfWork.SaveChangesAsync();

            _logger.LogInformation(
                "search_event_recorded {EventId} {PointOfSaleId} {SearchOrigin} {ResultsCount} {QueryLength} {RetrievalMs}",
                searchEvent.Id,
                searchEvent.PointOfSaleId,
                searchEvent.SearchOrigin,
                searchEvent.ResultsCount,
                request.Query.Length,
                request.RetrievalMs);

            return searchEvent.Id;
        }
        catch (Exception exception)
        {
            // Swallowed on purpose. "The system never goes down because of the AI" extends to
            // measuring it: a caller must not be able to turn a telemetry problem into a failed
            // search, and the only way that survives contact with future callers is for the
            // guarantee to live here rather than in an instruction they might not read.
            _logger.LogError(
                exception,
                "search_event_record_failed {PointOfSaleId} {QueryLength}",
                request.Scope.PointOfSaleId,
                request.Query.Length);

            return null;
        }
    }

    /// <inheritdoc/>
    public async Task<SelectionOutcome> RecordSelectionAsync(
        Guid searchEventId,
        Guid userId,
        Guid selectedProductId)
    {
        var searchEvent = await _events.GetByIdAsync(searchEventId);

        if (searchEvent is null)
        {
            return SelectionOutcome.EventNotFound;
        }

        // Ownership, with no administrator exception. Elsewhere in the system an administrator
        // bypasses point-of-sale checks by design, because those guard business data an
        // administrator manages. A search event is not managed: it is the record of what one
        // person did, and letting anyone else complete it would allow corrupting the data
        // without leaving a trace.
        if (searchEvent.UserId != userId)
        {
            return SelectionOutcome.NotOwner;
        }

        var rank = RankOf(searchEvent.ResultsJson, selectedProductId);

        if (rank is null)
        {
            // Recorded rather than rejected. Rejecting would leave the event looking abandoned
            // and the conversion KPI would be wrong; a null rank simply drops out of the rank
            // KPI. A null does not lie, a missing row does.
            _logger.LogWarning(
                "search_event_selection_outside_results {EventId} {SelectedProductId}",
                searchEventId,
                selectedProductId);
        }

        // Last write wins: an operator who picks the third result, goes back and picks the
        // first has picked the first.
        searchEvent.SelectedProductId = selectedProductId;
        searchEvent.SelectedFromRank = rank;
        searchEvent.SelectedAt = DateTime.UtcNow;

        await _events.UpdateAsync(searchEvent);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation(
            "search_event_selection_recorded {EventId} {SelectedFromRank}",
            searchEventId,
            rank);

        return SelectionOutcome.Recorded;
    }

    /// <summary>
    /// One-based position of a product within the stored result list, or null when it is absent.
    /// </summary>
    /// <remarks>
    /// Derived here rather than accepted from the client for two reasons. It removes the only
    /// way the pair could disagree, so the invariant needs no validation. And it is more
    /// correct: the KPI asks how good retrieval was, which is the position retrieval produced,
    /// not the position an interface happened to render.
    /// </remarks>
    private static int? RankOf(string resultsJson, Guid selectedProductId)
    {
        var stored = JsonSerializer.Deserialize<List<StoredSearchResult>>(resultsJson, JsonOptions);

        if (stored is null)
        {
            return null;
        }

        foreach (var entry in stored)
        {
            if (Guid.TryParse(entry.ProductId, out var productId) && productId == selectedProductId)
            {
                return entry.Rank;
            }
        }

        return null;
    }

    /// <summary>
    /// One stored result: identity, position, and the two signals that cannot be recovered later.
    /// </summary>
    /// <remarks>
    /// The projection keeps only what a join cannot rebuild. The score and the match reasons
    /// depended on the index, the embedding model and the weights of that day, so they are
    /// frozen here for the same reason <c>Sale.Price</c> is frozen. Materials, family and
    /// variant are catalog attributes and stay out. The SKU is redundant with the identifier and
    /// is kept anyway, because these rows get read by hand and an array of raw identifiers is
    /// unreadable — the same trade already made in <c>ProductPhotoEmbedding</c>.
    /// </remarks>
    private sealed record StoredSearchResult(
        string ProductId,
        string Sku,
        int Rank,
        double Score,
        IReadOnlyList<string> MatchReasons);
}
