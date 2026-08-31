using System.Net;
using System.Text.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Tests.TestHelpers;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// The family-suggestion side of the gateway: mapping that keeps both kinds of refusal, a scope
/// that must be the catalog one, and failure modes a caller can branch on without a fallback.
/// </summary>
public class AiGatewayFamilySuggestionTests
{
    private const string SuccessBody = """
        {
          "proposals": [
            {
              "root": "anillo erizo de mar",
              "suggested_name": "Anillo erizo de mar",
              "piece_type": "anillo",
              "members": [
                {
                  "product_id": "11111111-1111-1111-1111-111111111111",
                  "sku": "SKU-1",
                  "name": "Anillo erizo de mar S",
                  "variant_label": "S",
                  "position": 0,
                  "flagged_for_review": false,
                  "review_reason": null,
                  "margin": null
                },
                {
                  "product_id": "22222222-2222-2222-2222-222222222222",
                  "sku": "SKU-2",
                  "name": "Anillo erizo de mar",
                  "variant_label": null,
                  "position": 1,
                  "flagged_for_review": true,
                  "review_reason": "closer_to_another_family",
                  "margin": 0.12
                }
              ]
            }
          ],
          "rejected_groups": [
            {
              "root": "encargos",
              "piece_type": "collar",
              "reason": "root_too_short",
              "product_names": ["Encargos Oro", "Encargos plata"]
            }
          ],
          "excluded_products": [
            {
              "product_id": "33333333-3333-3333-3333-333333333333",
              "sku": "SKU-3",
              "name": "Vela Cerámica grande",
              "reason": "no_piece_type"
            }
          ],
          "already_in_family_count": 7,
          "trace_id": "trace-test-c18a"
        }
        """;

    private static AiFamilySuggestRequest AnyRequest() => new();

    private static AiCallScope CatalogScope() =>
        AiCallScope.ForCatalog(Guid.NewGuid(), "Administrator");

    [Fact]
    public async Task SuggestFamiliesAsync_WhenServiceReturns200_SurfacesAllThreeListsWithoutTruncating()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var response = await provider.Client().SuggestFamiliesAsync(AnyRequest(), CatalogScope());

        response.Proposals.Should().HaveCount(1);
        response.Proposals[0].Members.Should().HaveCount(2, "no member is dropped in mapping");
        response.RejectedGroups.Should().ContainSingle()
            .Which.Reason.Should().Be("root_too_short");
        response.ExcludedProducts.Should().ContainSingle()
            .Which.Reason.Should().Be("no_piece_type");
        response.AlreadyInFamilyCount.Should().Be(7);
    }

    [Fact]
    public async Task SuggestFamiliesAsync_KeepsMemberOrderAndTheReviewMark()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var members = (await provider.Client().SuggestFamiliesAsync(AnyRequest(), CatalogScope()))
            .Proposals[0].Members;

        members.Select(member => member.Position).Should().Equal([0, 1],
            "deciding what is worth looking at belongs to the administrator, not the transport");
        members[1].FlaggedForReview.Should().BeTrue();
        members[1].Margin.Should().BeApproximately(0.12, 0.0001);
        members[1].ReviewReason.Should().Be("closer_to_another_family");
    }

    /// <summary>
    /// Null is the base piece of a family — a legitimate variant value, not a missing one.
    /// </summary>
    [Fact]
    public async Task SuggestFamiliesAsync_MapsAnAbsentVariantToNullAndNotToEmptyString()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var members = (await provider.Client().SuggestFamiliesAsync(AnyRequest(), CatalogScope()))
            .Proposals[0].Members;

        members[0].VariantLabel.Should().Be("S");
        members[1].VariantLabel.Should().BeNull(
            "the contract guarantees an explicit null, and erasing it would lose the difference "
            + "between 'this is the plain one' and 'nobody has decided yet'");
    }

    /// <summary>
    /// Asserted on the serializer rather than on the sent request: the request content is disposed
    /// once the call returns, and the naming policy is the whole of what this pins.
    /// </summary>
    [Fact]
    public void FamilySuggestRequest_SerializesInSnakeCase()
    {
        var json = JsonSerializer.Serialize(
            new AiFamilySuggestRequest { PieceType = "anillo", MaxProposals = 10 },
            AiGatewaySerialization.Options);

        var sent = JsonDocument.Parse(json).RootElement;

        sent.TryGetProperty("piece_type", out _).Should().BeTrue();
        sent.TryGetProperty("max_proposals", out _).Should().BeTrue(
            "the wire name is max_proposals; a C# property called MaxProposalsRequested would "
            + "have serialized as max_proposals_requested and arrived as the contract default");
        sent.TryGetProperty("pieceType", out _).Should().BeFalse();
    }

    [Fact]
    public void FamilySuggestResponse_DeserializesTheSnakeCaseContract()
    {
        var response = JsonSerializer.Deserialize<AiFamilySuggestResponse>(
            SuccessBody, AiGatewaySerialization.Options);

        response!.Proposals[0].SuggestedName.Should().Be("Anillo erizo de mar");
        response.Proposals[0].Members[1].FlaggedForReview.Should().BeTrue();
        response.ExcludedProducts[0].Reason.Should().Be("no_piece_type");
        response.AlreadyInFamilyCount.Should().Be(7);
    }

    [Fact]
    public async Task SuggestFamiliesAsync_WhenRouteIsNotImplemented_RaisesTheNotImplementedError()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.NotImplemented, "{}");
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().SuggestFamiliesAsync(AnyRequest(), CatalogScope());

        await act.Should().ThrowAsync<AiNotImplementedException>();
    }

    [Fact]
    public async Task SuggestFamiliesAsync_WhenServiceFails_RaisesUnavailableAndNotNotImplemented()
    {
        var handler = new FakeHttpMessageHandler()
            .EnqueueResponse(HttpStatusCode.InternalServerError, "{}")
            .EnqueueResponse(HttpStatusCode.InternalServerError, "{}")
            .EnqueueResponse(HttpStatusCode.InternalServerError, "{}");
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().SuggestFamiliesAsync(AnyRequest(), CatalogScope());

        await act.Should().ThrowAsync<AiUnavailableException>();
    }

    [Fact]
    public async Task SuggestFamiliesAsync_WhenCredentialsAreRejected_RaisesTheConfigurationError()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.Unauthorized, "{}");
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().SuggestFamiliesAsync(AnyRequest(), CatalogScope());

        await act.Should().ThrowAsync<AiGatewayConfigurationException>();
    }

    /// <summary>
    /// There is no degraded mode. Unlike search, which drops to the lexical index, a partial
    /// grouping would mean inventing catalog structure.
    /// </summary>
    [Fact]
    public async Task SuggestFamiliesAsync_ProducesNoProposalsWhenItFails()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.NotImplemented, "{}");
        await using var provider = AiGatewayTestHost.Build(handler);

        AiFamilySuggestResponse? captured = null;
        try
        {
            captured = await provider.Client().SuggestFamiliesAsync(AnyRequest(), CatalogScope());
        }
        catch (AiNotImplementedException)
        {
            // expected
        }

        captured.Should().BeNull("a failure yields no proposals at all, never a synthesised fallback");
    }

    [Fact]
    public async Task SuggestFamiliesAsync_RejectsAPointOfSaleScope()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().SuggestFamiliesAsync(
            AnyRequest(),
            AiCallScope.ForPointOfSale(Guid.NewGuid(), "Administrator", Guid.NewGuid()));

        await act.Should().ThrowAsync<ArgumentException>()
            .WithMessage("*catalog scope*", "grouping the catalogue belongs to no point of sale");
    }

    [Fact]
    public async Task SuggestFamiliesAsync_RejectsAMaxProposalsOutsideTheContract()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().SuggestFamiliesAsync(
            new AiFamilySuggestRequest { MaxProposals = 0 }, CatalogScope());

        await act.Should().ThrowAsync<ArgumentException>(
            "rejecting it here turns a round trip into an immediate, explainable answer");
    }
}
