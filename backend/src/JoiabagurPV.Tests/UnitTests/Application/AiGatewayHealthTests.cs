using System.Net;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Tests.TestHelpers;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// The jbg-ai health probe on the gateway client (C17).
/// </summary>
/// <remarks>
/// The tests run against the real registration, pipeline included, with only the socket
/// replaced. That matters more here than anywhere else in this family: the property under test
/// is the ABSENCE of a resilience pipeline on this client, and a hand-rolled stand-in would
/// prove nothing about how the container actually wires it.
/// </remarks>
public class AiGatewayHealthTests
{
    private const string HealthyBody = """
        {
          "status": "OK",
          "version": "0.1.0",
          "database": "ok",
          "index": {
            "documents": 1200,
            "model": "openai/text-embedding-3-small",
            "configured_model": "openai/text-embedding-3-small",
            "status": "ok"
          },
          "provider": "configured"
        }
        """;

    /// <summary>
    /// The reason the probe has its own named client instead of reusing the retrieval one.
    /// </summary>
    /// <remarks>
    /// A probe that shares the retrieval breaker stops answering exactly when the retrieval path
    /// is broken — which is the only moment anyone opens the dashboard to ask what is wrong. It
    /// would answer "I cannot tell you" by refusing to look, and it would look identical to the
    /// AI service being down when the AI service is fine and only the circuit is open.
    /// </remarks>
    [Fact]
    public async Task AiHealth_BypassesCircuitBreaker_WhenGatewayCircuitIsOpen()
    {
        var retrievalHandler = new FakeHttpMessageHandler()
            .AlwaysRespond(HttpStatusCode.ServiceUnavailable);
        var healthHandler = new FakeHttpMessageHandler()
            .AlwaysRespond(HttpStatusCode.OK, HealthyBody);

        await using var provider = AiGatewayTestHost.Build(
            retrievalHandler,
            healthHandler: healthHandler);

        var client = provider.Client();

        // Drive the retrieval breaker open: minimum throughput is 2 in the test host.
        for (var attempt = 0; attempt < 4; attempt++)
        {
            try
            {
                await client.SearchAsync(
                    new AiSearchRequest { Query = "anillo de plata", TopK = 2 },
                    AiCallScope.ForPointOfSale(Guid.NewGuid(), "Operator", Guid.NewGuid()));
            }
            catch (AiUnavailableException)
            {
                // Expected while the circuit is closing.
            }
        }

        var requestsBefore = healthHandler.RequestCount;

        var report = await client.HealthAsync();

        report.Status.Should().Be("OK");
        report.Index.Documents.Should().Be(1200);
        healthHandler.RequestCount.Should().Be(
            requestsBefore + 1,
            "the probe must actually issue its request while the retrieval circuit is open");
    }

    /// <summary>The snake_case wire contract, mapped by the shared serialization options.</summary>
    [Fact]
    public async Task HealthAsync_MapsTheReportFromTheWireContract()
    {
        var handler = new FakeHttpMessageHandler().AlwaysRespond(HttpStatusCode.OK, HealthyBody);
        await using var provider = AiGatewayTestHost.Build(handler);

        var report = await provider.Client().HealthAsync();

        report.Version.Should().Be("0.1.0");
        report.Database.Should().Be("ok");
        report.Provider.Should().Be("configured");
        report.Index.Status.Should().Be("ok");
        report.Index.Model.Should().Be("openai/text-embedding-3-small");
        report.Index.ConfiguredModel.Should().Be("openai/text-embedding-3-small");
    }

    /// <summary>
    /// A model mismatch reaches this side intact, because the dashboard has to be able to show
    /// it as an error rather than as a healthy service.
    /// </summary>
    [Fact]
    public async Task HealthAsync_CarriesAModelMismatchThrough()
    {
        const string mismatched = """
            {
              "status": "degraded",
              "version": "0.1.0",
              "database": "ok",
              "index": {
                "documents": 1200,
                "model": "openai/text-embedding-3-large",
                "configured_model": "openai/text-embedding-3-small",
                "status": "model_mismatch"
              },
              "provider": "configured"
            }
            """;

        var handler = new FakeHttpMessageHandler().AlwaysRespond(HttpStatusCode.OK, mismatched);
        await using var provider = AiGatewayTestHost.Build(handler);

        var report = await provider.Client().HealthAsync();

        report.Status.Should().Be("degraded");
        report.Index.Status.Should().Be("model_mismatch");
        report.Index.Model.Should().Be("openai/text-embedding-3-large");
        report.Index.ConfiguredModel.Should().Be("openai/text-embedding-3-small");
    }

    /// <summary>
    /// An unreachable service is reported, not retried. Nobody is served by a probe that spends
    /// two more budgets before telling an administrator what they already suspect.
    /// </summary>
    [Fact]
    public async Task HealthAsync_WhenServiceUnreachable_ThrowsWithoutRetrying()
    {
        var handler = new FakeHttpMessageHandler().AlwaysRespond(HttpStatusCode.ServiceUnavailable);
        await using var provider = AiGatewayTestHost.Build(handler);

        var act = async () => await provider.Client().HealthAsync();

        await act.Should().ThrowAsync<AiUnavailableException>();
        handler.RequestCount.Should().Be(1, "the health client carries no retry");
    }
}
