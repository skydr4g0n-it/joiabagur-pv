namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// Health report returned by the jbg-ai service, and served on to the administrator dashboard.
/// </summary>
/// <remarks>
/// <para>
/// Every field here is deliberately non-sensitive. The response describes infrastructure, and it
/// is served to a browser: it carries no connection string, no database hostname and no fragment
/// of any credential. <see cref="Provider"/> in particular reports whether the embedding
/// credential is <em>configured</em> — never its value, and never whether the provider is
/// answering, which jbg-ai does not ask either.
/// </para>
/// <para>
/// The jbg-ai side declares this payload as an open mapping, on purpose: enriching it does not
/// move the frozen OpenAPI contract, whereas a typed response model there would. This class is
/// this side's reading of that mapping, and an unrecognised field is ignored rather than fatal.
/// </para>
/// </remarks>
public class AiHealthResponse
{
    /// <summary><c>OK</c> or <c>degraded</c>.</summary>
    public string Status { get; set; } = string.Empty;

    /// <summary>Version of the jbg-ai service that answered.</summary>
    public string Version { get; set; } = string.Empty;

    /// <summary><c>ok</c>, <c>unavailable</c>, or <c>not_configured</c>.</summary>
    /// <remarks>
    /// The name of the database, its host and its credentials are not part of this: only whether
    /// the service can reach it.
    /// </remarks>
    public string Database { get; set; } = string.Empty;

    /// <summary>State of the vector index.</summary>
    public AiHealthIndex Index { get; set; } = new();

    /// <summary><c>configured</c> or <c>missing</c> — presence of the credential, never its value.</summary>
    public string Provider { get; set; } = string.Empty;
}

/// <summary>
/// Vector index section of the health report.
/// </summary>
public class AiHealthIndex
{
    /// <summary>Documents currently indexed. Zero means an empty environment, not a broken one.</summary>
    public int Documents { get; set; }

    /// <summary>
    /// Embedding model recorded on the index rows, or <c>null</c> when the index is empty.
    /// </summary>
    public string? Model { get; set; }

    /// <summary>Embedding model the service is configured to query with.</summary>
    public string? ConfiguredModel { get; set; }

    /// <summary><c>ok</c>, <c>model_mismatch</c>, or <c>unavailable</c>.</summary>
    /// <remarks>
    /// <c>model_mismatch</c> is the quietest failure the deployment has: queries embedded with one
    /// model against documents embedded with another compare two different vector spaces, and the
    /// result is noise returned with a 200 and no log line. It is reported explicitly here so the
    /// dashboard can show it as an error rather than leaving somebody to infer it.
    /// </remarks>
    public string Status { get; set; } = string.Empty;
}
