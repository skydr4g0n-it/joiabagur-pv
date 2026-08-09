using System.IdentityModel.Tokens.Jwt;
using System.Net;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Application.Services;
using JoiabagurPV.Tests.TestHelpers;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// Exercises the gateway against the real resilience pipeline with a fake socket underneath.
/// No jbg-ai container, no network.
/// </summary>
public class AiGatewayClientTests
{
    private const string SuccessBody = """
        {
          "results": [
            {
              "product_id": "11111111-1111-1111-1111-111111111111",
              "sku": "ERIZO-M",
              "score": 0.87,
              "match_reasons": ["material", "piece_type"],
              "materials": ["plata", "baño de oro"],
              "family_id": "22222222-2222-2222-2222-222222222222",
              "variant_label": "M",
              "debug": { "vector_score": 0.9, "lexical_score": 0.4, "rerank_score": null, "notes": ["stub"] }
            },
            {
              "product_id": "33333333-3333-3333-3333-333333333333",
              "sku": "ANILLO-S",
              "score": 0.61,
              "match_reasons": ["piece_type"],
              "materials": ["plata"],
              "family_id": null,
              "variant_label": null,
              "debug": null
            }
          ],
          "candidates_returned": 2,
          "low_confidence": false,
          "trace_id": "trace-test-0001",
          "effective_pos_id": "44444444-4444-4444-4444-444444444444"
        }
        """;

    private static AiSearchRequest AnyRequest() => new()
    {
        Query = "anillo de plata para regalo",
        TopK = 5,
        Filters = new AiSearchFilters { Materials = ["plata"] }
    };

    private static AiCallScope AnyScope() =>
        AiCallScope.ForPointOfSale(Guid.NewGuid(), "Operator", Guid.NewGuid());

    [Fact]
    public async Task SearchAsync_WhenServiceReturns200_MapsResponse()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var response = await provider.Client().SearchAsync(AnyRequest(), AnyScope());

        response.CandidatesReturned.Should().Be(2);
        response.LowConfidence.Should().BeFalse();
        response.TraceId.Should().Be("trace-test-0001");
        response.EffectivePosId.Should().Be("44444444-4444-4444-4444-444444444444");

        var first = response.Results[0];
        first.ProductId.Should().Be("11111111-1111-1111-1111-111111111111");
        first.Sku.Should().Be("ERIZO-M");
        first.Score.Should().BeApproximately(0.87, 0.001);
        first.MatchReasons.Should().BeEquivalentTo(["material", "piece_type"]);
        first.Materials.Should().BeEquivalentTo(["plata", "baño de oro"]);
        first.VariantLabel.Should().Be("M");
        first.Debug!.VectorScore.Should().BeApproximately(0.9, 0.001);
    }

    [Fact]
    public async Task SearchAsync_WhenFamilyIdIsNull_MapsToNullWithoutThrowing()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var response = await provider.Client().SearchAsync(AnyRequest(), AnyScope());

        var second = response.Results[1];
        second.FamilyId.Should().BeNull();
        second.VariantLabel.Should().BeNull();
        second.Debug.Should().BeNull();
    }

    /// <summary>
    /// The service over-fetches so the caller has margin after hydrating and discarding.
    /// Truncating here would silently starve that caller.
    /// </summary>
    [Fact]
    public async Task SearchAsync_WhenServiceOverFetches_ReturnsEveryCandidate()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var request = AnyRequest();
        request.TopK = 1;

        var response = await provider.Client().SearchAsync(request, AnyScope());

        response.Results.Should().HaveCount(2, "the client must not truncate to top_k");
    }

    [Fact]
    public async Task SearchAsync_SendsBearerTokenAndTraceHeader()
    {
        var handler = new FakeHttpMessageHandler().EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler, traceId: "trace-xyz-999");
        var scope = AnyScope();

        await provider.Client().SearchAsync(AnyRequest(), scope);

        var request = handler.LastRequest!;
        request.RequestUri!.AbsolutePath.Should().Be("/v1/retrieval/products");
        request.Headers.Authorization!.Scheme.Should().Be("Bearer");
        request.Headers.GetValues(AiGatewayClient.TraceHeaderName).Should().ContainSingle()
            .Which.Should().Be("trace-xyz-999");

        var payload = new JwtSecurityTokenHandler()
            .ReadJwtToken(request.Headers.Authorization.Parameter).Payload;

        payload["trace_id"].Should().Be("trace-xyz-999");
        payload["pos_id"].Should().Be(scope.PointOfSaleId.ToString());
    }

    [Fact]
    public async Task SearchAsync_WhenTimeout_ThrowsAiUnavailable()
    {
        var handler = new FakeHttpMessageHandler().AlwaysRespond(HttpStatusCode.OK, SuccessBody);
        handler.EnqueueHang().EnqueueHang();
        await using var provider = AiGatewayTestHost.Build(handler, retrievalTimeoutMs: 60);

        var act = async () => await provider.Client().SearchAsync(AnyRequest(), AnyScope());

        await act.Should().ThrowAsync<AiUnavailableException>();
    }

    /// <summary>
    /// Two failing calls fill the sampling window and open the circuit; the third must not
    /// reach the socket at all. The thresholds are set low on purpose — with the framework
    /// defaults the circuit never opens and this test would pass without testing anything.
    /// </summary>
    [Fact]
    public async Task SearchAsync_WhenCircuitOpen_FailsFastWithoutCall()
    {
        var handler = new FakeHttpMessageHandler().AlwaysRespond(HttpStatusCode.ServiceUnavailable);
        await using var provider = AiGatewayTestHost.Build(handler);
        var client = provider.Client();

        await Assert.ThrowsAsync<AiUnavailableException>(
            () => client.SearchAsync(AnyRequest(), AnyScope()));

        var requestsBeforeCircuitOpened = handler.RequestCount;

        await Assert.ThrowsAsync<AiUnavailableException>(
            () => client.SearchAsync(AnyRequest(), AnyScope()));

        handler.RequestCount.Should().Be(
            requestsBeforeCircuitOpened,
            "with the circuit open no request may leave the process");
    }

    /// <summary>
    /// jbg-ai answers 501 for a route whose implementation lands in a later change. Retrying it
    /// spends the budget for nothing, which is why the contract uses 501 and not 503.
    /// </summary>
    [Fact]
    public async Task SearchAsync_WhenServiceReturns501_DoesNotRetryAndThrowsNotImplemented()
    {
        var handler = new FakeHttpMessageHandler().AlwaysRespond(HttpStatusCode.NotImplemented);
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().SearchAsync(AnyRequest(), AnyScope());

        await act.Should().ThrowAsync<AiNotImplementedException>();
        handler.RequestCount.Should().Be(1, "a route with no implementation must not be retried");
    }

    [Fact]
    public async Task SearchAsync_WhenServiceReturns401_DoesNotRetry()
    {
        var handler = new FakeHttpMessageHandler().AlwaysRespond(HttpStatusCode.Unauthorized);
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().SearchAsync(AnyRequest(), AnyScope());

        await act.Should().ThrowAsync<AiGatewayConfigurationException>();
        handler.RequestCount.Should().Be(1, "a mismatched secret is not fixed by trying again");
    }

    [Fact]
    public async Task SearchAsync_WhenServiceReturns503_RetriesOnceThenSucceeds()
    {
        var handler = new FakeHttpMessageHandler()
            .EnqueueResponse(HttpStatusCode.ServiceUnavailable)
            .EnqueueResponse(HttpStatusCode.OK, SuccessBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var response = await provider.Client().SearchAsync(AnyRequest(), AnyScope());

        response.CandidatesReturned.Should().Be(2);
        handler.RequestCount.Should().Be(2, "a transient server error is worth exactly one more attempt");
    }

    [Fact]
    public async Task SearchAsync_WhenTransportFails_ThrowsAiUnavailableAfterOneRetry()
    {
        var handler = new FakeHttpMessageHandler()
            .EnqueueTransportFailure()
            .EnqueueTransportFailure();
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().SearchAsync(AnyRequest(), AnyScope());

        await act.Should().ThrowAsync<AiUnavailableException>();
        handler.RequestCount.Should().Be(2);
    }
}
