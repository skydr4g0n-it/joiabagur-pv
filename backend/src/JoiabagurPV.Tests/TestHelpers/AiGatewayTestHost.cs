using JoiabagurPV.Application.Extensions;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Http;
using Microsoft.Extensions.Logging;

namespace JoiabagurPV.Tests.TestHelpers;

/// <summary>
/// Builds the AI gateway exactly as the API registers it, but with its outbound socket
/// replaced by a <see cref="FakeHttpMessageHandler"/>.
/// </summary>
/// <remarks>
/// The tests run against the real resilience pipeline on purpose. A hand-rolled stand-in would
/// test the stand-in: the interesting behaviour — what gets retried, when the breaker opens,
/// how the time budget expires — lives in the pipeline configuration, which is the thing under
/// test.
/// </remarks>
public static class AiGatewayTestHost
{
    public const string Secret = "test-jwt-secret-0123456789abcdefghij";

    /// <summary>
    /// Creates a provider wired like production. Breaker thresholds default low so a test can
    /// actually open the circuit: with the framework defaults, a couple of failures open nothing
    /// and a breaker test passes without ever exercising the breaker.
    /// </summary>
    public static ServiceProvider Build(
        FakeHttpMessageHandler handler,
        int retrievalTimeoutMs = 800,
        int breakerMinimumThroughput = 2,
        double breakerFailureRatio = 0.1,
        int breakerSamplingDurationSeconds = 10,
        int breakerBreakDurationSeconds = 30,
        string? traceId = null,
        RecordingLoggerProvider? logs = null,
        int enrichTimeoutMs = 120_000,
        FakeHttpMessageHandler? enrichHandler = null,
        FakeHttpMessageHandler? healthHandler = null,
        int healthTimeoutMs = 2000)
    {
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["AiGateway:BaseUrl"] = "http://localhost:8001",
                ["AiGateway:JwtSecret"] = Secret,
                ["AiGateway:TokenTtlSeconds"] = "300",
                ["AiGateway:RetrievalTimeoutMs"] = retrievalTimeoutMs.ToString(),
                ["AiGateway:BreakerMinimumThroughput"] = breakerMinimumThroughput.ToString(),
                ["AiGateway:BreakerFailureRatio"] = breakerFailureRatio.ToString(System.Globalization.CultureInfo.InvariantCulture),
                ["AiGateway:BreakerSamplingDurationSeconds"] = breakerSamplingDurationSeconds.ToString(),
                ["AiGateway:BreakerBreakDurationSeconds"] = breakerBreakDurationSeconds.ToString(),
                ["AiGateway:EnrichTimeoutMs"] = enrichTimeoutMs.ToString(),
                ["AiGateway:HealthTimeoutMs"] = healthTimeoutMs.ToString()
            })
            .Build();

        var services = new ServiceCollection();
        services.AddLogging(builder =>
        {
            if (logs is not null)
            {
                // Trace level so the debug-only query event is observable, which is exactly what
                // the privacy assertion needs to see in order to prove it stays down there.
                builder.SetMinimumLevel(LogLevel.Trace).AddProvider(logs);
            }
        });
        services.AddSingleton<ITraceContextAccessor>(new StubTraceContextAccessor(traceId ?? "trace-test-0001"));
        services.AddAiGateway(configuration);

        // Replace only the socket. Everything above it — token, pipeline, mapping — stays real.
        services.Configure<HttpClientFactoryOptions>(
            AiGatewayClient.RetrievalClientName,
            options => options.HttpMessageHandlerBuilderActions.Add(b => b.PrimaryHandler = handler));

        // The enrichment family gets its own handler when a test supplies one. Sharing the
        // retrieval handler would defeat the very property most worth asserting here: that the
        // two circuits are independent.
        services.Configure<HttpClientFactoryOptions>(
            AiGatewayClient.EnrichClientName,
            options => options.HttpMessageHandlerBuilderActions.Add(
                b => b.PrimaryHandler = enrichHandler ?? handler));

        // The health client gets its own handler too, for the same reason as enrichment and one
        // more: the property worth asserting about it is that an OPEN RETRIEVAL CIRCUIT does not
        // stop it answering. Sharing a handler would make that assertion meaningless.
        services.Configure<HttpClientFactoryOptions>(
            AiGatewayClient.HealthClientName,
            options => options.HttpMessageHandlerBuilderActions.Add(
                b => b.PrimaryHandler = healthHandler ?? handler));

        return services.BuildServiceProvider();
    }

    /// <summary>Resolves the client under test.</summary>
    public static IAiGatewayClient Client(this ServiceProvider provider) =>
        provider.GetRequiredService<IAiGatewayClient>();

    private sealed class StubTraceContextAccessor : ITraceContextAccessor
    {
        public StubTraceContextAccessor(string traceId) => CurrentTraceId = traceId;

        public string CurrentTraceId { get; }
    }
}
