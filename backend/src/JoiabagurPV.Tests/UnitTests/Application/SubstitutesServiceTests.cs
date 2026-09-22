using FluentAssertions;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;
using JoiabagurPV.Domain.Interfaces.Repositories;
using JoiabagurPV.Domain.Interfaces.Services;
using JoiabagurPV.Tests.TestHelpers;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Microsoft.Extensions.Time.Testing;
using Moq;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// Unit tests for the substitutes orchestrator. Hydration is simulated as the repository behaves:
/// among the requested identifiers, the rows this point of sale carries — quantity zero included.
/// </summary>
public class SubstitutesServiceTests
{
    private static readonly Guid UserId = Guid.Parse("11111111-1111-1111-1111-111111111111");
    private static readonly Guid PosId = Guid.Parse("22222222-2222-2222-2222-222222222222");
    private static readonly Guid Anchor = Guid.Parse("bbbbbbbb-0000-0000-0000-000000000001");

    private readonly Mock<IAiGatewayClient> _gateway = new();
    private readonly Mock<IAssistedSearchRepository> _repository = new();
    private readonly Mock<IUserPointOfSaleService> _userPointOfSale = new();
    private readonly Mock<IFileStorageService> _fileStorage = new();
    private readonly Mock<ITraceContextAccessor> _traceContext = new();
    private readonly RecordingLoggerProvider _logs = new();
    private readonly List<AssistedSearchRow> _carried = [];
    private readonly List<IReadOnlyList<Guid>> _hydrations = [];
    private readonly List<AiSubstitutesRequest> _sent = [];

    private readonly AiSalesAssistOptions _options = new() { EnabledByDefault = true };

    public SubstitutesServiceTests()
    {
        _traceContext.SetupGet(t => t.CurrentTraceId).Returns("trace-subs-1");

        _repository
            .Setup(r => r.IsPointOfSaleActiveAsync(PosId, It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);

        _repository
            .Setup(r => r.HydrateAsync(It.IsAny<IReadOnlyList<Guid>>(), PosId, It.IsAny<CancellationToken>()))
            .ReturnsAsync((IReadOnlyList<Guid> ids, Guid _, CancellationToken _) =>
            {
                _hydrations.Add(ids);
                return _carried.Where(row => ids.Contains(row.ProductId)).ToList();
            });

        _userPointOfSale.Setup(u => u.HasAccessAsync(UserId, PosId)).ReturnsAsync(true);

        Carry(Anchor, quantity: 0);
    }

    // ---------------------------------------------------------------- scope

    [Fact]
    public async Task GetSubstitutesAsync_AsOperatorOfAnotherPos_IsForbiddenWithoutCallingAi()
    {
        _userPointOfSale.Setup(u => u.HasAccessAsync(UserId, PosId)).ReturnsAsync(false);

        (await SubstitutesAsync()).Outcome.Should().Be(SalesCardAccessOutcome.PointOfSaleForbidden);
        VerifyAiCalls(Times.Never());
    }

    [Fact]
    public async Task GetSubstitutesAsync_AnchorNotCarriedAtPos_IsNotFoundWithoutCallingAi()
    {
        _carried.Clear();

        (await SubstitutesAsync()).Outcome.Should().Be(SalesCardAccessOutcome.ProductNotFound);
        VerifyAiCalls(Times.Never());
    }

    // ---------------------------------------------------------------- the call

    [Fact]
    public async Task Substitutes_AlwaysRequestsTheLargestWindow()
    {
        GatewayReturns();

        await SubstitutesAsync(pageSize: 1);

        _sent.Should().ContainSingle().Which.TopK.Should().Be(20,
            "20 reaches the over-retrieval cap of 60 whatever page the caller asked for");
        AiSearchRequest.OverRetrievalCount(20).Should().Be(AiSearchRequest.OverRetrievalCap);
        _sent[0].Reason.Should().Be("sin_stock", "the anchored product has no units here");
        _sent[0].ProductId.Should().Be(Anchor.ToString());
    }

    [Fact]
    public async Task Substitutes_WithStockOnTheAnchor_SendsNoReason()
    {
        _carried.Clear();
        Carry(Anchor, quantity: 4);
        GatewayReturns();

        await SubstitutesAsync();

        _sent.Single().Reason.Should().BeNull();
    }

    [Fact]
    public async Task Substitutes_ShortPage_DoesNotTriggerASecondCall()
    {
        var ids = Enumerable.Range(0, 60).Select(_ => Guid.NewGuid()).ToArray();
        Carry(ids[7], quantity: 2);
        GatewayReturns(ids);

        var response = (await SubstitutesAsync(pageSize: 5)).Response!;

        response.Results.Should().ContainSingle();
        VerifyAiCalls(Times.Once());
    }

    // ---------------------------------------------------------------- hydration

    [Fact]
    public async Task Substitutes_ExcludeProductsWithoutStockAtTargetPos()
    {
        var withStock = Guid.NewGuid();
        var withoutStock = Guid.NewGuid();
        var notCarried = Guid.NewGuid();
        Carry(withStock, quantity: 3);
        Carry(withoutStock, quantity: 0);
        GatewayReturns(notCarried, withoutStock, withStock);

        var response = (await SubstitutesAsync()).Response!;

        response.Results.Select(r => r.ProductId).Should().Equal(withStock);
        response.Results.Single().QuantityAtPointOfSale.Should().Be(3);
        response.SurvivedHydration.Should().Be(2, "carried with or without units");
        response.CandidatesReturned.Should().Be(3);
    }

    [Fact]
    public async Task Substitutes_KeepTheOrderOfTheAiService()
    {
        var ids = Enumerable.Range(0, 4).Select(_ => Guid.NewGuid()).ToArray();

        // Carried in the reverse order, so an accidental re-sort by hydration would show.
        foreach (var id in ids.Reverse())
        {
            Carry(id, quantity: 1);
        }

        GatewayReturns(ids);

        var response = (await SubstitutesAsync(pageSize: 10)).Response!;

        response.Results.Select(r => r.ProductId).Should().Equal(ids);
    }

    [Fact]
    public async Task Substitutes_TruncateToThePageAfterFiltering()
    {
        var ids = Enumerable.Range(0, 10).Select(_ => Guid.NewGuid()).ToArray();
        for (var i = 0; i < ids.Length; i++)
        {
            // Every other one without stock: the page must be filled from the survivors.
            Carry(ids[i], quantity: i % 2 == 0 ? 0 : 1);
        }

        GatewayReturns(ids);

        var response = (await SubstitutesAsync(pageSize: 3)).Response!;

        response.Results.Select(r => r.ProductId).Should().Equal(ids[1], ids[3], ids[5]);
    }

    [Fact]
    public async Task Substitutes_HydrateTheWindowInASingleQuery()
    {
        var ids = Enumerable.Range(0, 60).Select(_ => Guid.NewGuid()).ToArray();
        GatewayReturns(ids);

        await SubstitutesAsync();

        _hydrations.Should().HaveCount(2, "one query checks the anchor, one hydrates the whole window");
        _hydrations[1].Should().HaveCount(60);
    }

    [Fact]
    public async Task Substitutes_NeverOfferTheProductItself()
    {
        _carried.Clear();
        Carry(Anchor, quantity: 5);
        var other = Guid.NewGuid();
        Carry(other, quantity: 1);
        GatewayReturns(Anchor, other);

        var response = (await SubstitutesAsync()).Response!;

        response.Results.Select(r => r.ProductId).Should().Equal(other);
    }

    [Fact]
    public async Task Substitutes_CarryPriceFromTheCatalogAndSignalsFromTheAi()
    {
        var id = Guid.NewGuid();
        Carry(id, quantity: 2, price: 55m);
        GatewayReturns(id);

        var result = (await SubstitutesAsync()).Response!.Results.Single();

        result.Price.Should().Be(55m);
        result.MaterialOverlap.Should().Be(0.5);
        result.StyleSimilarity.Should().Be(0.4);
        result.FamilyMatch.Should().BeFalse();
    }

    // ---------------------------------------------------------------- outcomes

    public static TheoryData<string, SubstitutesOutcome> FourOutcomes => new()
    {
        { "ok", SubstitutesOutcome.Ok },
        { "none_in_stock", SubstitutesOutcome.NoneInStock },
        { "product_not_indexed", SubstitutesOutcome.ProductNotIndexed },
        { "ai_unavailable", SubstitutesOutcome.AiUnavailable }
    };

    /// <summary>
    /// Four things that can leave the block without substitutes, each a different message to the
    /// operator — and none of them a server error.
    /// </summary>
    [Theory]
    [MemberData(nameof(FourOutcomes))]
    public async Task Substitutes_DistinguishesTheFourEmptyOutcomes(string wire, SubstitutesOutcome expected)
    {
        var candidate = Guid.NewGuid();

        switch (expected)
        {
            case SubstitutesOutcome.Ok:
                Carry(candidate, quantity: 1);
                GatewayReturns(candidate);
                break;
            case SubstitutesOutcome.NoneInStock:
                Carry(candidate, quantity: 0);
                GatewayReturns(candidate);
                break;
            case SubstitutesOutcome.ProductNotIndexed:
                GatewayThrows(new AiRequestRejectedException(422, "not indexed"));
                break;
            case SubstitutesOutcome.AiUnavailable:
                GatewayThrows(new AiUnavailableException("timeout"));
                break;
        }

        var result = await SubstitutesAsync();

        result.Outcome.Should().Be(SalesCardAccessOutcome.Success);
        result.Response!.Outcome.Should().Be(expected);
        FunnelLine().Property("Outcome").Should().Be(wire);
    }

    [Theory]
    [MemberData(nameof(OtherGatewayFailures))]
    public async Task Substitutes_AnyOtherGatewayFailure_IsAiUnavailable(AiGatewayException failure)
    {
        GatewayThrows(failure);

        (await SubstitutesAsync()).Response!.Outcome.Should().Be(SubstitutesOutcome.AiUnavailable);
    }

    public static TheoryData<AiGatewayException> OtherGatewayFailures => new()
    {
        new AiNotImplementedException("501"),
        new AiGatewayConfigurationException("401")
    };

    [Fact]
    public async Task Substitutes_WhenSwitchedOff_ReportsAiUnavailableWithoutCallingAi()
    {
        _options.EnabledByDefault = false;

        var response = (await SubstitutesAsync()).Response!;

        response.Outcome.Should().Be(SubstitutesOutcome.AiUnavailable);
        VerifyAiCalls(Times.Never());
        FunnelLine().Property("Reason").Should().Be("switched_off");
    }

    // ---------------------------------------------------------------- funnel

    [Fact]
    public async Task Substitutes_LogsTheFunnel()
    {
        var ids = Enumerable.Range(0, 6).Select(_ => Guid.NewGuid()).ToArray();
        Carry(ids[0], quantity: 1);
        Carry(ids[1], quantity: 0);
        Carry(ids[2], quantity: 2);
        Carry(ids[3], quantity: 5);
        GatewayReturns(ids);

        await SubstitutesAsync(pageSize: 2);

        var line = FunnelLine();
        line.Level.Should().Be(LogLevel.Information);
        line.Property("TraceId").Should().Be("trace-subs-1");
        line.Property("PointOfSaleId").Should().Be(PosId);
        line.Property("ProductId").Should().Be(Anchor);
        line.Property("Outcome").Should().Be("ok");
        line.Property("CandidatesReturned").Should().Be(6);
        line.Property("Carried").Should().Be(4);
        line.Property("InStock").Should().Be(3);
        line.Property("Returned").Should().Be(2);
        line.Property("AiMs").Should().NotBeNull();
    }

    // ---------------------------------------------------------------- helpers

    private SubstitutesService CreateService() => new(
        _gateway.Object,
        _repository.Object,
        _userPointOfSale.Object,
        _fileStorage.Object,
        _traceContext.Object,
        Mock.Of<IOptionsMonitor<AiSalesAssistOptions>>(m => m.CurrentValue == _options),
        new FakeTimeProvider(),
        LoggerFactory.Create(builder => builder.SetMinimumLevel(LogLevel.Trace).AddProvider(_logs))
            .CreateLogger<SubstitutesService>());

    private Task<SubstitutesResult> SubstitutesAsync(int? pageSize = null) =>
        CreateService().GetSubstitutesAsync(
            Anchor, new SubstitutesRequest { PointOfSaleId = PosId, PageSize = pageSize }, UserId, "Operator", isAdmin: false);

    private CapturedLogEntry FunnelLine() =>
        _logs.Entries.Single(e => e.Template.StartsWith("stage=substitutes ", StringComparison.Ordinal));

    private void Carry(Guid id, int quantity, decimal price = 30m) =>
        _carried.Add(new AssistedSearchRow
        {
            ProductId = id, Sku = "SKU-" + id.ToString()[..8], Name = "Pieza", Price = price, Quantity = quantity
        });

    private void GatewayReturns(params Guid[] ids) =>
        _gateway
            .Setup(g => g.SubstitutesAsync(It.IsAny<AiSubstitutesRequest>(), It.IsAny<AiCallScope>(), It.IsAny<CancellationToken>()))
            .Callback<AiSubstitutesRequest, AiCallScope, CancellationToken>((r, _, _) => _sent.Add(r))
            .ReturnsAsync(new AiSubstitutesResponse
            {
                Results = ids.Select(id => new AiSubstituteResult
                {
                    ProductId = id.ToString(),
                    Sku = "SKU-" + id.ToString()[..8],
                    Score = 0.7,
                    SimilaritySignals = new AiSimilaritySignals { MaterialOverlap = 0.5, StyleSimilarity = 0.4 }
                }).ToList(),
                CandidatesReturned = ids.Length,
                TraceId = "trace-subs-1",
                EffectivePosId = PosId.ToString()
            });

    private void GatewayThrows(Exception exception) =>
        _gateway
            .Setup(g => g.SubstitutesAsync(It.IsAny<AiSubstitutesRequest>(), It.IsAny<AiCallScope>(), It.IsAny<CancellationToken>()))
            .ThrowsAsync(exception);

    private void VerifyAiCalls(Times times) =>
        _gateway.Verify(
            g => g.SubstitutesAsync(It.IsAny<AiSubstitutesRequest>(), It.IsAny<AiCallScope>(), It.IsAny<CancellationToken>()),
            times);
}
