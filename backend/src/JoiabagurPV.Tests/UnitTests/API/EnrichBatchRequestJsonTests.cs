using System.Text.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Tests.UnitTests.API;

/// <summary>
/// The AutoBulk runbook sends <c>"reviewMode":"AutoBulk"</c>. Without a string
/// enum converter the whole body failed to bind and FluentValidation threw.
/// </summary>
public class EnrichBatchRequestJsonTests
{
    /// <summary>
    /// Mirrors API <c>AddJsonOptions</c>: camelCase naming. The converter lives
    /// on <see cref="ProfileReviewMode"/>, not on these options, so other
    /// controllers keep emitting numeric enums.
    /// </summary>
    private static readonly JsonSerializerOptions ApiJson = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };

    [Fact]
    public void Deserializes_AutoBulk_FromMemberName()
    {
        var request = JsonSerializer.Deserialize<EnrichBatchRequest>(
            """{"productIds":["00000000-0000-0000-0000-000000000001"],"reviewMode":"AutoBulk","force":false}""",
            ApiJson);

        request.Should().NotBeNull();
        request!.ReviewMode.Should().Be(ProfileReviewMode.AutoBulk);
        request.Force.Should().BeFalse();
        request.ProductIds.Should().ContainSingle();
    }

    [Fact]
    public void Deserializes_AutoBulk_FromNumericValue()
    {
        var request = JsonSerializer.Deserialize<EnrichBatchRequest>(
            """{"productIds":["00000000-0000-0000-0000-000000000001"],"reviewMode":2,"force":false}""",
            ApiJson);

        request.Should().NotBeNull();
        request!.ReviewMode.Should().Be(ProfileReviewMode.AutoBulk);
    }

    [Fact]
    public void Deserializes_Routed_FromMemberName()
    {
        var request = JsonSerializer.Deserialize<EnrichBatchRequest>(
            """{"productIds":["00000000-0000-0000-0000-000000000001"],"reviewMode":"Routed"}""",
            ApiJson);

        request.Should().NotBeNull();
        request!.ReviewMode.Should().Be(ProfileReviewMode.Routed);
    }
}
