using System.IdentityModel.Tokens.Jwt;
using System.Text;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using Microsoft.Extensions.Options;
using Microsoft.IdentityModel.Tokens;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Signs the internal service token for jbg-ai.
/// </summary>
/// <remarks>
/// <para>
/// Deliberately not built on <c>JwtTokenService</c>: that one signs <em>user</em> tokens with a
/// different secret, a different lifetime, different claim names and — decisively — an issuer
/// and an audience.
/// </para>
/// <para>
/// The payload is assembled by hand rather than through <c>SecurityTokenDescriptor</c> because
/// the descriptor path fills in temporal claims on its own. Three properties of the receiving
/// validator make that dangerous, and all three surface as the same undiagnosable 401:
/// </para>
/// <list type="bullet">
/// <item><description>
/// jbg-ai decodes without an expected audience. PyJWT rejects a token that <em>declares</em> an
/// audience when the validator expects none, so an <c>aud</c> claim breaks every single call.
/// </description></item>
/// <item><description>
/// PyJWT validates <c>iat</c> and <c>nbf</c> with zero clock tolerance. A couple of seconds of
/// drift between containers would make a freshly signed token look like it came from the future.
/// </description></item>
/// <item><description>
/// The rejection body is required to disclose neither the secret nor the failing step, so none
/// of the above leaves a usable trace anywhere in the stack.
/// </description></item>
/// </list>
/// <para>
/// The payload therefore contains exactly five entries: the four required claims and an expiry.
/// <c>AiServiceTokenFactoryTests</c> asserts that set exactly, so a future refactor toward the
/// descriptor API fails loudly instead of silently.
/// </para>
/// </remarks>
public class AiServiceTokenFactory : IAiServiceTokenFactory
{
    /// <summary>Claim names frozen in snake_case by the jbg-ai contract.</summary>
    public const string UserIdClaim = "user_id";

    /// <inheritdoc cref="UserIdClaim"/>
    public const string RoleClaim = "role";

    /// <inheritdoc cref="UserIdClaim"/>
    public const string PointOfSaleClaim = "pos_id";

    /// <inheritdoc cref="UserIdClaim"/>
    public const string TraceIdClaim = "trace_id";

    /// <summary>Expiry claim, the only temporal claim this factory emits.</summary>
    public const string ExpiryClaim = "exp";

    private readonly AiGatewayOptions _options;
    private readonly TimeProvider _timeProvider;
    private readonly JwtSecurityTokenHandler _handler = new();

    public AiServiceTokenFactory(IOptions<AiGatewayOptions> options, TimeProvider timeProvider)
    {
        _options = options?.Value ?? throw new ArgumentNullException(nameof(options));
        _timeProvider = timeProvider ?? throw new ArgumentNullException(nameof(timeProvider));
    }

    /// <inheritdoc/>
    public string Create(AiCallScope scope, string traceId)
    {
        ArgumentNullException.ThrowIfNull(scope);

        if (string.IsNullOrWhiteSpace(traceId))
        {
            throw new ArgumentException("A service token requires a trace id.", nameof(traceId));
        }

        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_options.JwtSecret));
        var credentials = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);

        var expiresAt = _timeProvider.GetUtcNow().AddSeconds(_options.TokenTtlSeconds);

        // Assembled explicitly: no issuer, no audience, no not-before, no issued-at.
        var payload = new JwtPayload
        {
            { UserIdClaim, scope.UserId.ToString() },
            { RoleClaim, scope.Role },
            { PointOfSaleClaim, scope.PointOfSaleId.ToString() },
            { TraceIdClaim, traceId },
            { ExpiryClaim, EpochTime.GetIntDate(expiresAt.UtcDateTime) }
        };

        var token = new JwtSecurityToken(new JwtHeader(credentials), payload);

        return _handler.WriteToken(token);
    }
}
