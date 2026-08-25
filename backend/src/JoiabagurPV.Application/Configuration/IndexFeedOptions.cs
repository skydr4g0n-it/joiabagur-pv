namespace JoiabagurPV.Application.Configuration;

/// <summary>
/// Service credential for the indexing feeds. Bound from the "IndexFeed" section and
/// validated at application start.
/// </summary>
/// <remarks>
/// Distinct from <c>Jwt:SecretKey</c> (user tokens) and <c>AiGateway:JwtSecret</c> (tokens
/// .NET signs toward Python). Reusing either would let a logged-in administrator or a C03
/// token open the feed. Production injects the value from SSM in C17; this change only
/// ships a local placeholder.
/// </remarks>
public class IndexFeedOptions
{
    /// <summary>Configuration section name.</summary>
    public const string SectionName = "IndexFeed";

    /// <summary>HTTP header the feeds accept.</summary>
    public const string HeaderName = "X-Index-Feed-Key";

    /// <summary>
    /// Minimum secret length, matching <see cref="AiGatewayOptions.MinimumSecretLength"/>.
    /// </summary>
    public const int MinimumSecretLength = AiGatewayOptions.MinimumSecretLength;

    /// <summary>Current API key. Required; at least <see cref="MinimumSecretLength"/> characters.</summary>
    public string ApiKey { get; set; } = string.Empty;

    /// <summary>
    /// Previous API key, accepted during rotation. Empty or whitespace means unset.
    /// When set it must also meet <see cref="MinimumSecretLength"/>.
    /// </summary>
    public string? ApiKeyPrevious { get; set; }
}
