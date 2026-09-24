using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using JoiabagurPV.Domain.Interfaces.Services;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Orchestrates one free-query search: the operator's own words, routed, answered from the corpus
/// and the catalog, and written up. C40.
/// </summary>
/// <remarks>
/// <para>
/// The third of the three assistance modes, and the only one that had no way to reach an
/// operator. It is the panel's assisted route: same query box, same filters, same shop selector
/// as the semantic path, with a router, a corpus and prose behind it.
/// </para>
/// <para>
/// <strong>Never throws because of the AI.</strong> Every failure of the gateway degrades to an
/// answer with no argument and a reason, exactly as the sale card does, because an operator with
/// a customer in front of them needs a screen that says something true rather than an error.
/// </para>
/// </remarks>
public class FreeQuerySearchService : IFreeQuerySearchService
{
    private readonly IAiGatewayClient _gateway;
    private readonly IAssistedSearchRepository _repository;
    private readonly IAssistedSearchResultProjector _projector;
    private readonly IUserPointOfSaleService _userPointOfSaleService;
    private readonly IProductSearchEventService _searchEventService;
    private readonly ITraceContextAccessor _traceContext;
    private readonly IOptionsMonitor<AiFreeQuerySearchOptions> _options;
    private readonly TimeProvider _timeProvider;
    private readonly ILogger<FreeQuerySearchService> _logger;

    public FreeQuerySearchService(
        IAiGatewayClient gateway,
        IAssistedSearchRepository repository,
        IAssistedSearchResultProjector projector,
        IUserPointOfSaleService userPointOfSaleService,
        IProductSearchEventService searchEventService,
        ITraceContextAccessor traceContext,
        IOptionsMonitor<AiFreeQuerySearchOptions> options,
        TimeProvider timeProvider,
        ILogger<FreeQuerySearchService> logger)
    {
        _gateway = gateway;
        _repository = repository;
        _projector = projector;
        _userPointOfSaleService = userPointOfSaleService;
        _searchEventService = searchEventService;
        _traceContext = traceContext;
        _options = options;
        _timeProvider = timeProvider;
        _logger = logger;
    }

    /// <inheritdoc/>
    public async Task<FreeQuerySearchResult> SearchAsync(
        FreeQuerySearchRequest request,
        Guid userId,
        string role,
        bool isAdmin,
        CancellationToken cancellationToken = default)
    {
        var startedAt = _timeProvider.GetTimestamp();
        var options = _options.CurrentValue;

        var access = await AuthoriseAsync(request.PointOfSaleId, userId, isAdmin, cancellationToken);
        if (access is not null)
        {
            return access;
        }

        var filters = BuildFilters(request);
        var pageSize = Math.Clamp(
            request.PageSize ?? options.DefaultPageSize, 1, options.MaxPageSize);

        AiAssistSaleResponse? ai = null;
        string? degradedReason = null;
        int? aiMs = null;

        // **Switched off costs no call and no quota.** The reason is recorded so the screen can
        // say a switch did it rather than presenting an outage that is not happening.
        if (!options.IsEnabledFor(request.PointOfSaleId))
        {
            degradedReason = "switched_off";
        }
        else
        {
            var aiStartedAt = _timeProvider.GetTimestamp();
            (ai, degradedReason) = await CallAsync(request, filters, userId, role, cancellationToken);
            aiMs = ElapsedMs(aiStartedAt);
        }

        var groups = ai is null
            ? []
            : await HydrateAsync(ai, request.PointOfSaleId, pageSize, cancellationToken);

        var candidates = ai?.Groups.Sum(group => group.Members.Count) ?? 0;
        var survived = groups.Sum(group => group.Members.Count);

        // Captured before telemetry: recording is work this figure must not include, or the
        // number starts describing the writer instead of the search.
        var totalMs = ElapsedMs(startedAt);

        var searchEventId = await RecordAsync(request, filters, userId, role, survived, totalMs);

        var response = new FreeQuerySearchResponse
        {
            Groups = groups,
            Pitch = string.IsNullOrWhiteSpace(ai?.Pitch) ? null : ai.Pitch,
            PitchStatus = StatusOf(ai),
            Citations = ai is null
                ? []
                : ai.Citations.Select(citation => new SalesAssistCitationDto
                {
                    CitationId = citation.CitationId,
                    DocumentTitle = citation.DocumentTitle,
                    SectionTitle = citation.SectionTitle,
                    DocType = citation.DocType,
                    ClaimScope = citation.ClaimScope,
                    Snippet = citation.Snippet
                }).ToList(),
            Warnings = QueryWarnings(ai),
            ClarificationQuestion = ai?.ClarificationQuestion,
            Intent = ai?.Intent,
            Abstained = ai?.Abstained ?? false,
            AiAvailable = ai is not null,
            DegradedReason = degradedReason,
            Usage = isAdmin ? UsageOf(ai, aiMs, totalMs) : null,
            SearchEventId = searchEventId,
            PointOfSaleId = request.PointOfSaleId,
            CandidatesReturned = candidates,
            SurvivedHydration = survived,
            TraceId = _traceContext.CurrentTraceId
        };

        LogFunnel(request, response, aiMs, totalMs);

        return FreeQuerySearchResult.Ok(response);
    }

    /// <summary>
    /// Checks that the caller may search on this point of sale, and that it is usable at all.
    /// </summary>
    /// <remarks>
    /// A point of sale is required. The third scope class — every shop at once — arrives with its
    /// own authorisation boundary and is deliberately not anticipated here.
    /// </remarks>
    private async Task<FreeQuerySearchResult?> AuthoriseAsync(
        Guid pointOfSaleId,
        Guid userId,
        bool isAdmin,
        CancellationToken cancellationToken)
    {
        if (!await _repository.IsPointOfSaleActiveAsync(pointOfSaleId, cancellationToken))
        {
            return FreeQuerySearchResult.Unavailable();
        }

        if (isAdmin)
        {
            return null;
        }

        return await _userPointOfSaleService.HasAccessAsync(userId, pointOfSaleId)
            ? null
            : FreeQuerySearchResult.Forbidden();
    }

    /// <summary>
    /// The call, with every failure of the gateway turned into a reason to degrade.
    /// </summary>
    /// <remarks>
    /// The same six-way partition the sale card uses, and deliberately the same vocabulary: the
    /// screen already knows how to word each of them, and a seventh word for the same situation
    /// would be a second thing to translate.
    ///
    /// **A generative failure must not open the retrieval circuit.** It does not, and not by
    /// care taken here: the two ride different named clients with different circuits, so the
    /// isolation is structural rather than a rule somebody has to remember.
    /// </remarks>
    private async Task<(AiAssistSaleResponse? Response, string? DegradedReason)> CallAsync(
        FreeQuerySearchRequest request,
        AiSearchFilters filters,
        Guid userId,
        string role,
        CancellationToken cancellationToken)
    {
        var traceId = _traceContext.CurrentTraceId;
        var scope = ScopeOf(request.PointOfSaleId, userId, role);

        try
        {
            var response = await _gateway.AssistSaleAsync(
                new AiAssistSaleRequest { Query = request.Query, Filters = filters },
                scope,
                cancellationToken);

            return (response, null);
        }
        catch (AiGatewayConfigurationException exception)
        {
            _logger.LogError(exception,
                "Free-query search degraded: the AI service rejected the gateway credentials. TraceId={TraceId}", traceId);
            return (null, "credential_rejected");
        }
        catch (AiNotImplementedException exception)
        {
            _logger.LogError(exception,
                "Free-query search degraded: the route is not implemented on the AI service. TraceId={TraceId}", traceId);
            return (null, "not_implemented");
        }
        catch (AiRequestRejectedException exception)
        {
            _logger.LogWarning(exception,
                "Free-query search degraded: the AI service refused the request. TraceId={TraceId}", traceId);
            return (null, "not_indexed");
        }
        catch (AiUnavailableException exception)
        {
            _logger.LogWarning(exception,
                "Free-query search degraded: the AI service is unavailable. TraceId={TraceId}", traceId);
            return (null, "ai_unavailable");
        }
        catch (AiGatewayException exception)
        {
            // Final clause over the abstract base, so "the search never breaks because of the
            // AI" survives the day somebody adds another failure type.
            _logger.LogError(exception,
                "Free-query search degraded: unclassified gateway failure of type {FailureType}. TraceId={TraceId}",
                exception.GetType().Name, traceId);
            return (null, "unclassified");
        }
    }

    /// <summary>
    /// Hydrates what the AI service proposed against the catalog, keeping its order.
    /// </summary>
    /// <remarks>
    /// One query for every member of every group, not one per group: hydrating group by group
    /// would issue five round trips inside a request already competing with a ten-second budget.
    /// A member the point of sale does not carry drops out, and a group left with no member drops
    /// out with it — a family nobody can sell here is not an answer.
    /// </remarks>
    private async Task<List<FreeQueryGroupDto>> HydrateAsync(
        AiAssistSaleResponse ai,
        Guid pointOfSaleId,
        int pageSize,
        CancellationToken cancellationToken)
    {
        var ids = new List<Guid>();
        foreach (var member in ai.Groups.SelectMany(group => group.Members))
        {
            if (Guid.TryParse(member.ProductId, out var id))
            {
                ids.Add(id);
            }
            else
            {
                _logger.LogWarning(
                    "Free-query search dropped a candidate whose product identifier is not a GUID. Sku={Sku} TraceId={TraceId}",
                    member.Sku,
                    _traceContext.CurrentTraceId);
            }
        }

        if (ids.Count == 0)
        {
            return [];
        }

        var rows = await _repository.HydrateAsync(ids, pointOfSaleId, cancellationToken);

        var byId = rows.ToDictionary(row => row.ProductId);
        var groups = new List<FreeQueryGroupDto>();

        foreach (var group in ai.Groups.Take(pageSize))
        {
            var members = new List<AssistedSearchResultDto>();

            foreach (var member in group.Members)
            {
                if (!Guid.TryParse(member.ProductId, out var id) || !byId.TryGetValue(id, out var row))
                {
                    continue;
                }

                members.Add(await _projector.ProjectAsync(row, new AiSearchResult
                {
                    ProductId = member.ProductId,
                    Sku = member.Sku,
                    Score = member.Score,
                    Materials = member.Materials,
                    MatchReasons = member.MatchReasons,
                    FamilyId = group.FamilyId,
                    VariantLabel = member.VariantLabel
                }));
            }

            if (members.Count > 0)
            {
                groups.Add(new FreeQueryGroupDto
                {
                    FamilyId = group.FamilyId,
                    FamilyLabel = group.FamilyLabel,
                    Members = members
                });
            }
        }

        return groups;
    }

    /// <summary>
    /// The warnings that describe <strong>the query</strong>, which are the only ones this screen
    /// may paint.
    /// </summary>
    /// <remarks>
    /// The AI service stacks two different subjects into one array. A warning about a piece
    /// describes the first member of the first group, so rendering it above a list of fifteen
    /// would state something false about fourteen of them. Filtering by an allow-list rather than
    /// by a deny-list is what keeps a code added later from leaking onto the screen by default.
    /// </remarks>
    private static List<string> QueryWarnings(AiAssistSaleResponse? ai) =>
        ai is null
            ? []
            : ai.Warnings.Where(QueryWarningCodes.Contains).ToList();

    /// <summary>Warning codes whose subject is the query rather than a piece.</summary>
    private static readonly HashSet<string> QueryWarningCodes =
    [
        "query_out_of_domain",
        "query_not_in_catalogue",
        "knowledge_not_covered",
        "filters_too_narrow"
    ];

    /// <summary>
    /// The state of the argument. Simpler than the card's because nothing is resolved here.
    /// </summary>
    /// <remarks>
    /// The free-query argument carries no placeholder — `assist/v5` forbids them and a hard cause
    /// in the service's integrity gate enforces it — so there is no resolution step and therefore
    /// no <c>withheld_unresolved</c>. The other distinctions are the card's and reuse its
    /// vocabulary, including the one the screen needs most: a version present with no text means
    /// the model wrote and the gate withheld, and a version absent means nothing generated.
    /// </remarks>
    private static PitchStatus StatusOf(AiAssistSaleResponse? ai)
    {
        if (ai is null)
        {
            return PitchStatus.AiUnavailable;
        }

        if (ai.PromptVersion is null)
        {
            return PitchStatus.NotGenerated;
        }

        return string.IsNullOrWhiteSpace(ai.Pitch)
            ? PitchStatus.WithheldByAi
            : PitchStatus.Generated;
    }

    /// <summary>What the search cost. Built only when the caller is an administrator.</summary>
    private static FreeQueryUsageDto? UsageOf(AiAssistSaleResponse? ai, int? aiMs, int totalMs) =>
        new()
        {
            Model = ai?.Usage.Model,
            PromptTokens = ai?.Usage.PromptTokens ?? 0,
            CompletionTokens = ai?.Usage.CompletionTokens ?? 0,
            TotalTokens = ai?.Usage.TotalTokens ?? 0,
            PromptVersion = ai?.PromptVersion,
            AiMs = aiMs,
            TotalMs = totalMs
        };

    /// <summary>
    /// The scope that carries the shop into the service token.
    /// </summary>
    /// <remarks>
    /// A point of sale is required here. The third scope class — every shop at once — is a
    /// separate piece of work with an authorisation boundary of its own, and giving this service
    /// a provisional version of it would be the kind of half-open door nobody revisits.
    /// </remarks>
    private static AiCallScope ScopeOf(Guid pointOfSaleId, Guid userId, string role) =>
        AiCallScope.ForPointOfSale(userId, role, pointOfSaleId);

    private static AiSearchFilters BuildFilters(FreeQuerySearchRequest request) => new()
    {
        Materials = request.Materials
            .Where(material => !string.IsNullOrWhiteSpace(material))
            .Select(material => material.Trim())
            .ToList(),
        Category = string.IsNullOrWhiteSpace(request.Category) ? null : request.Category.Trim()
    };

    /// <summary>
    /// Records the search. Never throws: telemetry is expendable and a search is not.
    /// </summary>
    /// <remarks>
    /// The query text is persisted exactly as the semantic path persists it, inheriting the same
    /// retention limitation and declaring it rather than discovering it later. The customer's
    /// question asked about one piece on the sale card is <strong>not</strong> persisted, because
    /// it is of another nature.
    /// </remarks>
    private async Task<Guid?> RecordAsync(
        FreeQuerySearchRequest request,
        AiSearchFilters filters,
        Guid userId,
        string role,
        int resultCount,
        int totalMs)
    {
        try
        {
            return await _searchEventService.RecordSearchAsync(new RecordSearchRequest
            {
                Scope = ScopeOf(request.PointOfSaleId, userId, role),
                Query = request.Query,
                Filters = filters,
                DisplayedResults = [],
                // The fourth origin, which is what turns the comparison of the two routes into a
                // query over the telemetry rather than a demonstration on a screen.
                Origin = SearchOrigin.AssistedGenerative,
                SearchSessionId = request.SearchSessionId,
                TraceId = _traceContext.CurrentTraceId,
                RetrievalMs = null,
                TotalMs = totalMs
            });
        }
        catch (Exception exception)
        {
            _logger.LogWarning(exception,
                "Free-query search served but telemetry could not persist. TraceId={TraceId}",
                _traceContext.CurrentTraceId);
            return null;
        }
    }

    private void LogFunnel(
        FreeQuerySearchRequest request,
        FreeQuerySearchResponse response,
        int? aiMs,
        int totalMs)
    {
        // Neither the query nor the argument: the first is what a customer said and the second
        // carries it back. Lengths are diagnostic without being content.
        _logger.LogInformation(
            "stage=free_query_search trace_id={TraceId} pos_id={PointOfSaleId} query_len={QueryLength} intent={Intent} ai_available={AiAvailable} degraded_reason={DegradedReason} pitch_status={PitchStatus} pitch_len={PitchLength} groups={Groups} survived={Survived} citations={Citations} warnings={Warnings} abstained={Abstained} ai_ms={AiMs} total_ms={TotalMs} prompt_version={PromptVersion}",
            response.TraceId,
            request.PointOfSaleId,
            request.Query.Length,
            response.Intent,
            response.AiAvailable,
            response.DegradedReason,
            response.PitchStatus,
            response.Pitch?.Length ?? 0,
            response.Groups.Count,
            response.SurvivedHydration,
            response.Citations.Count,
            string.Join(",", response.Warnings),
            response.Abstained,
            aiMs,
            totalMs,
            response.Usage?.PromptVersion);
    }

    private int ElapsedMs(long startedAt) =>
        (int)_timeProvider.GetElapsedTime(startedAt).TotalMilliseconds;
}
