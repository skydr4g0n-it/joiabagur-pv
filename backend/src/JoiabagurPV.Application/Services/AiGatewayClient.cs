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

    /// <summary>Correlation header, the only thing that ties a rejected request to its origin.</summary>
    public const string TraceHeaderName = "X-Trace-Id";

    private const string RetrievalPath = "/v1/retrieval/products";

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
                throw TranslateStatus(response.StatusCode, stopwatch);
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

    /// <summary>
    /// Maps a non-success status onto the contract's failure modes.
    /// </summary>
    /// <remarks>
    /// A 401 is configuration rather than a transient fault, and a 501 means the route has no
    /// implementation yet — jbg-ai chose 501 over 503 exactly so this client would not insist.
    /// Both reach here only because the resilience pipeline declines to retry them.
    /// </remarks>
    private AiGatewayException TranslateStatus(HttpStatusCode statusCode, Stopwatch stopwatch)
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
                    $"The AI service has no implementation for {RetrievalPath} yet."));
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
