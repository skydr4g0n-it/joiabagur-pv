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

    /// <summary>
    /// Reference instant the POS sales windows are counted against. Null — the default —
    /// means the wall clock, so an unset configuration preserves the behaviour every
    /// deployment had before this option existed.
    /// </summary>
    /// <remarks>
    /// It exists for reproducibility before it exists for the dataset: a ranking that reads
    /// <c>now()</c> yields different aggregates on different days for the same configuration
    /// and seed, so the ablation table C24 requires was never reproducible. The synthetic
    /// world's fixed horizon only makes that urgent.
    /// <para>
    /// Never read this property directly — read <see cref="SalesAsOfUtc"/>. Configuration
    /// binds an ISO-8601 string through <see cref="DateTime"/>'s type converter, which turns
    /// a trailing <c>Z</c> into a <see cref="DateTimeKind.Local"/> value; only the normalised
    /// property is the instant that was meant. A value carrying no offset at all binds as
    /// <see cref="DateTimeKind.Unspecified"/> and is rejected at start-up rather than read
    /// silently as local time, because a windowed figure whose clock is ambiguous is the very
    /// thing this option was added to remove.
    /// </para>
    /// </remarks>
    public DateTime? SalesAsOf { get; set; }

    /// <summary>
    /// The configured reference instant as UTC, or null when the wall clock governs.
    /// </summary>
    public DateTime? SalesAsOfUtc => SalesAsOf?.ToUniversalTime();
}
