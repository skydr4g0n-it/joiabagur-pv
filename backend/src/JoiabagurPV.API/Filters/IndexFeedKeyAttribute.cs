using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Filters;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace JoiabagurPV.API.Filters;

/// <summary>
/// Accepts <c>X-Index-Feed-Key</c> against the configured secrets. Not a JWT scheme: a user
/// token, an access-token cookie or a C03 token do not authenticate this filter.
/// </summary>
/// <remarks>
/// The header value is never written to logs. A missing or distinct key is 401, not 403:
/// this scheme has not identified a user.
/// </remarks>
[AttributeUsage(AttributeTargets.Class | AttributeTargets.Method)]
public sealed class IndexFeedKeyAttribute : Attribute, IAsyncActionFilter
{
    /// <inheritdoc/>
    public Task OnActionExecutionAsync(ActionExecutingContext context, ActionExecutionDelegate next)
    {
        var options = context.HttpContext.RequestServices
            .GetRequiredService<IOptions<IndexFeedOptions>>()
            .Value;

        var provided = context.HttpContext.Request.Headers[IndexFeedOptions.HeaderName].ToString();
        if (string.IsNullOrEmpty(provided))
        {
            provided = null;
        }

        if (!IndexFeedKeyComparer.Matches(provided, options.ApiKey, options.ApiKeyPrevious))
        {
            context.Result = new UnauthorizedResult();
            return Task.CompletedTask;
        }

        return next();
    }
}
