using System.Diagnostics;
using JoiabagurPV.Application.Interfaces;

namespace JoiabagurPV.API.Services;

/// <summary>
/// Resolves the correlation identifier of the request in flight, from the ambient
/// <see cref="Activity"/> when one exists and from the HTTP context otherwise.
/// </summary>
/// <remarks>
/// Same layering as <see cref="CurrentUserService"/>: the interface lives in the application
/// layer and the implementation here, because the value comes from the request context.
///
/// The identifier travels to jbg-ai twice — as the `trace_id` claim of the service token and
/// as a request header. The claim is what jbg-ai prefers, but a header is the only thing that
/// correlates responses it rejects before a handler ever runs, such as a 401.
/// </remarks>
public class TraceContextAccessor : ITraceContextAccessor
{
    private readonly IHttpContextAccessor _httpContextAccessor;

    public TraceContextAccessor(IHttpContextAccessor httpContextAccessor)
    {
        _httpContextAccessor = httpContextAccessor;
    }

    /// <inheritdoc/>
    public string CurrentTraceId
    {
        get
        {
            var activityId = Activity.Current?.TraceId.ToString();
            if (!string.IsNullOrWhiteSpace(activityId))
            {
                return activityId;
            }

            var contextId = _httpContextAccessor.HttpContext?.TraceIdentifier;
            if (!string.IsNullOrWhiteSpace(contextId))
            {
                return contextId;
            }

            // Background work outside a request still needs a non-empty claim.
            return Guid.NewGuid().ToString("n");
        }
    }
}
