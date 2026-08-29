namespace JoiabagurPV.Application.Configuration;

/// <summary>
/// Configuration for the outbound integration with the jbg-ai service.
/// Bound from the "AiGateway" section and validated at application start.
/// </summary>
/// <remarks>
/// The base address differs by environment and neither value is the intuitive one.
/// In development the .NET API runs on the host while jbg-ai runs in Compose, so the
/// API only sees the published port (8001). In production both containers live on the
/// same host and the address is the container name, which requires the user-defined
/// Docker network that C17 must create: on the default bridge network Docker does not
/// resolve container names.
/// </remarks>
public class AiGatewayOptions
{
    /// <summary>Configuration section name.</summary>
    public const string SectionName = "AiGateway";

    /// <summary>Minimum secret length accepted for HS256 signing.</summary>
    public const int MinimumSecretLength = 32;

    /// <summary>Base address of the jbg-ai service. Must be an absolute URI.</summary>
    public string BaseUrl { get; set; } = string.Empty;

    /// <summary>
    /// HS256 secret shared with jbg-ai. Must match the service's JWT_SECRET literally:
    /// any divergence produces a 401 whose cause the service is required not to disclose.
    /// Distinct from Jwt:SecretKey, which signs user tokens.
    /// </summary>
    public string JwtSecret { get; set; } = string.Empty;

    /// <summary>Lifetime of the internal service token, in seconds.</summary>
    public int TokenTtlSeconds { get; set; } = 300;

    /// <summary>Time budget for a retrieval call, in milliseconds.</summary>
    /// <remarks>
    /// <para>
    /// The design specifies 800 ms (§6.4). Raised to 2500 ms during C16 because measurement
    /// against the seeded world with real retrieval showed the assisted path degrading on
    /// <em>every</em> search at 800 ms: the AI service builds its embedding client per request,
    /// so the in-memory cache never hits and each search pays a full cold round trip to the
    /// embedding provider.
    /// </para>
    /// <para>
    /// <strong>Temporary.</strong> When that client becomes a singleton — the change that already
    /// works inside the retrieval package — measure again and put this back to 800 ms. A budget
    /// this loose stops protecting the search from a slow provider, and with the single retry it
    /// turns the worst case into roughly five seconds of an operator waiting for a degraded
    /// answer.
    /// </para>
    /// </remarks>
    public int RetrievalTimeoutMs { get; set; } = 2500;

    /// <summary>
    /// Time budget for a generative call, in milliseconds. Reserved for the assist client
    /// that C34 will register with its own circuit breaker.
    /// </summary>
    public int AssistTimeoutMs { get; set; } = 5000;

    /// <summary>
    /// Time budget for a catalog enrichment batch, in milliseconds.
    /// </summary>
    /// <remarks>
    /// Two orders of magnitude above the retrieval budget, and that is the point: a batch of up
    /// to fifty products through a structured-extraction model has nothing in common with a
    /// vector lookup. Nobody is waiting on this call the way an operator waits on a search — it
    /// is an administration action — so the budget is generous enough that a slow provider does
    /// not turn into a half-enriched catalog.
    /// </remarks>
    public int EnrichTimeoutMs { get; set; } = 120_000;

    /// <summary>Whether the gateway client is registered at all.</summary>
    public bool Enabled { get; set; } = true;

    /// <summary>Failure ratio that opens the circuit breaker.</summary>
    public double BreakerFailureRatio { get; set; } = 0.5;

    /// <summary>Minimum number of calls in the sampling window before the breaker can open.</summary>
    public int BreakerMinimumThroughput { get; set; } = 4;

    /// <summary>Sampling window of the circuit breaker, in seconds.</summary>
    public int BreakerSamplingDurationSeconds { get; set; } = 30;

    /// <summary>How long the circuit stays open before probing again, in seconds.</summary>
    public int BreakerBreakDurationSeconds { get; set; } = 15;
}
