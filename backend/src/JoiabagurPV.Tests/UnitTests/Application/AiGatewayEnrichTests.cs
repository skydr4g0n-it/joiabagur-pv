using System.Net;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Application.Services;
using JoiabagurPV.Tests.TestHelpers;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// The enrichment side of the gateway: mapping that keeps provenance, a scope that must be the
/// catalog one, and a resilience family isolated from retrieval.
/// </summary>
public class AiGatewayEnrichTests
{
    private const string SuccessBody = """
        {
          "profiles": [
            {
              "product_id": "P-0001",
              "sku": "JBG-0001",
              "title": {"value": "Anillo erizo", "confidence": 0.81, "source": "inferred"},
              "description": null,
              "piece_type": {"value": "anillo", "confidence": 0.88, "source": "inferred"},
              "materials": {"value": ["plata", "baño de oro"], "confidence": 0.72, "source": "inferred"},
              "stone_type": null,
              "size_label": {"value": "M", "confidence": 1.0, "source": "rule"},
              "color_tags": {"value": ["dorado"], "confidence": 0.92, "source": "inferred"},
              "style_tags": {"value": ["marino"], "confidence": 0.45, "source": "inferred"},
              "occasion_tags": {"value": [], "confidence": 0.3, "source": "inferred"},
              "family_id": {"value": "F-000", "confidence": 0.55, "source": "inferred"},
              "variant_label": null,
              "warnings": []
            }
          ],
          "usage": {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160, "model": "test-model"},
          "prompt_version": "v1",
          "trace_id": "trace-test-0001"
        }
        """;

    private static AiEnrichRequest AnyRequest() => new()
    {
        Products =
        [
            new AiEnrichProductInput { ProductId = "P-0001", Sku = "JBG-0001", Name = "Anillo erizo" }
        ]
    };

    private static AiCallScope CatalogScope() =>
        AiCallScope.ForCatalog(Guid.NewGuid(), "Administrator");

    [Fact]
    public async Task EnrichAsync_WhenServiceReturns200_MapsConfidenceAndSourcePerField()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var response = await provider.Client().EnrichAsync(AnyRequest(), CatalogScope());

        var profile = response.Profiles.Single();
        profile.ProductId.Should().Be("P-0001");
        profile.Materials.Value.Should().Equal(["plata", "baño de oro"]);
        profile.Materials.Confidence.Should().Be(0.72);
        profile.Materials.Source.Should().Be(AiFieldSource.Inferred);

        // The distinction the whole review policy rests on: same kind of field, different origin.
        profile.SizeLabel!.Source.Should().Be(AiFieldSource.Rule);
        profile.PieceType!.Source.Should().Be(AiFieldSource.Inferred);

        response.PromptVersion.Should().Be("v1");
        response.Usage.TotalTokens.Should().Be(160);
    }

    [Fact]
    public async Task EnrichAsync_WhenFieldIsAbsent_MapsToNullWithoutSubstituting()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var profile = (await provider.Client().EnrichAsync(AnyRequest(), CatalogScope())).Profiles.Single();

        profile.StoneType.Should().BeNull(
            "the contract states an explicit null for a piece with no stone; substituting a "
            + "default here would turn an absence of evidence into a finding");
        profile.Description.Should().BeNull();
        profile.OccasionTags.Value.Should().BeEmpty();
    }

    [Fact]
    public async Task EnrichAsync_WithPointOfSaleScope_IsRejected()
    {
        var handler = new FakeHttpMessageHandler().AlwaysRespond(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);
        var posScope = AiCallScope.ForPointOfSale(Guid.NewGuid(), "Administrator", Guid.NewGuid());

        var act = async () => await provider.Client().EnrichAsync(AnyRequest(), posScope);

        await act.Should().ThrowAsync<ArgumentException>().WithParameterName("scope");
        handler.Requests.Should().BeEmpty();
    }

    [Fact]
    public async Task EnrichAsync_WithOversizedBatch_IsRejectedBeforeCalling()
    {
        var handler = new FakeHttpMessageHandler().AlwaysRespond(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var request = new AiEnrichRequest
        {
            Products = Enumerable.Range(0, AiEnrichRequest.MaxBatchSize + 1)
                .Select(i => new AiEnrichProductInput { ProductId = $"P-{i}", Sku = $"JBG-{i}" })
                .ToList()
        };

        var act = async () => await provider.Client().EnrichAsync(request, CatalogScope());

        await act.Should().ThrowAsync<ArgumentException>().WithParameterName("request");
        handler.Requests.Should().BeEmpty(
            "the contract limit is known on this side; spending a round trip to be told so is waste");
    }

    [Fact]
    public async Task EnrichAsync_WhenRouteNotImplemented_ReportsItAsSuch()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.NotImplemented);
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().EnrichAsync(AnyRequest(), CatalogScope());

        await act.Should().ThrowAsync<AiNotImplementedException>();
        handler.Requests.Should().HaveCount(1, "a 501 is never retried: no attempt can succeed");
    }

    /// <summary>
    /// No automatic retry, and the reason is money rather than latency: a second attempt at a
    /// structured extraction spends the model budget again with no reason to expect a different
    /// answer.
    /// </summary>
    [Fact]
    public async Task EnrichAsync_WhenServerFails_IsNotRetried()
    {
        var handler = new FakeHttpMessageHandler().AlwaysRespond(HttpStatusCode.ServiceUnavailable);
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().EnrichAsync(AnyRequest(), CatalogScope());

        await act.Should().ThrowAsync<AiUnavailableException>();
        handler.Requests.Should().HaveCount(1);
    }

    /// <summary>
    /// The property that justifies a separate named client at all.
    /// </summary>
    /// <remarks>
    /// An enrichment batch is orders of magnitude slower than a retrieval call. Sharing a
    /// breaker would let a bad batch open the retrieval circuit and push every operator's search
    /// onto its degraded lexical path, for a service that is answering retrieval perfectly well.
    /// </remarks>
    [Fact]
    public async Task EnrichAsync_WhenItsCircuitOpens_RetrievalKeepsWorking()
    {
        var retrievalHandler = new FakeHttpMessageHandler()
            .AlwaysRespond(HttpStatusCode.OK, AiGatewayClientTestBodies.RetrievalSuccess);
        var enrichHandler = new FakeHttpMessageHandler()
            .AlwaysRespond(HttpStatusCode.ServiceUnavailable);

        await using var provider = AiGatewayTestHost.Build(
            retrievalHandler,
            enrichHandler: enrichHandler);

        var client = provider.Client();

        // Drive the enrichment breaker open: minimum throughput is 2 in the test host.
        for (var attempt = 0; attempt < 4; attempt++)
        {
            try
            {
                await client.EnrichAsync(AnyRequest(), CatalogScope());
            }
            catch (AiUnavailableException)
            {
                // Expected while the circuit is closing.
            }
        }

        var search = await client.SearchAsync(
            new AiSearchRequest { Query = "anillo de plata", TopK = 2 },
            AiCallScope.ForPointOfSale(Guid.NewGuid(), "Operator", Guid.NewGuid()));

        search.Results.Should().NotBeEmpty(
            "retrieval must keep answering while the enrichment circuit is open");
    }
}
