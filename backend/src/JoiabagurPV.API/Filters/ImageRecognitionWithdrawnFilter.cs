using System.Security.Claims;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Filters;

namespace JoiabagurPV.API.Filters;

/// <summary>
/// Short-circuits image-recognition actions with HTTP 410 Gone for signed-in users.
/// </summary>
public sealed class ImageRecognitionWithdrawnFilter : IAsyncAuthorizationFilter
{
    public const string WithdrawalCode = "image_recognition_withdrawn";

    public const string WithdrawalMessageSpanish =
        "El reconocimiento de productos por foto ha sido retirado del sistema.";

    public Task OnAuthorizationAsync(AuthorizationFilterContext context)
    {
        if (!HasAuthenticatedUser(context.HttpContext.User))
        {
            return Task.CompletedTask;
        }

        context.Result = new ObjectResult(new
        {
            code = WithdrawalCode,
            message = WithdrawalMessageSpanish
        })
        {
            StatusCode = StatusCodes.Status410Gone
        };

        return Task.CompletedTask;
    }

    private static bool HasAuthenticatedUser(ClaimsPrincipal user)
    {
        if (user.Identity?.IsAuthenticated != true)
        {
            return false;
        }

        return user.Claims.Any(c =>
            c.Type == ClaimTypes.NameIdentifier
            || c.Type == "sub"
            || c.Type == ClaimTypes.Name);
    }
}
