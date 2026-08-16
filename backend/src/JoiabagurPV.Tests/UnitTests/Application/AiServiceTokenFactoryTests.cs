using System.IdentityModel.Tokens.Jwt;
using FluentAssertions;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Services;
using Microsoft.Extensions.Options;
using Microsoft.Extensions.Time.Testing;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// These tests guard a failure mode that leaves no diagnosis anywhere: jbg-ai rejects a
/// doubtful token with a 401 whose cause it is required not to disclose. An extra audience
/// claim, or a temporal claim evaluated with no clock tolerance, breaks every call and looks
/// exactly like a mistyped secret.
/// </summary>
public class AiServiceTokenFactoryTests
{
    private static readonly Guid AnyUser = Guid.NewGuid();
    private static readonly Guid AnyPointOfSale = Guid.NewGuid();
    private const string AnyRole = "Operator";
    private const string AnyTraceId = "trace-abc-123";
    private const string AnySecret = "local-dev-jwt-secret-0123456789abcdef";

    private static readonly DateTimeOffset FixedNow = new(2026, 8, 9, 10, 0, 0, TimeSpan.Zero);

    private static AiServiceTokenFactory CreateFactory(int ttlSeconds = 300)
    {
        var options = Options.Create(new AiGatewayOptions
        {
            BaseUrl = "http://localhost:8001",
            JwtSecret = AnySecret,
            TokenTtlSeconds = ttlSeconds
        });

        var timeProvider = new FakeTimeProvider(FixedNow);

        return new AiServiceTokenFactory(options, timeProvider);
    }

    private static JwtSecurityToken Decode(string token) =>
        new JwtSecurityTokenHandler().ReadJwtToken(token);

    private static AiCallScope AnyScope() =>
        AiCallScope.ForPointOfSale(AnyUser, AnyRole, AnyPointOfSale);

    [Fact]
    public void BuildToken_IncludesPosAndRoleClaims()
    {
        var token = Decode(CreateFactory().Create(AnyScope(), AnyTraceId));

        token.Payload[AiServiceTokenFactory.PointOfSaleClaim].Should().Be(AnyPointOfSale.ToString());
        token.Payload[AiServiceTokenFactory.RoleClaim].Should().Be(AnyRole);
        token.Payload[AiServiceTokenFactory.UserIdClaim].Should().Be(AnyUser.ToString());
        token.Payload[AiServiceTokenFactory.TraceIdClaim].Should().Be(AnyTraceId);
    }

    [Fact]
    public void BuildToken_UsesSnakeCaseClaimNames()
    {
        var token = Decode(CreateFactory().Create(AnyScope(), AnyTraceId));

        token.Payload.Keys.Should().Contain(["user_id", "role", "pos_id", "trace_id"]);
        token.Payload.Keys.Should().NotContain(["userId", "pointOfSaleId", "traceId", "PosId"]);
    }

    /// <summary>
    /// The decisive test. PyJWT rejects a token declaring an audience when the validator
    /// expects none, and validates `iat` and `nbf` with zero leeway. Emitting any of them
    /// breaks every call with an opaque 401.
    /// </summary>
    [Fact]
    public void BuildToken_OmitsAudienceAndIssuer()
    {
        var token = Decode(CreateFactory().Create(AnyScope(), AnyTraceId));

        token.Payload.Keys.Should().NotContain(["aud", "iss", "nbf", "iat"]);
        token.Payload.Keys.Should().BeEquivalentTo(
            ["user_id", "role", "pos_id", "trace_id", "exp"],
            "the payload must carry the four required claims plus an expiry, and nothing else");
    }

    [Fact]
    public void BuildToken_ExpiresAfterConfiguredTtl()
    {
        var token = Decode(CreateFactory(ttlSeconds: 300).Create(AnyScope(), AnyTraceId));

        var expected = FixedNow.AddSeconds(300).ToUnixTimeSeconds();

        Convert.ToInt64(token.Payload[AiServiceTokenFactory.ExpiryClaim]).Should().Be(expected);
    }

    [Fact]
    public void BuildToken_UsesHmacSha256()
    {
        var token = Decode(CreateFactory().Create(AnyScope(), AnyTraceId));

        token.Header.Alg.Should().Be("HS256");
    }

    [Fact]
    public void BuildToken_WhenTraceIdIsBlank_ThrowsArgumentException()
    {
        var act = () => CreateFactory().Create(AnyScope(), "  ");

        act.Should().Throw<ArgumentException>().WithParameterName("traceId");
    }

    /// <summary>
    /// A catalog call belongs to no point of sale, so the claim is left out rather than
    /// emitted empty. The service rejects a blank claim exactly like an absent one, but an
    /// empty string on the wire would read like a point of sale that failed to resolve
    /// instead of one that was never meant to be there.
    /// </summary>
    [Fact]
    public void BuildToken_ForCatalogScope_OmitsPosClaim()
    {
        var scope = AiCallScope.ForCatalog(Guid.NewGuid(), "Administrator");

        var token = Decode(CreateFactory().Create(scope, AnyTraceId));

        token.Payload.Keys.Should().NotContain(AiServiceTokenFactory.PointOfSaleClaim);
        token.Payload.Keys.Should().BeEquivalentTo(
            ["user_id", "role", "trace_id", "exp"],
            "a catalog token carries the three base claims plus an expiry, and nothing else");
    }
}
