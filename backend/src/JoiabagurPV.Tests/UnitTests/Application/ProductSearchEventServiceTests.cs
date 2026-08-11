using System.Text.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using JoiabagurPV.Tests.TestHelpers;
using Microsoft.Extensions.Logging;
using Moq;
using Xunit;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// Unit tests for the assisted-search telemetry service.
/// </summary>
public class ProductSearchEventServiceTests
{
    private static readonly Guid UserId = Guid.Parse("11111111-1111-1111-1111-111111111111");
    private static readonly Guid PointOfSaleId = Guid.Parse("22222222-2222-2222-2222-222222222222");

    private readonly Mock<IRepository<ProductSearchEvent>> _events = new();
    private readonly Mock<IUnitOfWork> _unitOfWork = new();
    private readonly RecordingLoggerProvider _logs = new();
    private readonly List<ProductSearchEvent> _added = [];

    private ProductSearchEventService CreateService()
    {
        _events
            .Setup(r => r.AddAsync(It.IsAny<ProductSearchEvent>()))
            .Callback<ProductSearchEvent>(_added.Add)
            .ReturnsAsync((ProductSearchEvent e) => e);

        _events
            .Setup(r => r.UpdateAsync(It.IsAny<ProductSearchEvent>()))
            .ReturnsAsync((ProductSearchEvent e) => e);

        using var factory = LoggerFactory.Create(builder => builder
            .SetMinimumLevel(LogLevel.Trace)
            .AddProvider(_logs));

        return new ProductSearchEventService(
            _events.Object,
            _unitOfWork.Object,
            factory.CreateLogger<ProductSearchEventService>());
    }

    private static AiSearchResult Result(string sku, Guid productId, double score = 0.9) => new()
    {
        ProductId = productId.ToString(),
        Sku = sku,
        Score = score,
        MatchReasons = ["material:plata"],
        Materials = ["plata"]
    };

    private static RecordSearchRequest Request(
        IReadOnlyList<AiSearchResult> results,
        SearchOrigin origin = SearchOrigin.Assisted,
        string query = "anillo de plata para regalo",
        Guid? sessionId = null) => new()
        {
            Scope = AiCallScope.ForPointOfSale(UserId, "Operator", PointOfSaleId),
            Query = query,
            Filters = new AiSearchFilters { Materials = ["plata"] },
            DisplayedResults = results,
            Origin = origin,
            SearchSessionId = sessionId,
            TraceId = "0af7651916cd43dd8448eb211c80319c",
            RetrievalMs = 180,
            TotalMs = 240
        };

    [Fact]
    public async Task RecordSearch_WithValidScope_PersistsEventWithServerKnownFields()
    {
        var service = CreateService();
        var request = Request([Result("SKU-1", Guid.NewGuid())]);

        var id = await service.RecordSearchAsync(request);

        id.Should().NotBeNull();
        var stored = _added.Single();
        stored.UserId.Should().Be(UserId);
        stored.PointOfSaleId.Should().Be(PointOfSaleId);
        stored.SearchText.Should().Be(request.Query);
        stored.TraceId.Should().Be(request.TraceId);
        stored.RetrievalMs.Should().Be(180);
        stored.TotalMs.Should().Be(240);
        stored.SearchOrigin.Should().Be(SearchOrigin.Assisted);
        _unitOfWork.Verify(u => u.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task RecordSearch_ProjectsResultsToCamelCaseWithOneBasedRank()
    {
        var service = CreateService();
        var first = Guid.NewGuid();
        var second = Guid.NewGuid();

        await service.RecordSearchAsync(Request([Result("SKU-1", first), Result("SKU-2", second, 0.4)]));

        using var document = JsonDocument.Parse(_added.Single().ResultsJson);
        var entries = document.RootElement.EnumerateArray().ToList();

        entries.Should().HaveCount(2);
        entries[0].GetProperty("productId").GetString().Should().Be(first.ToString());
        entries[0].GetProperty("sku").GetString().Should().Be("SKU-1");
        entries[0].GetProperty("rank").GetInt32().Should().Be(1, "ranks are 1-based, as the KPI reads them");
        entries[0].GetProperty("score").GetDouble().Should().Be(0.9);
        entries[0].GetProperty("matchReasons").EnumerateArray().Should().ContainSingle();
        entries[1].GetProperty("rank").GetInt32().Should().Be(2);

        // Catalog attributes stay out: they are one join away, so storing them would duplicate
        // the catalog inside an event table.
        entries[0].TryGetProperty("materials", out _).Should().BeFalse();
    }

    [Fact]
    public async Task RecordSearch_WhenOriginIsLexicalFallback_PersistsDistinguishableOrigin()
    {
        var service = CreateService();

        await service.RecordSearchAsync(
            Request([Result("SKU-1", Guid.NewGuid())], SearchOrigin.LexicalFallback));

        _added.Single().SearchOrigin.Should().Be(SearchOrigin.LexicalFallback,
            "a week of open circuit breakers must not read as the AI ranking worse");
    }

    [Fact]
    public async Task RecordSearch_WithNoResults_PersistsZeroCountAndEmptyArray()
    {
        var service = CreateService();

        await service.RecordSearchAsync(Request([]));

        var stored = _added.Single();
        stored.ResultsCount.Should().Be(0);
        stored.ResultsJson.Should().Be("[]", "an empty array, never a null, so the KPI query needs no COALESCE");
    }

    [Fact]
    public async Task RecordSearch_WithMoreResultsThanCap_StoresOnlyTheCap()
    {
        var service = CreateService();
        var results = Enumerable.Range(0, ProductSearchEventService.MaxStoredResults + 20)
            .Select(i => Result($"SKU-{i}", Guid.NewGuid()))
            .ToList();

        await service.RecordSearchAsync(Request(results));

        using var document = JsonDocument.Parse(_added.Single().ResultsJson);
        document.RootElement.GetArrayLength().Should().Be(ProductSearchEventService.MaxStoredResults);
    }

    [Fact]
    public async Task RecordSearch_WithMoreResultsThanCap_RecordsTrueDisplayedCount()
    {
        var service = CreateService();
        var displayed = ProductSearchEventService.MaxStoredResults + 20;
        var results = Enumerable.Range(0, displayed)
            .Select(i => Result($"SKU-{i}", Guid.NewGuid()))
            .ToList();

        await service.RecordSearchAsync(Request(results));

        _added.Single().ResultsCount.Should().Be(displayed,
            "the count reports what the operator saw; comparing it against the stored array "
            + "length is what makes truncation detectable at all");
    }

    [Fact]
    public async Task RecordSearch_WithoutSessionId_GeneratesOneSoTheColumnIsNeverEmpty()
    {
        var service = CreateService();

        await service.RecordSearchAsync(Request([], sessionId: null));

        _added.Single().SearchSessionId.Should().NotBeEmpty();
    }

    [Fact]
    public async Task RecordSearch_WithSessionId_KeepsTheCallerEpisode()
    {
        var service = CreateService();
        var session = Guid.NewGuid();

        await service.RecordSearchAsync(Request([], sessionId: session));
        await service.RecordSearchAsync(Request([], sessionId: session));

        _added.Should().OnlyContain(e => e.SearchSessionId == session,
            "the reformulations of one episode have to group together");
        _added.Should().OnlyContain(e => e.SelectedProductId == null,
            "a selection only appears on the query it was made from");
    }

    [Fact]
    public async Task RecordSearch_GroupedByEpisode_TellsReformulationFromAbandonment()
    {
        // The whole justification for SearchSessionId. Without grouping, the two refinements
        // below are indistinguishable from genuine abandonments and the "searches with no
        // result" KPI counts two false positives for an operator who refined and then bought.
        var service = CreateService();
        var converted = Guid.NewGuid();
        var abandoned = Guid.NewGuid();
        var chosen = Guid.NewGuid();

        await service.RecordSearchAsync(Request([], sessionId: converted));
        await service.RecordSearchAsync(Request([], sessionId: converted));
        await service.RecordSearchAsync(Request([Result("SKU-1", chosen)], sessionId: converted));
        await service.RecordSearchAsync(Request([], sessionId: abandoned));

        var last = _added.Last(e => e.SearchSessionId == converted);
        _events.Setup(r => r.GetByIdAsync(last.Id)).ReturnsAsync(last);
        await service.RecordSelectionAsync(last.Id, UserId, chosen);

        // Reformulation: no selection of its own, but a later sibling in the same episode.
        // Ordered by position rather than by timestamp: consecutive calls can land on the same
        // clock tick, and a test that depends on them not doing so is flaky by construction.
        var reformulations = _added
            .Where((e, index) => e.SelectedProductId is null
                                 && _added.Skip(index + 1).Any(s => s.SearchSessionId == e.SearchSessionId))
            .ToList();

        _added.Should().BeInAscendingOrder(e => e.CreatedAt,
            "the derivation in SQL orders an episode by its timestamps");

        // Abandonment: an episode where nothing was ever selected.
        var abandonedEpisodes = _added
            .GroupBy(e => e.SearchSessionId)
            .Where(episode => episode.All(e => e.SelectedProductId is null))
            .Select(episode => episode.Key)
            .ToList();

        reformulations.Should().HaveCount(2, "the two queries preceding the selection were refinements");
        abandonedEpisodes.Should().Equal([abandoned], "only the episode with no selection at all was abandoned");
    }

    [Fact]
    public void RecordSearchAsync_HasNoOverloadTakingABarePointOfSaleIdentifier()
    {
        // The point-of-sale guarantee rests on the signature: the request carries an
        // AiCallScope, whose only factory demands a validated point of sale, so a search cannot
        // be recorded outside an authorised scope. A guarantee that lives only in the code
        // disappears in the first refactor unless something asserts it — the same reason C03
        // asserts that its scope type has no public constructor.
        var overloads = typeof(IProductSearchEventService)
            .GetMethods()
            .Where(m => m.Name == nameof(IProductSearchEventService.RecordSearchAsync))
            .ToList();

        overloads.Should().ContainSingle();
        overloads[0].GetParameters().Should().ContainSingle()
            .Which.ParameterType.Should().Be<RecordSearchRequest>();

        typeof(RecordSearchRequest).GetProperty(nameof(RecordSearchRequest.Scope))!
            .PropertyType.Should().Be<AiCallScope>("a bare Guid would bypass the validated scope");
    }

    [Fact]
    public async Task RecordSearch_WhenPersistenceFails_DoesNotThrowAndReturnsNull()
    {
        var service = CreateService();
        _unitOfWork.Setup(u => u.SaveChangesAsync()).ThrowsAsync(new InvalidOperationException("database is gone"));

        var act = async () => await service.RecordSearchAsync(Request([Result("SKU-1", Guid.NewGuid())]));

        var id = await act.Should().NotThrowAsync();
        id.Subject.Should().BeNull();
        _logs.At(LogLevel.Error).Should().ContainSingle(e => e.Template.StartsWith("search_event_record_failed"));
    }

    [Fact]
    public async Task RecordSearch_QueryTextNeverRisesAboveDebug()
    {
        var service = CreateService();
        const string query = "gargantilla oro para la clienta de la 302";

        await service.RecordSearchAsync(Request([Result("SKU-1", Guid.NewGuid())], query: query));

        _logs.At(LogLevel.Debug).Should().Contain(e => e.Mentions(query),
            "the query is still recorded, just where it belongs");

        _logs.Entries
            .Where(e => e.Level >= LogLevel.Information)
            .Should().NotContain(e => e.Mentions(query),
                "it is free text that may incidentally carry personal data, and production logs "
                + "are not where that should be discovered");

        _logs.Single("search_event_recorded").Property("QueryLength").Should().Be(query.Length);
    }

    [Fact]
    public async Task RecordSelection_WithProductInResults_DerivesRankFromStoredList()
    {
        var service = CreateService();
        var chosen = Guid.NewGuid();
        var stored = EventWith([Result("SKU-1", Guid.NewGuid()), Result("SKU-2", chosen)]);
        _events.Setup(r => r.GetByIdAsync(stored.Id)).ReturnsAsync(stored);

        var outcome = await service.RecordSelectionAsync(stored.Id, UserId, chosen);

        outcome.Should().Be(SelectionOutcome.Recorded);
        stored.SelectedProductId.Should().Be(chosen);
        stored.SelectedFromRank.Should().Be(2, "the client sends no rank; the server derives it");
        stored.SelectedAt.Should().NotBeNull();
    }

    [Fact]
    public async Task RecordSelection_WhenProductNotInResults_PersistsSelectionWithNullRank()
    {
        var service = CreateService();
        var stored = EventWith([Result("SKU-1", Guid.NewGuid())]);
        _events.Setup(r => r.GetByIdAsync(stored.Id)).ReturnsAsync(stored);
        var stranger = Guid.NewGuid();

        var outcome = await service.RecordSelectionAsync(stored.Id, UserId, stranger);

        outcome.Should().Be(SelectionOutcome.Recorded);
        stored.SelectedProductId.Should().Be(stranger, "the event must not read as abandoned");
        stored.SelectedFromRank.Should().BeNull("a null drops out of the rank KPI without distorting it");
        _logs.At(LogLevel.Warning).Should().ContainSingle(
            e => e.Template.StartsWith("search_event_selection_outside_results"));
    }

    [Fact]
    public async Task RecordSelection_WhenCalledTwice_KeepsLastSelection()
    {
        var service = CreateService();
        var first = Guid.NewGuid();
        var second = Guid.NewGuid();
        var stored = EventWith([Result("SKU-1", first), Result("SKU-2", second)]);
        _events.Setup(r => r.GetByIdAsync(stored.Id)).ReturnsAsync(stored);

        await service.RecordSelectionAsync(stored.Id, UserId, first);
        var outcome = await service.RecordSelectionAsync(stored.Id, UserId, second);

        outcome.Should().Be(SelectionOutcome.Recorded, "picking again is not a conflict");
        stored.SelectedProductId.Should().Be(second);
        stored.SelectedFromRank.Should().Be(2);
    }

    [Fact]
    public async Task RecordSelection_WhenEventDoesNotExist_ReportsNotFound()
    {
        var service = CreateService();
        _events.Setup(r => r.GetByIdAsync(It.IsAny<Guid>())).ReturnsAsync((ProductSearchEvent?)null);

        var outcome = await service.RecordSelectionAsync(Guid.NewGuid(), UserId, Guid.NewGuid());

        outcome.Should().Be(SelectionOutcome.EventNotFound);
    }

    [Fact]
    public async Task RecordSelection_WhenEventBelongsToAnotherUser_ReportsNotOwnerAndChangesNothing()
    {
        var service = CreateService();
        var stored = EventWith([Result("SKU-1", Guid.NewGuid())]);
        _events.Setup(r => r.GetByIdAsync(stored.Id)).ReturnsAsync(stored);

        var outcome = await service.RecordSelectionAsync(stored.Id, Guid.NewGuid(), Guid.NewGuid());

        outcome.Should().Be(SelectionOutcome.NotOwner);
        stored.SelectedProductId.Should().BeNull();
        stored.SelectedAt.Should().BeNull();
        _unitOfWork.Verify(u => u.SaveChangesAsync(), Times.Never);
    }

    /// <summary>
    /// Builds a stored event by running the real recording path, so the tests read back exactly
    /// the JSON the service writes rather than a hand-rolled imitation of it.
    /// </summary>
    private ProductSearchEvent EventWith(IReadOnlyList<AiSearchResult> results)
    {
        var service = CreateService();
        service.RecordSearchAsync(Request(results)).GetAwaiter().GetResult();
        var stored = _added.Single();
        _added.Clear();
        _unitOfWork.Invocations.Clear();
        return stored;
    }
}
