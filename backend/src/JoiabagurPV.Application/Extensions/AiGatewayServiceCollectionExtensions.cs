using System.Net;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Http.Resilience;
using Polly;
using Polly.Timeout;

namespace JoiabagurPV.Application.Extensions;

/// <summary>
/// Registers the jbg-ai gateway: options with start-up validation, the service token factory
/// and the named HTTP client carrying the resilience pipeline.
/// </summary>
public static class AiGatewayServiceCollectionExtensions
{
    /// <summary>
    /// Adds the AI gateway client and validates its configuration during host start-up.
    /// </summary>
    public static IServiceCollection AddAiGateway(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configuration);

        var section = configuration.GetSection(AiGatewayOptions.SectionName);

        // A disabled gateway registers nothing and validates nothing: an unused integration
        // must not be able to stop the API from starting.
        if (!section.GetValue("Enabled", true))
        {
            return services;
        }

        services
            .AddOptions<AiGatewayOptions>()
            .Bind(section)
            // Absolute is not enough: Uri.TryCreate accepts "localhost:8001" as an absolute URI
            // whose scheme is "localhost". That is precisely the typo someone makes in production
            // configuration, so the scheme is checked explicitly.
            .Validate(
                o => Uri.TryCreate(o.BaseUrl, UriKind.Absolute, out var uri)
                     && (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps),
                $"{AiGatewayOptions.SectionName}:BaseUrl must be an absolute http or https URI (for example http://localhost:8001).")
            .Validate(
                o => !string.IsNullOrWhiteSpace(o.JwtSecret),
                $"{AiGatewayOptions.SectionName}:JwtSecret is not configured. It must match the JWT_SECRET of the jbg-ai service literally.")
            .Validate(
                o => o.JwtSecret.Length >= AiGatewayOptions.MinimumSecretLength,
                $"{AiGatewayOptions.SectionName}:JwtSecret is too short for HS256; at least {AiGatewayOptions.MinimumSecretLength} characters are required.")
            .Validate(
                o => o.TokenTtlSeconds > 0 && o.RetrievalTimeoutMs > 0 && o.AssistTimeoutMs > 0
                     && o.EnrichTimeoutMs > 0 && o.HealthTimeoutMs > 0,
                $"{AiGatewayOptions.SectionName} time-to-live and time budgets must be positive.")
            // ValidateOnStart is the whole point. Without it the check is lazy and would surface
            // inside a request instead of at boot, which is the failure mode being removed here.
            .ValidateOnStart();

        var options = section.Get<AiGatewayOptions>() ?? new AiGatewayOptions();

        services.TryAddTimeProvider();
        services.AddScoped<IAiServiceTokenFactory, AiServiceTokenFactory>();
        services.AddScoped<IAiGatewayClient, AiGatewayClient>();

        services
            .AddHttpClient(AiGatewayClient.RetrievalClientName, client =>
            {
                client.BaseAddress = new Uri(options.BaseUrl);

                // The pipeline owns the time budget. Leaving HttpClient's own timeout in play
                // would race it and surface as a cancellation the retry cannot classify.
                client.Timeout = Timeout.InfiniteTimeSpan;
            })
            .AddResilienceHandler("ai-retrieval-pipeline", builder =>
            {
                // Outermost first. Retry wraps the breaker, which wraps the per-attempt timeout,
                // so each attempt gets the full budget and the breaker sees each attempt.
                builder.AddRetry(new HttpRetryStrategyOptions
                {
                    MaxRetryAttempts = 1,
                    Delay = TimeSpan.FromMilliseconds(100),
                    BackoffType = DelayBackoffType.Constant,
                    UseJitter = false,
                    ShouldHandle = args => ValueTask.FromResult(IsRetryable(args.Outcome)),
                    OnRetry = _ =>
                    {
                        AiGatewayAttemptTracker.RecordRetry();
                        return default;
                    }
                });

                builder.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
                {
                    FailureRatio = options.BreakerFailureRatio,
                    MinimumThroughput = options.BreakerMinimumThroughput,
                    SamplingDuration = TimeSpan.FromSeconds(options.BreakerSamplingDurationSeconds),
                    BreakDuration = TimeSpan.FromSeconds(options.BreakerBreakDurationSeconds),
                    ShouldHandle = args => ValueTask.FromResult(IsRetryable(args.Outcome))
                });

                builder.AddTimeout(TimeSpan.FromMilliseconds(options.RetrievalTimeoutMs));
            });

        services
            .AddHttpClient(AiGatewayClient.EnrichClientName, client =>
            {
                client.BaseAddress = new Uri(options.BaseUrl);
                client.Timeout = Timeout.InfiniteTimeSpan;
            })
            .AddResilienceHandler("ai-enrich-pipeline", builder =>
            {
                // No retry, deliberately. A second attempt at a structured extraction spends the
                // model budget again with no reason to expect a different answer, and the
                // delivery commits to the AI cost being instrumented and defensible. A failed
                // batch is re-run by an administrator who decided to, not by a policy.
                builder.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
                {
                    FailureRatio = options.BreakerFailureRatio,
                    MinimumThroughput = options.BreakerMinimumThroughput,
                    SamplingDuration = TimeSpan.FromSeconds(options.BreakerSamplingDurationSeconds),
                    BreakDuration = TimeSpan.FromSeconds(options.BreakerBreakDurationSeconds),
                    ShouldHandle = args => ValueTask.FromResult(IsRetryable(args.Outcome))
                });

                builder.AddTimeout(TimeSpan.FromMilliseconds(options.EnrichTimeoutMs));
            });

        // The health client (C17). NO resilience handler, and that is the entire point of it
        // being a separate registration rather than a third call on the retrieval client:
        //
        //   * No circuit breaker. The probe exists to diagnose the system when the main path is
        //     already failing. Sharing retrieval's breaker would make it decline to answer at
        //     exactly the moment an administrator opens the dashboard to find out why.
        //   * No retry. A human refreshing a card is the retry, and each attempt costs them a
        //     wait.
        //
        // The budget is therefore the client's own timeout, with no pipeline to race against it.
        services
            .AddHttpClient(AiGatewayClient.HealthClientName, client =>
            {
                client.BaseAddress = new Uri(options.BaseUrl);
                client.Timeout = TimeSpan.FromMilliseconds(options.HealthTimeoutMs);
            });

        // C34 registers its own named client here for the generative route, with a 5 s budget
        // and its own breaker state. Separate breakers on purpose: a slow language model must
        // not open the retrieval circuit and push the caller onto its lexical fallback for a
        // service that is answering correctly.

        return services;
    }

    /// <summary>
    /// Transient conditions worth one more attempt, and the same set the breaker counts as
    /// failures.
    /// </summary>
    /// <remarks>
    /// A whitelist, never "any server error". HTTP 501 is excluded because jbg-ai uses it for a
    /// route whose implementation arrives in a later change: retrying spends the budget with no
    /// possibility of success, and counting it as a health failure would open the circuit on a
    /// service that is perfectly healthy. HTTP 401 is excluded for the same reason — it is
    /// configuration, and no number of attempts fixes a mismatched secret.
    /// </remarks>
    private static bool IsRetryable(Outcome<HttpResponseMessage> outcome)
    {
        if (outcome.Exception is HttpRequestException or TimeoutRejectedException)
        {
            return true;
        }

        var status = outcome.Result?.StatusCode;
        if (status is null)
        {
            return false;
        }

        if (status == HttpStatusCode.RequestTimeout)
        {
            return true;
        }

        return (int)status >= 500 && status != HttpStatusCode.NotImplemented;
    }

    private static IServiceCollection TryAddTimeProvider(this IServiceCollection services)
    {
        if (services.All(d => d.ServiceType != typeof(TimeProvider)))
        {
            services.AddSingleton(TimeProvider.System);
        }

        return services;
    }
}
