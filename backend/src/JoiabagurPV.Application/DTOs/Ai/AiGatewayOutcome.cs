namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// Classification of a failed gateway call, emitted as the <c>outcome</c> field of the
/// failure log event so failures can be counted by cause instead of by message text.
/// </summary>
public enum AiGatewayOutcome
{
    /// <summary>The service did not answer within the time budget.</summary>
    Timeout,

    /// <summary>The circuit was open; no request was issued.</summary>
    CircuitOpen,

    /// <summary>The route is contracted but has no implementation yet.</summary>
    NotImplemented,

    /// <summary>The service rejected the credentials. On this side, misconfiguration.</summary>
    Unauthorized,

    /// <summary>The service answered with a server error.</summary>
    ServerError,

    /// <summary>The service could not be reached at all.</summary>
    Transport
}
