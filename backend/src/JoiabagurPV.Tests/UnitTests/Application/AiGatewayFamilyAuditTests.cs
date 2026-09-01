using System.Net;
using System.Text.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Tests.TestHelpers;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// The family-audit side of the gateway.
/// </summary>
/// <remarks>
/// <para>
/// Written during the QA pass of C18b, which found the audit covered only through the controller.
/// That is the same hole C18a's QA found on the suggestion side, and it matters for the same
/// reason: an integration test exercises the client through a double that already speaks in mapped
/// types, so nothing there would notice a wire name that stopped matching the frozen contract or a
/// candidate field silently dropped in mapping.
/// </para>
/// <para>
/// The failure modes are the point of the file rather than an afterthought. On this route a
/// mapping that turned a failure into an empty result would be read as "the catalogue is clean",
/// which is the one conclusion the whole change exists to support with evidence.
/// </para>
/// </remarks>
public class AiGatewayFamilyAuditTests
{
    private const string SuccessBody = """
        {
          "flagged_members": [
            {
              "product_id": "11111111-1111-1111-1111-111111111111",
              "sku": "SKU-1",
              "name": "Colgante estrella de mar M oro",
              "variant_label": "M oro",
              "family_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              "family_name": "Colgante estrella de mar",
              "margin": 0.147,
              "stranger_family_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
              "reason": "closer_to_another_family"
            },
            {
              "product_id": "22222222-2222-2222-2222-222222222222",
              "sku": "SKU-2",
              "name": "Colgante estrella de mar",
              "variant_label": null,
              "family_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              "family_name": "Colgante estrella de mar",
              "margin": 0.051,
              "stranger_family_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
              "reason": "closer_to_another_family"
            }
          ],
          "orphan_candidates": [
            {
              "product_id": "33333333-3333-3333-3333-333333333333",
              "sku": "SKU-3",
              "name": "Pendientes botón erizo de mar S dorado",
              "piece_type": "pendientes",
              "data_origin": "real",
              "family_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
              "family_name": "Pendientes boton erizo de mar",
              "similarity": 0.887,
              "worst_sibling": 0.778,
              "margin": 0.109,
              "purity": 4
            },
            {
              "product_id": "44444444-4444-4444-4444-444444444444",
              "sku": "SKU-4",
              "name": "Colgante mejillón plata L",
              "piece_type": "colgante",
              "data_origin": "synthetic",
              "family_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              "family_name": "Colgante estrella de mar",
              "similarity": 0.828,
              "worst_sibling": 0.778,
              "margin": 0.050,
              "purity": 0
            }
          ],
          "rejected_groups": [
            {
              "root": "cadena",
              "piece_type": "cadena",
              "reason": "bare_piece_type_root",
              "product_names": ["Cadena oro", "Cadena plata"]
            }
          ],
          "excluded_products": [
            {
              "product_id": "55555555-5555-5555-5555-555555555555",
              "sku": "SKU-5",
              "name": "Vela Cerámica grande",
              "reason": "no_piece_type"
            }
          ],
          "families_reviewed_count": 156,
          "members_examined_count": 486,
          "trace_id": "trace-test-c18b"
        }
        """;

    private static AiFamilyAuditRequest AnyRequest() => new();

    private static AiCallScope CatalogScope() =>
        AiCallScope.ForCatalog(Guid.NewGuid(), "Administrator");

    // ── Both lists are surfaced without truncation ──────────────────────────────────────────

    [Fact]
    public async Task AuditFamiliesAsync_WhenServiceReturns200_SurfacesBothListsWithoutTruncating()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var response = await provider.Client().AuditFamiliesAsync(AnyRequest(), CatalogScope());

        response.FlaggedMembers.Should().HaveCount(2, "no flagged member is dropped in mapping");
        response.OrphanCandidates.Should().HaveCount(2, "no candidate is dropped in mapping");
        response.RejectedGroups.Should().ContainSingle()
            .Which.Reason.Should().Be("bare_piece_type_root");
        response.ExcludedProducts.Should().ContainSingle()
            .Which.Reason.Should().Be("no_piece_type");
        response.FamiliesReviewedCount.Should().Be(156);
        response.MembersExaminedCount.Should().Be(486);
    }

    /// <summary>
    /// The order is the service's ranking, and re-sorting it here would quietly replace the
    /// ranking a reviewer is reading with the transport's opinion.
    /// </summary>
    [Fact]
    public async Task AuditFamiliesAsync_KeepsTheOrderReceived()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var response = await provider.Client().AuditFamiliesAsync(AnyRequest(), CatalogScope());

        response.FlaggedMembers.Select(member => member.Sku).Should().Equal(["SKU-1", "SKU-2"]);
        response.OrphanCandidates.Select(candidate => candidate.Sku).Should().Equal(["SKU-3", "SKU-4"]);
    }

    /// <summary>
    /// A synthetic candidate with purity zero is the shape most tempting to filter out, and the one
    /// the spec names explicitly: deciding what deserves attention is the administrator's.
    /// </summary>
    [Fact]
    public async Task AuditFamiliesAsync_DoesNotDropACandidateForItsOriginOrItsPurity()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var response = await provider.Client().AuditFamiliesAsync(AnyRequest(), CatalogScope());

        response.OrphanCandidates.Should().Contain(candidate =>
            candidate.Sku == "SKU-4" && candidate.DataOrigin == "synthetic" && candidate.Purity == 0);
    }

    // ── The evidence a reviewer judges by survives the mapping ──────────────────────────────

    [Fact]
    public async Task AuditFamiliesAsync_KeepsEveryFieldACandidateIsJudgedBy()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var candidate = (await provider.Client().AuditFamiliesAsync(AnyRequest(), CatalogScope()))
            .OrphanCandidates[0];

        candidate.Similarity.Should().BeApproximately(0.887, 0.0001);
        candidate.WorstSibling.Should().BeApproximately(0.778, 0.0001);
        candidate.Margin.Should().BeApproximately(0.109, 0.0001);
        candidate.DataOrigin.Should().Be("real");
        candidate.Purity.Should().Be(4);
        candidate.FamilyName.Should().Be("Pendientes boton erizo de mar",
            "the reviewer judges against a family by its name, not by a bare identifier");
    }

    [Fact]
    public async Task AuditFamiliesAsync_KeepsTheMarginAndTheStrangerOfAFlaggedMember()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var flagged = (await provider.Client().AuditFamiliesAsync(AnyRequest(), CatalogScope()))
            .FlaggedMembers[0];

        flagged.Margin.Should().BeApproximately(0.147, 0.0001);
        flagged.StrangerFamilyId.Should().Be("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "the product that beat the worst sibling is half of why the flag exists");
        flagged.Reason.Should().Be("closer_to_another_family");
    }

    /// <summary>
    /// Null is the base piece of a family — a legitimate variant value, not a missing one. The same
    /// distinction the suggestion mapping pins, on the route that surfaces existing members.
    /// </summary>
    [Fact]
    public async Task AuditFamiliesAsync_MapsAnAbsentVariantToNullAndNotToEmptyString()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var flagged = (await provider.Client().AuditFamiliesAsync(AnyRequest(), CatalogScope()))
            .FlaggedMembers;

        flagged[0].VariantLabel.Should().Be("M oro");
        flagged[1].VariantLabel.Should().BeNull();
    }

    // ── Wire names follow the frozen contract ───────────────────────────────────────────────

    /// <summary>
    /// Asserted on the serializer rather than on the sent request: the request content is disposed
    /// once the call returns, and the naming policy is the whole of what this pins.
    /// </summary>
    [Fact]
    public void FamilyAuditRequest_SerializesInSnakeCase()
    {
        var json = JsonSerializer.Serialize(
            new AiFamilyAuditRequest { PieceType = "anillo", VetoMargin = 0.05, OrphanMargin = 0, MaxOrphans = 40 },
            AiGatewaySerialization.Options);

        var sent = JsonDocument.Parse(json).RootElement;

        sent.TryGetProperty("piece_type", out _).Should().BeTrue();
        sent.TryGetProperty("veto_margin", out _).Should().BeTrue();
        sent.TryGetProperty("orphan_margin", out _).Should().BeTrue();
        sent.TryGetProperty("max_orphans", out _).Should().BeTrue();
        sent.TryGetProperty("judged_pairs", out _).Should().BeTrue();
        sent.TryGetProperty("pieceType", out _).Should().BeFalse();
    }

    /// <summary>
    /// The pairs the backend already holds a verdict for. The service stores none of its own, so a
    /// pair that does not travel is a question the administrator is asked twice.
    /// </summary>
    [Fact]
    public void FamilyAuditRequest_SerializesTheJudgedPairsWithContractNames()
    {
        var request = new AiFamilyAuditRequest
        {
            JudgedPairs =
            [
                new AiJudgedPair
                {
                    ProductId = "11111111-1111-1111-1111-111111111111",
                    FamilyId = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
                }
            ]
        };

        var pair = JsonDocument.Parse(JsonSerializer.Serialize(request, AiGatewaySerialization.Options))
            .RootElement.GetProperty("judged_pairs")[0];

        pair.GetProperty("product_id").GetString().Should().Be("11111111-1111-1111-1111-111111111111");
        pair.GetProperty("family_id").GetString().Should().Be("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    }

    [Fact]
    public void FamilyAuditResponse_DeserializesTheSnakeCaseContract()
    {
        var response = JsonSerializer.Deserialize<AiFamilyAuditResponse>(
            SuccessBody, AiGatewaySerialization.Options);

        response!.FlaggedMembers[0].StrangerFamilyId.Should()
            .Be("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
        response.OrphanCandidates[0].WorstSibling.Should().BeApproximately(0.778, 0.0001);
        response.OrphanCandidates[0].DataOrigin.Should().Be("real");
        response.FamiliesReviewedCount.Should().Be(156);
        response.MembersExaminedCount.Should().Be(486);
    }

    // ── An unreachable dependency is not an empty audit ─────────────────────────────────────

    [Fact]
    public async Task AuditFamiliesAsync_WhenServiceFails_RaisesUnavailableAndNeverAnEmptyAudit()
    {
        var handler = new FakeHttpMessageHandler()
            .EnqueueResponse(HttpStatusCode.ServiceUnavailable, "{}")
            .EnqueueResponse(HttpStatusCode.ServiceUnavailable, "{}")
            .EnqueueResponse(HttpStatusCode.ServiceUnavailable, "{}");
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().AuditFamiliesAsync(AnyRequest(), CatalogScope());

        await act.Should().ThrowAsync<AiUnavailableException>();
    }

    /// <summary>
    /// The failure mode this route exists to avoid: a 200 carrying nothing is indistinguishable
    /// from a clean catalogue, and only one of the two is true.
    /// </summary>
    [Fact]
    public async Task AuditFamiliesAsync_WhenBodyIsEmpty_RaisesRatherThanReturningNoFindings()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, "null");
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().AuditFamiliesAsync(AnyRequest(), CatalogScope());

        await act.Should().ThrowAsync<AiUnavailableException>()
            .WithMessage("*empty audit body*");
    }

    [Fact]
    public async Task AuditFamiliesAsync_WhenTransportFails_RaisesUnavailable()
    {
        var handler = new FakeHttpMessageHandler()
            .EnqueueTransportFailure()
            .EnqueueTransportFailure()
            .EnqueueTransportFailure();
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().AuditFamiliesAsync(AnyRequest(), CatalogScope());

        await act.Should().ThrowAsync<AiUnavailableException>();
    }

    // ── A refused request is distinguishable from an unavailable service ────────────────────

    [Fact]
    public async Task AuditFamiliesAsync_WhenRouteIsNotImplemented_RaisesTheNotImplementedError()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.NotImplemented, "{}");
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().AuditFamiliesAsync(AnyRequest(), CatalogScope());

        await act.Should().ThrowAsync<AiNotImplementedException>();
    }

    [Fact]
    public async Task AuditFamiliesAsync_WhenCredentialsAreRejected_RaisesTheConfigurationError()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.Unauthorized, "{}");
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().AuditFamiliesAsync(AnyRequest(), CatalogScope());

        await act.Should().ThrowAsync<AiGatewayConfigurationException>();
    }

    /// <summary>
    /// An invalid request is refused <em>before</em> it is sent, which is a stronger guarantee than
    /// telling a refusal apart after the fact: the caller gets an <see cref="ArgumentException"/>
    /// and the service is never asked. It is also the only way the two are distinguishable by
    /// type — a 4xx the service itself issues is translated, like any other non-success status,
    /// into <see cref="AiUnavailableException"/> carrying the code in its message. That collapse
    /// is shared by every route on this client and is not C18b's to change.
    /// </summary>
    [Fact]
    public async Task AuditFamiliesAsync_RefusesAnInvalidRequestWithoutCallingTheService()
    {
        var handler = new FakeHttpMessageHandler();
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().AuditFamiliesAsync(
            new AiFamilyAuditRequest { MaxOrphans = AiFamilyAuditRequest.MaxOrphansLimit + 1 },
            CatalogScope());

        await act.Should().ThrowAsync<ArgumentException>().WithMessage("*max_orphans*");
        handler.RequestCount.Should().Be(0, "a request the contract cannot accept is never sent");
    }

    [Fact]
    public async Task AuditFamiliesAsync_RejectsAPointOfSaleScope()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().AuditFamiliesAsync(
            AnyRequest(),
            AiCallScope.ForPointOfSale(Guid.NewGuid(), "Administrator", Guid.NewGuid()));

        await act.Should().ThrowAsync<ArgumentException>()
            .WithMessage("*catalog scope*", "auditing the catalogue's families belongs to no point of sale");
        handler.RequestCount.Should().Be(0);
    }

    // ── A failed audit changes nothing ──────────────────────────────────────────────────────

    /// <summary>
    /// There is no degraded mode. A partial audit would mean inventing an opinion about catalogue
    /// structure, and an empty one would be read as an all-clear.
    /// </summary>
    [Fact]
    public async Task AuditFamiliesAsync_ProducesNoAuditWhenItFails()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.NotImplemented, "{}");
        await using var provider = AiGatewayTestHost.Build(handler);

        AiFamilyAuditResponse? captured = null;
        try
        {
            captured = await provider.Client().AuditFamiliesAsync(AnyRequest(), CatalogScope());
        }
        catch (AiNotImplementedException)
        {
            // expected
        }

        captured.Should().BeNull("a failure yields no audit at all, never a synthesised empty one");
    }
}
