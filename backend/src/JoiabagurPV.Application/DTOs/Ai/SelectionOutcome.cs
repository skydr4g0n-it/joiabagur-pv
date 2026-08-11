namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// How an attempt to record a selection ended.
/// </summary>
/// <remarks>
/// An explicit outcome rather than exceptions, because there are two distinct rejections and
/// neither is exceptional: an event that does not exist and an event that belongs to somebody
/// else are both ordinary answers the endpoint has to map to different status codes.
/// </remarks>
public enum SelectionOutcome
{
    /// <summary>The selection was persisted.</summary>
    Recorded,

    /// <summary>No search event exists with that identifier.</summary>
    EventNotFound,

    /// <summary>The event belongs to another user.</summary>
    NotOwner
}
