using System.Diagnostics;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Application.Interfaces;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Polly.CircuitBreaker;
using Polly.Timeout;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Typed client for the jbg-ai service.
/// </summary>
/// <remarks>
/// Lives in the application layer rather than in infrastructure because
/// <c>JoiabagurPV.Infrastructure</c> references only <c>Domain</c>: implementing it there would
/// force the AI transport models up into the jewellery domain, where they do not belong.
/// </remarks>
public class AiGatewayClient : IAiGatewayClient
{
    /// <summary>Named client carrying the retrieval time budget and its own circuit breaker.</summary>
    public const string RetrievalClientName = "ai-retrieval";

    /// <summary>
    /// Named client for catalog enrichment, with its own budget and its own breaker state.
    /// </summary>
    /// <remarks>
    /// Separate from retrieval on purpose, and not as a formality. An extraction call is orders
    /// of magnitude slower than a retrieval one, so sharing a breaker would let a batch of
    /// enrichment open the retrieval circuit and push every operator's search onto its degraded
    /// lexical path — for a service that is answering retrieval perfectly well.
    /// </remarks>
    public const string EnrichClientName = "ai-enrich";

    /// <summary>
    /// Named client for the health probe. Carries a short timeout and <b>no resilience
    /// pipeline at all</b>.
    /// </summary>
    /// <remarks>
    /// No breaker, and that is the reason it exists as a separate client rather than reusing
    /// <see cref="RetrievalClientName"/>. The probe's job is to say what is wrong when the main
    /// path is already failing; sharing the retrieval breaker would make it refuse to look at
    /// exactly the moment somebody opens the dashboard to find out why. No retry either: an
    /// administrator refreshing a card is the retry.
    /// </remarks>
    public const string HealthClientName = "ai-health";

    /// <summary>Correlation header, the only thing that ties a rejected request to its origin.</summary>
    public const string TraceHeaderName = "X-Trace-Id";

    private const string RetrievalPath = "/v1/retrieval/products";
    private const string EnrichPath = "/v1/enrich/products";
    private const string HealthPath = "/health";
    private const string FamilySuggestPath = "/v1/families/suggest";
    private const string FamilyAuditPath = "/v1/families/audit";

    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IAiServiceTokenFactory _tokenFactory;
    private readonly ITraceContextAccessor _traceContextAccessor;
    private readonly AiGatewayOptions _options;
    private readonly ILogger<AiGatewayClient> _logger;

    public AiGatewayClient(
        IHttpClientFactory httpClientFactory,
        IAiServiceTokenFactory tokenFactory,
        ITraceContextAccessor traceContextAccessor,
        IOptions<AiGatewayOptions> options,
        ILogger<AiGatewayClient> logger)
    {
        _httpClientFactory = httpClientFactory ?? throw new ArgumentNullException(nameof(httpClientFactory));
        _tokenFactory = tokenFactory ?? throw new ArgumentNullException(nameof(tokenFactory));
        _traceContextAccessor = traceContextAccessor ?? throw new ArgumentNullException(nameof(traceContextAccessor));
        _options = options?.Value ?? throw new ArgumentNullException(nameof(options));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <inheritdoc/>
    public async Task<AiSearchResponse> SearchAsync(
        AiSearchRequest request,
        AiCallScope scope,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(scope);

        // The first of two independent closures on this boundary. From C22 onward the pos_id
        // claim is the retriever's only hard filter, so a catalog scope reaching this route
        // would be a cross-POS leak. jbg-ai refuses it too; neither side is trusted to be the
        // only one that remembers.
        if (scope.Kind != AiCallScopeKind.PointOfSale)
        {
            throw new ArgumentException(
                "Retrieval requires a point-of-sale scope. A catalog scope carries no pos_id, "
                + "which the retriever uses as its only hard filter between points of sale.",
                nameof(scope));
        }

        var traceId = _traceContextAccessor.CurrentTraceId;

        using var logScope = _logger.BeginScope(new Dictionary<string, object>
        {
            ["trace_id"] = traceId,
            ["endpoint"] = RetrievalPath
        });

        // The operator's query never rises above Debug: it is free text that may accidentally
        // contain personal data, and production logs are not the place to find that out.
        _logger.LogDebug("ai_gateway_call_query {Query}", request.Query);

        _logger.LogInformation(
            "ai_gateway_call_started {PosId} {Role} {TopK} {QueryLength}",
            scope.PointOfSaleId,
            scope.Role,
            request.TopK,
            request.Query.Length);

        var stopwatch = Stopwatch.StartNew();
        AiGatewayAttemptTracker.Begin();

        try
        {
            var client = _httpClientFactory.CreateClient(RetrievalClientName);

            using var httpRequest = new HttpRequestMessage(HttpMethod.Post, RetrievalPath)
            {
                Content = JsonContent.Create(request, options: AiGatewaySerialization.Options)
            };

            httpRequest.Headers.Authorization =
                new AuthenticationHeaderValue("Bearer", _tokenFactory.Create(scope, traceId));
            httpRequest.Headers.TryAddWithoutValidation(TraceHeaderName, traceId);

            using var response = await client.SendAsync(httpRequest, cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                throw TranslateStatus(response.StatusCode, stopwatch, RetrievalPath);
            }

            var payload = await response.Content.ReadFromJsonAsync<AiSearchResponse>(
                AiGatewaySerialization.Options,
                cancellationToken);

            if (payload is null)
            {
                throw Fail(AiGatewayOutcome.ServerError, stopwatch,
                    new AiUnavailableException("The AI service returned an empty retrieval body."));
            }

            stopwatch.Stop();

            _logger.LogInformation(
                "ai_gateway_call_completed {StatusCode} {LatencyMs} {Attempts} {CandidatesReturned} {ResultsCount} {LowConfidence}",
                (int)response.StatusCode,
                stopwatch.ElapsedMilliseconds,
                AiGatewayAttemptTracker.Attempts,
                payload.CandidatesReturned,
                payload.Results.Count,
                payload.LowConfidence);

            return payload;
        }
        catch (AiGatewayException)
        {
            // Already translated and logged by TranslateStatus / Fail.
            throw;
        }
        catch (BrokenCircuitException ex)
        {
            // The breaker short-circuits before any request leaves the process.
            throw Fail(AiGatewayOutcome.CircuitOpen, stopwatch,
                new AiUnavailableException("The AI service circuit is open; no request was issued.", ex));
        }
        catch (TimeoutRejectedException ex)
        {
            throw Fail(AiGatewayOutcome.Timeout, stopwatch,
                new AiUnavailableException("The AI service did not answer within the time budget.", ex));
        }
        catch (OperationCanceledException ex) when (!cancellationToken.IsCancellationRequested)
        {
            // A cancellation the caller did not ask for is this client's own budget expiring.
            throw Fail(AiGatewayOutcome.Timeout, stopwatch,
                new AiUnavailableException("The AI service did not answer within the time budget.", ex));
        }
        catch (HttpRequestException ex)
        {
            throw Fail(AiGatewayOutcome.Transport, stopwatch,
                new AiUnavailableException("The AI service could not be reached.", ex));
        }
        finally
        {
            AiGatewayAttemptTracker.End();
        }
    }

    /// <inheritdoc/>
    public async Task<AiEnrichResponse> EnrichAsync(
        AiEnrichRequest request,
        AiCallScope scope,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(scope);

        // The mirror image of the guard in SearchAsync. Enrichment covers the whole catalog, so
        // a point-of-sale scope here would silently narrow nothing and merely emit a claim the
        // route does not use — but accepting it would blur the one distinction that keeps the
        // catalog scope from drifting into retrieval.
        if (scope.Kind != AiCallScopeKind.Catalog)
        {
            throw new ArgumentException(
                "Catalog enrichment requires a catalog scope. Enriching the catalog belongs to no "
                + "point of sale.",
                nameof(scope));
        }

        if (request.Products.Count is 0 or > AiEnrichRequest.MaxBatchSize)
        {
            throw new ArgumentException(
                $"A batch must hold between 1 and {AiEnrichRequest.MaxBatchSize} products, which is "
                + "the limit the frozen contract accepts.",
                nameof(request));
        }

        var traceId = _traceContextAccessor.CurrentTraceId;

        using var logScope = _logger.BeginScope(new Dictionary<string, object>
        {
            ["trace_id"] = traceId,
            ["endpoint"] = EnrichPath
        });

        _logger.LogInformation(
            "ai_gateway_enrich_started {Role} {ProductCount}",
            scope.Role,
            request.Products.Count);

        var stopwatch = Stopwatch.StartNew();
        AiGatewayAttemptTracker.Begin();

        try
        {
            var client = _httpClientFactory.CreateClient(EnrichClientName);

            using var httpRequest = new HttpRequestMessage(HttpMethod.Post, EnrichPath)
            {
                Content = JsonContent.Create(request, options: AiGatewaySerialization.Options)
            };

            httpRequest.Headers.Authorization =
                new AuthenticationHeaderValue("Bearer", _tokenFactory.Create(scope, traceId));
            httpRequest.Headers.TryAddWithoutValidation(TraceHeaderName, traceId);

            using var response = await client.SendAsync(httpRequest, cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                throw TranslateStatus(response.StatusCode, stopwatch, EnrichPath);
            }

            var payload = await response.Content.ReadFromJsonAsync<AiEnrichResponse>(
                AiGatewaySerialization.Options,
                cancellationToken);

            if (payload is null)
            {
                throw Fail(AiGatewayOutcome.ServerError, stopwatch,
                    new AiUnavailableException("The AI service returned an empty enrichment body."));
            }

            stopwatch.Stop();

            // Token usage is logged on every batch, not sampled. The delivery commits to
            // reporting what the AI costs, and a figure nobody recorded cannot be reported.
            _logger.LogInformation(
                "ai_gateway_enrich_completed {StatusCode} {LatencyMs} {ProfileCount} {TotalTokens} {PromptVersion}",
                (int)response.StatusCode,
                stopwatch.ElapsedMilliseconds,
                payload.Profiles.Count,
                payload.Usage.TotalTokens,
                payload.PromptVersion);

            return payload;
        }
        catch (AiGatewayException)
        {
            throw;
        }
        catch (BrokenCircuitException ex)
        {
            throw Fail(AiGatewayOutcome.CircuitOpen, stopwatch,
                new AiUnavailableException("The AI enrichment circuit is open; no request was issued.", ex));
        }
        catch (TimeoutRejectedException ex)
        {
            throw Fail(AiGatewayOutcome.Timeout, stopwatch,
                new AiUnavailableException("The AI service did not answer within the enrichment time budget.", ex));
        }
        catch (OperationCanceledException ex) when (!cancellationToken.IsCancellationRequested)
        {
            throw Fail(AiGatewayOutcome.Timeout, stopwatch,
                new AiUnavailableException("The AI service did not answer within the enrichment time budget.", ex));
        }
        catch (HttpRequestException ex)
        {
            throw Fail(AiGatewayOutcome.Transport, stopwatch,
                new AiUnavailableException("The AI service could not be reached.", ex));
        }
        finally
        {
            AiGatewayAttemptTracker.End();
        }
    }

    /// <inheritdoc/>
    public async Task<AiHealthResponse> HealthAsync(CancellationToken cancellationToken = default)
    {
        var traceId = _traceContextAccessor.CurrentTraceId;

        using var logScope = _logger.BeginScope(new Dictionary<string, object>
        {
            ["trace_id"] = traceId,
            ["endpoint"] = HealthPath
        });

        var stopwatch = Stopwatch.StartNew();

        try
        {
            // The health client, never the retrieval one. Its pipeline is empty on purpose:
            // see HealthClientName.
            var client = _httpClientFactory.CreateClient(HealthClientName);

            using var httpRequest = new HttpRequestMessage(HttpMethod.Get, HealthPath);

            // No Authorization header: GET /health is public on the jbg-ai side. The
            // restriction that matters is on this side, where the calling endpoint is limited
            // to administrators.
            httpRequest.Headers.TryAddWithoutValidation(TraceHeaderName, traceId);

            using var response = await client.SendAsync(httpRequest, cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                throw Fail(AiGatewayOutcome.ServerError, stopwatch,
                    new AiUnavailableException($"The AI service answered {(int)response.StatusCode} on its health probe."));
            }

            var payload = await response.Content.ReadFromJsonAsync<AiHealthResponse>(
                AiGatewaySerialization.Options,
                cancellationToken);

            if (payload is null)
            {
                throw Fail(AiGatewayOutcome.ServerError, stopwatch,
                    new AiUnavailableException("The AI service returned an empty health body."));
            }

            stopwatch.Stop();

            _logger.LogInformation(
                "ai_gateway_health_completed {LatencyMs} {ServiceStatus} {Database} {IndexStatus} {IndexedDocuments}",
                stopwatch.ElapsedMilliseconds,
                payload.Status,
                payload.Database,
                payload.Index.Status,
                payload.Index.Documents);

            return payload;
        }
        catch (AiGatewayException)
        {
            throw;
        }
        catch (TimeoutRejectedException ex)
        {
            throw Fail(AiGatewayOutcome.Timeout, stopwatch,
                new AiUnavailableException("The AI service did not answer its health probe in time.", ex));
        }
        catch (OperationCanceledException ex) when (!cancellationToken.IsCancellationRequested)
        {
            throw Fail(AiGatewayOutcome.Timeout, stopwatch,
                new AiUnavailableException("The AI service did not answer its health probe in time.", ex));
        }
        catch (HttpRequestException ex)
        {
            throw Fail(AiGatewayOutcome.Transport, stopwatch,
                new AiUnavailableException("The AI service could not be reached.", ex));
        }
    }

    /// <inheritdoc/>
    public async Task<AiFamilyAuditResponse> AuditFamiliesAsync(
        AiFamilyAuditRequest request,
        AiCallScope scope,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(scope);

        // Same guard as suggestion, for the same reason: the audit covers every family in the
        // catalog, so a point-of-sale scope would narrow nothing and merely emit a claim the
        // route ignores.
        if (scope.Kind != AiCallScopeKind.Catalog)
        {
            throw new ArgumentException(
                "Family audit requires a catalog scope. Auditing the catalog's families belongs "
                + "to no point of sale.",
                nameof(scope));
        }

        if (request.MaxOrphans is < 1 or > AiFamilyAuditRequest.MaxOrphansLimit)
        {
            throw new ArgumentException(
                $"max_orphans must be between 1 and {AiFamilyAuditRequest.MaxOrphansLimit}, "
                + "which is the range the frozen contract accepts.",
                nameof(request));
        }

        var traceId = _traceContextAccessor.CurrentTraceId;

        using var logScope = _logger.BeginScope(new Dictionary<string, object>
        {
            ["trace_id"] = traceId,
            ["endpoint"] = FamilyAuditPath
        });

        _logger.LogInformation(
            "ai_gateway_family_audit_started {Role} {JudgedPairs}",
            scope.Role,
            request.JudgedPairs.Count);

        var stopwatch = Stopwatch.StartNew();
        AiGatewayAttemptTracker.Begin();

        try
        {
            // The enrichment client, like suggestion: a catalog-wide read that shares enrichment's
            // budget and breaker rather than spending retrieval's.
            var client = _httpClientFactory.CreateClient(EnrichClientName);

            using var httpRequest = new HttpRequestMessage(HttpMethod.Post, FamilyAuditPath)
            {
                Content = JsonContent.Create(request, options: AiGatewaySerialization.Options)
            };

            httpRequest.Headers.Authorization =
                new AuthenticationHeaderValue("Bearer", _tokenFactory.Create(scope, traceId));
            httpRequest.Headers.TryAddWithoutValidation(TraceHeaderName, traceId);

            using var response = await client.SendAsync(httpRequest, cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                throw TranslateStatus(response.StatusCode, stopwatch, FamilyAuditPath);
            }

            var payload = await response.Content.ReadFromJsonAsync<AiFamilyAuditResponse>(
                AiGatewaySerialization.Options,
                cancellationToken);

            if (payload is null)
            {
                // Never a silent empty result. On this route an empty body and a clean catalog
                // look identical to the screen, and only one of them is true.
                throw Fail(AiGatewayOutcome.ServerError, stopwatch,
                    new AiUnavailableException("The AI service returned an empty audit body."));
            }

            stopwatch.Stop();

            // The two examined counts are logged beside the findings, so that "nothing flagged"
            // can be told from "nothing looked at" in the log as well as on the screen.
            _logger.LogInformation(
                "ai_gateway_family_audit_completed {StatusCode} {LatencyMs} {Flagged} {Candidates} {Families} {Members}",
                (int)response.StatusCode,
                stopwatch.ElapsedMilliseconds,
                payload.FlaggedMembers.Count,
                payload.OrphanCandidates.Count,
                payload.FamiliesReviewedCount,
                payload.MembersExaminedCount);

            return payload;
        }
        catch (AiGatewayException)
        {
            throw;
        }
        catch (BrokenCircuitException ex)
        {
            throw Fail(AiGatewayOutcome.CircuitOpen, stopwatch,
                new AiUnavailableException("The AI enrichment circuit is open; no request was issued.", ex));
        }
        catch (TimeoutRejectedException ex)
        {
            throw Fail(AiGatewayOutcome.Timeout, stopwatch,
                new AiUnavailableException("The AI service did not answer within the batch time budget.", ex));
        }
        catch (OperationCanceledException ex) when (!cancellationToken.IsCancellationRequested)
        {
            throw Fail(AiGatewayOutcome.Timeout, stopwatch,
                new AiUnavailableException("The AI service did not answer within the batch time budget.", ex));
        }
        catch (HttpRequestException ex)
        {
            throw Fail(AiGatewayOutcome.Transport, stopwatch,
                new AiUnavailableException("The AI service could not be reached.", ex));
        }
        finally
        {
            AiGatewayAttemptTracker.End();
        }
    }

    public async Task<AiFamilySuggestResponse> SuggestFamiliesAsync(
        AiFamilySuggestRequest request,
        AiCallScope scope,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(scope);

        // Same guard as EnrichAsync, for the same reason: grouping covers the whole catalog, so
        // a point-of-sale scope would narrow nothing and merely emit a claim the route ignores.
        if (scope.Kind != AiCallScopeKind.Catalog)
        {
            throw new ArgumentException(
                "Family suggestion requires a catalog scope. Grouping the catalog belongs to no "
                + "point of sale.",
                nameof(scope));
        }

        if (request.MaxProposals is < 1 or > AiFamilySuggestRequest.MaxProposalsLimit)
        {
            throw new ArgumentException(
                $"max_proposals must be between 1 and {AiFamilySuggestRequest.MaxProposalsLimit}, "
                + "which is the range the frozen contract accepts.",
                nameof(request));
        }

        var traceId = _traceContextAccessor.CurrentTraceId;

        using var logScope = _logger.BeginScope(new Dictionary<string, object>
        {
            ["trace_id"] = traceId,
            ["endpoint"] = FamilySuggestPath
        });

        _logger.LogInformation("ai_gateway_family_suggest_started {Role}", scope.Role);

        var stopwatch = Stopwatch.StartNew();
        AiGatewayAttemptTracker.Begin();

        try
        {
            // The enrichment client, not the retrieval one: this is a catalog-wide batch that
            // shares enrichment.s budget and breaker, and it must not spend retrieval.s.
            var client = _httpClientFactory.CreateClient(EnrichClientName);

            using var httpRequest = new HttpRequestMessage(HttpMethod.Post, FamilySuggestPath)
            {
                Content = JsonContent.Create(request, options: AiGatewaySerialization.Options)
            };

            httpRequest.Headers.Authorization =
                new AuthenticationHeaderValue("Bearer", _tokenFactory.Create(scope, traceId));
            httpRequest.Headers.TryAddWithoutValidation(TraceHeaderName, traceId);

            using var response = await client.SendAsync(httpRequest, cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                throw TranslateStatus(response.StatusCode, stopwatch, FamilySuggestPath);
            }

            var payload = await response.Content.ReadFromJsonAsync<AiFamilySuggestResponse>(
                AiGatewaySerialization.Options,
                cancellationToken);

            if (payload is null)
            {
                throw Fail(AiGatewayOutcome.ServerError, stopwatch,
                    new AiUnavailableException("The AI service returned an empty suggestion body."));
            }

            stopwatch.Stop();

            // The two refusal counts are logged beside the proposal count on purpose: a run that
            // proposes little because it refused much is a catalog finding, not a quiet failure.
            _logger.LogInformation(
                "ai_gateway_family_suggest_completed {StatusCode} {LatencyMs} {Proposals} {Rejected} {Excluded}",
                (int)response.StatusCode,
                stopwatch.ElapsedMilliseconds,
                payload.Proposals.Count,
                payload.RejectedGroups.Count,
                payload.ExcludedProducts.Count);

            return payload;
        }
        catch (AiGatewayException)
        {
            throw;
        }
        catch (BrokenCircuitException ex)
        {
            throw Fail(AiGatewayOutcome.CircuitOpen, stopwatch,
                new AiUnavailableException("The AI enrichment circuit is open; no request was issued.", ex));
        }
        catch (TimeoutRejectedException ex)
        {
            throw Fail(AiGatewayOutcome.Timeout, stopwatch,
                new AiUnavailableException("The AI service did not answer within the batch time budget.", ex));
        }
        catch (OperationCanceledException ex) when (!cancellationToken.IsCancellationRequested)
        {
            throw Fail(AiGatewayOutcome.Timeout, stopwatch,
                new AiUnavailableException("The AI service did not answer within the batch time budget.", ex));
        }
        catch (HttpRequestException ex)
        {
            throw Fail(AiGatewayOutcome.Transport, stopwatch,
                new AiUnavailableException("The AI service could not be reached.", ex));
        }
        finally
        {
            AiGatewayAttemptTracker.End();
        }
    }

    /// <summary>
    /// Maps a non-success status onto the contract's failure modes.
    /// </summary>
    /// <remarks>
    /// A 401 is configuration rather than a transient fault, and a 501 means the route has no
    /// implementation yet — jbg-ai chose 501 over 503 exactly so this client would not insist.
    /// Both reach here only because the resilience pipeline declines to retry them.
    /// </remarks>
    private AiGatewayException TranslateStatus(HttpStatusCode statusCode, Stopwatch stopwatch, string path)
    {
        if (statusCode == HttpStatusCode.Unauthorized)
        {
            return Fail(AiGatewayOutcome.Unauthorized, stopwatch,
                new AiGatewayConfigurationException(
                    "The AI service rejected the internal token. Check that AiGateway:JwtSecret matches " +
                    "the service's JWT_SECRET; the service does not disclose the cause by design."),
                LogLevel.Error);
        }

        if (statusCode == HttpStatusCode.NotImplemented)
        {
            return Fail(AiGatewayOutcome.NotImplemented, stopwatch,
                new AiNotImplementedException(
                    $"The AI service has no implementation for {path} yet."));
        }

        return Fail(AiGatewayOutcome.ServerError, stopwatch,
            new AiUnavailableException($"The AI service answered {(int)statusCode}."));
    }

    private TException Fail<TException>(
        AiGatewayOutcome outcome,
        Stopwatch stopwatch,
        TException exception,
        LogLevel level = LogLevel.Warning)
        where TException : AiGatewayException
    {
        stopwatch.Stop();

        // base_url appears only here: when a call fails, the first useful question is where it
        // was pointing. Emitting it on every success would be noise.
        _logger.Log(
            level,
            "ai_gateway_call_failed {Outcome} {LatencyMs} {Attempts} {BaseUrl}",
            outcome.ToString().ToLowerInvariant(),
            stopwatch.ElapsedMilliseconds,
            outcome == AiGatewayOutcome.CircuitOpen ? 0 : AiGatewayAttemptTracker.Attempts,
            _options.BaseUrl);

        return exception;
    }
}
