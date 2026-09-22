using System.Globalization;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.DTOs.Products;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Tests.TestHelpers;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for the two routes of the sale card, against a real PostgreSQL and a gateway
/// double.
/// </summary>
/// <remarks>
/// <para>
/// <strong>These reach the gateway, and every served test proves it.</strong> The integration
/// tests of assisted search never do: with no <c>AiSearch</c> section the switch is false and they
/// walk the disabled path, so a copy of that pattern here would stay green without ever hydrating
/// an AI response. The host below switches the card on explicitly and replaces the gateway with a
/// double that counts its calls, and each test asserts the count.
/// </para>
/// <para>
/// Families are created through <c>POST /api/product-families</c> as an administrator: there is
/// no object mother for them on purpose, because the service is what stamps the catalog watermark.
/// </para>
/// </remarks>
[Collection(IntegrationTestCollection.Name)]
public class AiSalesAssistControllerTests : IAsyncLifetime
{
    private static readonly CultureInfo Spanish = CultureInfo.GetCultureInfo("es-ES");

    private const string Template = "Pendientes de plata, disponibles por {{price}} y tenemos {{stock}} en tienda.";

    private readonly ApiWebApplicationFactory _sharedFactory;
    private readonly HttpClient _warmUpClient;
    private readonly RecordingGateway _gateway = new();

    private WebApplicationFactory<Program> _factory = null!;
    private PointOfSale _pos = null!;
    private PointOfSale _otherPos = null!;
    private PointOfSale _closedPos = null!;
    private Product _anchor = null!;
    private Product _sibling = null!;
    private Product _elsewhere = null!;
    private Product _soldOut = null!;
    private Product _substituteA = null!;
    private Product _substituteB = null!;
    private HttpClient _operator = null!;
    private HttpClient _admin = null!;

    public AiSalesAssistControllerTests(ApiWebApplicationFactory sharedFactory)
    {
        _sharedFactory = sharedFactory;

        // Builds the shared host, which applies the migrations before the reset below.
        _warmUpClient = sharedFactory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        await _sharedFactory.ResetDatabaseAsync();

        using var mother = new TestDataMother(_sharedFactory.Services);

        // Phone pinned on every point of sale: the generator produces numbers of varying length
        // and the column is varchar(20).
        _pos = await mother.PointOfSale().WithCode("CARD-POS").WithName("Card Point of Sale")
            .WithAddress("Test Address").WithPhone("600123456").CreateAsync();
        _otherPos = await mother.PointOfSale().WithCode("CARD-OTHER").WithName("Other Point of Sale")
            .WithAddress("Test Address").WithPhone("600123456").CreateAsync();
        _closedPos = await mother.PointOfSale().WithCode("CARD-CLOSED").WithName("Closed Point of Sale")
            .WithAddress("Test Address").WithPhone("600123456").Inactive().CreateAsync();

        _anchor = await mother.Product().WithSku("ERIZO-M").WithName("Pendiente erizo M").WithPrice(39.90m).CreateAsync();
        _sibling = await mother.Product().WithSku("ERIZO-S").WithName("Pendiente erizo S").WithPrice(35.00m).CreateAsync();
        _elsewhere = await mother.Product().WithSku("ERIZO-L").WithName("Pendiente erizo L").WithPrice(44.00m).CreateAsync();
        _soldOut = await mother.Product().WithSku("AROS-1").WithName("Aros de plata").WithPrice(25.00m).CreateAsync();
        _substituteA = await mother.Product().WithSku("SUB-A").WithName("Pendiente coral").WithPrice(41.00m).CreateAsync();
        _substituteB = await mother.Product().WithSku("SUB-B").WithName("Pendiente estrella").WithPrice(38.00m).CreateAsync();

        await mother.Inventory().WithProduct(_anchor.Id).WithPointOfSale(_pos.Id).WithQuantity(3).CreateAsync();
        await mother.Inventory().WithProduct(_sibling.Id).WithPointOfSale(_pos.Id).WithQuantity(0).CreateAsync();
        await mother.Inventory().WithProduct(_elsewhere.Id).WithPointOfSale(_otherPos.Id).WithQuantity(9).CreateAsync();
        await mother.Inventory().WithProduct(_soldOut.Id).WithPointOfSale(_pos.Id).WithQuantity(0).CreateAsync();
        await mother.Inventory().WithProduct(_substituteA.Id).WithPointOfSale(_pos.Id).WithQuantity(2).CreateAsync();
        await mother.Inventory().WithProduct(_substituteB.Id).WithPointOfSale(_pos.Id).WithQuantity(5).CreateAsync();
        await mother.Inventory().WithProduct(_anchor.Id).WithPointOfSale(_closedPos.Id).WithQuantity(1).CreateAsync();

        await mother.User().WithUsername("cardoperator").AsOperator().AssignedTo(_pos.Id).CreateAsync();

        // The card switched on explicitly, and the gateway replaced by a double that counts.
        _factory = _sharedFactory.WithWebHostBuilder(builder =>
        {
            builder.UseSetting("AiSalesAssist:EnabledByDefault", "true");
            builder.ConfigureServices(services => services.AddScoped<IAiGatewayClient>(_ => _gateway));
        });

        _operator = await AuthenticateAsync(_factory, "cardoperator", "Test123!");
        _admin = await AuthenticateAsync(_factory, "admin", "Admin123!");

        // The family is declared as the business declares it: through the API, as an administrator.
        var family = await _admin.PostAsJsonAsync("/api/product-families", new CreateProductFamilyRequest
        {
            Name = "Pendiente erizo",
            Members =
            [
                new ProductFamilyMemberRequest { ProductId = _sibling.Id, VariantLabel = "S" },
                new ProductFamilyMemberRequest { ProductId = _anchor.Id, VariantLabel = "M" },
                new ProductFamilyMemberRequest { ProductId = _elsewhere.Id, VariantLabel = "L" }
            ]
        });
        family.StatusCode.Should().Be(HttpStatusCode.Created);
    }

    public Task DisposeAsync()
    {
        _factory?.Dispose();
        return Task.CompletedTask;
    }

    // ---------------------------------------------------------------- scope, before any call (6.1 · 7.1)

    [Fact]
    public async Task SalesAssist_AsOperatorOfAnotherPos_Returns403()
    {
        var response = await AssistAsync(_operator, _anchor.Id, _otherPos.Id);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
        _gateway.AssistCalls.Should().Be(0, "a request about to be refused never costs a paid call");
    }

    [Fact]
    public async Task Substitutes_AsOperatorOfAnotherPos_Returns403()
    {
        var response = await SubstitutesAsync(_operator, _anchor.Id, _otherPos.Id);

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
        _gateway.SubstitutesCalls.Should().Be(0);
    }

    [Fact]
    public async Task SalesAssist_AnchorNotCarriedAtPos_Returns404WithoutCallingAi()
    {
        var asOperator = await AssistAsync(_operator, _elsewhere.Id, _pos.Id);
        var asAdmin = await AssistAsync(_admin, _elsewhere.Id, _pos.Id);

        asOperator.StatusCode.Should().Be(HttpStatusCode.NotFound);
        asAdmin.StatusCode.Should().Be(HttpStatusCode.NotFound, "the same for every role");
        _gateway.AssistCalls.Should().Be(0);
    }

    [Fact]
    public async Task Substitutes_AnchorNotCarriedAtPos_Returns404WithoutCallingAi()
    {
        var response = await SubstitutesAsync(_operator, _elsewhere.Id, _pos.Id);

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
        _gateway.SubstitutesCalls.Should().Be(0);
    }

    [Fact]
    public async Task SalesAssist_WhenPointOfSaleInactive_IsRefused()
    {
        var response = await AssistAsync(_admin, _anchor.Id, _closedPos.Id);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest, "nobody, whatever their role, uses a closed shop");
        _gateway.AssistCalls.Should().Be(0);
    }

    [Fact]
    public async Task SalesAssist_WithoutPointOfSale_Returns400WithoutCallingAi()
    {
        var response = await _operator.PostAsJsonAsync($"/api/ai/products/{_anchor.Id}/sales-assist", new { });
        var noBody = await _operator.PostAsync(
            $"/api/ai/products/{_anchor.Id}/sales-assist",
            new StringContent("", System.Text.Encoding.UTF8, "application/json"));
        var substitutes = await _operator.GetAsync($"/api/ai/products/{_anchor.Id}/substitutes");

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        noBody.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        substitutes.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        _gateway.AssistCalls.Should().Be(0);
        _gateway.SubstitutesCalls.Should().Be(0);
    }

    [Theory]
    [InlineData("   ")]
    [InlineData(null)]
    public async Task SalesAssist_WithAnInvalidQuestion_Returns400WithoutCallingAi(string? question)
    {
        var response = await AssistAsync(_operator, _anchor.Id, _pos.Id, question ?? new string('a', 501));

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        _gateway.AssistCalls.Should().Be(0);
    }

    [Fact]
    public async Task Substitutes_WithPageSizeAboveTheMaximum_Returns400WithoutCallingAi()
    {
        var response = await SubstitutesAsync(_operator, _anchor.Id, _pos.Id, pageSize: 21);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        _gateway.SubstitutesCalls.Should().Be(0);
    }

    [Fact]
    public async Task SalesAssist_AnchorWithZeroStock_IsServed()
    {
        _gateway.Assist = _ => Ai(Member(_soldOut));

        var response = await AssistAsync(_operator, _soldOut.Id, _pos.Id);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        _gateway.AssistCalls.Should().Be(1);

        var body = await ReadAsync<SalesAssistResponse>(response);
        var anchor = body.Groups.Single().Members.Single();
        anchor.QuantityAtPointOfSale.Should().Be(0);
        anchor.HasStock.Should().BeFalse();
    }

    /// <summary>
    /// Asks the factory for a fresh client on purpose: the ones this class holds have logged in and
    /// carry cookies, which turns a genuine 401 into a passing 200 or 403.
    /// </summary>
    [Fact]
    public async Task SalesAssist_WhenUnauthenticated_Returns401()
    {
        var anonymous = _factory.CreateClient();

        (await AssistAsync(anonymous, _anchor.Id, _pos.Id)).StatusCode.Should().Be(HttpStatusCode.Unauthorized);
        (await SubstitutesAsync(anonymous, _anchor.Id, _pos.Id)).StatusCode.Should().Be(HttpStatusCode.Unauthorized);
        _gateway.AssistCalls.Should().Be(0);
        _gateway.SubstitutesCalls.Should().Be(0);
    }

    // ---------------------------------------------------------------- the question (8.3)

    [Fact]
    public async Task SalesAssist_QuestionTravelsInTheBodyNeverInTheUrl()
    {
        _gateway.Assist = _ => Ai(Member(_anchor));

        var fromBody = await _operator.PostAsJsonAsync(
            $"/api/ai/products/{_anchor.Id}/sales-assist?question=desde-la-url",
            new SalesAssistRequest { PointOfSaleId = _pos.Id, Question = "¿Se puede mojar?" });
        fromBody.StatusCode.Should().Be(HttpStatusCode.OK);
        _gateway.LastAssistRequest!.Query.Should().Be("¿Se puede mojar?");

        var onlyInUrl = await _operator.PostAsJsonAsync(
            $"/api/ai/products/{_anchor.Id}/sales-assist?question=desde-la-url",
            new SalesAssistRequest { PointOfSaleId = _pos.Id });
        onlyInUrl.StatusCode.Should().Be(HttpStatusCode.OK);
        _gateway.LastAssistRequest!.Query.Should().BeNull("nothing in the query string is read");

        var asGet = await _operator.GetAsync(
            $"/api/ai/products/{_anchor.Id}/sales-assist?pointOfSaleId={_pos.Id}&question=hola");
        // No GET route exists: a GET could be prefetched, and every prefetch would be a paid call.
        // This host answers an unmatched verb with 404 rather than 405, as AiCatalog_ExposesNoReadRoute
        // already accepts; either way the request reaches no action.
        asGet.StatusCode.Should().BeOneOf(HttpStatusCode.NotFound, HttpStatusCode.MethodNotAllowed);

        _gateway.AssistCalls.Should().Be(2);
        _gateway.LastScope!.PointOfSaleId.Should().Be(_pos.Id, "the scope comes from the validated request");
    }

    [Theory]
    [InlineData("/api/ai/products/assist")]
    [InlineData("/api/ai/products/agent")]
    public async Task SalesCard_ExposesNoRouteForAFreeQuestionOrTheAgent(string path)
    {
        var response = await _operator.PostAsJsonAsync(path, new { query = "anillos de plata", pointOfSaleId = _pos.Id });

        response.StatusCode.Should().BeOneOf(HttpStatusCode.NotFound, HttpStatusCode.MethodNotAllowed);
        _gateway.AssistCalls.Should().Be(0);
    }

    // ---------------------------------------------------------------- served flows (9.2)

    /// <summary>
    /// M2 end to end: the group of the AI service hydrated against the shop, the member it does
    /// not carry dropped, the stock warnings computed here, and the argument resolved against the
    /// anchored product — price in Spanish currency, the stock as a whole number.
    /// </summary>
    [Fact]
    public async Task SalesAssist_M2_ServesTheHydratedGroupAndTheResolvedArgument()
    {
        _gateway.Assist = _ => Ai([Member(_sibling, "S"), Member(_anchor, "M"), Member(_elsewhere, "L")],
            warnings: ["family_has_variants", "size_label_missing"]);

        var response = await AssistAsync(_operator, _anchor.Id, _pos.Id);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        _gateway.AssistCalls.Should().Be(1);

        var body = await ReadAsync<SalesAssistResponse>(response);
        body.AiAvailable.Should().BeTrue();
        body.Intent.Should().Be("product_pitch");

        var members = body.Groups.Single().Members;
        members.Select(m => m.Sku).Should().Equal("ERIZO-S", "ERIZO-M");
        members.Single(m => m.IsAnchor).Price.Should().Be(39.90m);
        members.Single(m => m.IsAnchor).QuantityAtPointOfSale.Should().Be(3);

        body.Warnings.Should().Equal("family_has_variants", "size_label_missing", "family_members_out_of_stock");

        body.PitchStatus.Should().Be(PitchStatus.Generated);
        body.Pitch.Should().Be(
            $"Pendientes de plata, disponibles por {39.90m.ToString("C2", Spanish)} y tenemos 3 en tienda.");

        (await response.Content.ReadAsStringAsync()).Should().Contain("\"pitchStatus\":\"generated\"");
    }

    [Fact]
    public async Task SalesAssist_M3_ReturnsCitationsWithTheirScope()
    {
        _gateway.Assist = _ => Ai([Member(_anchor)], citations:
        [
            new AiCitation
            {
                CitationId = "garantia#devoluciones", DocumentTitle = "Garantía", SectionTitle = "Devoluciones",
                DocType = "politica", ClaimScope = "establecimiento", Score = 0.7, Snippet = "Quince días."
            }
        ]);

        var response = await AssistAsync(_operator, _anchor.Id, _pos.Id, "¿La puedo devolver?");

        var body = await ReadAsync<SalesAssistResponse>(response);
        _gateway.AssistCalls.Should().Be(1);
        body.Citations.Should().ContainSingle().Which.ClaimScope.Should().Be("establecimiento");
        body.Citations[0].SectionTitle.Should().Be("Devoluciones");
    }

    [Fact]
    public async Task SalesAssist_SoldOutAnchor_WithholdsTheArgumentWithoutQuestion_AndAnswersWithOne()
    {
        _gateway.Assist = _ => Ai(Member(_soldOut));

        var withoutQuestion = await ReadAsync<SalesAssistResponse>(await AssistAsync(_operator, _soldOut.Id, _pos.Id));
        var withQuestion = await ReadAsync<SalesAssistResponse>(
            await AssistAsync(_operator, _soldOut.Id, _pos.Id, "¿Es plata de ley?"));

        _gateway.AssistCalls.Should().Be(2);
        withoutQuestion.PitchStatus.Should().Be(PitchStatus.WithheldOutOfStock);
        withoutQuestion.Pitch.Should().BeNull();
        withQuestion.PitchStatus.Should().Be(PitchStatus.Generated);
        withQuestion.Pitch.Should().Contain("tenemos 0 en tienda");
    }

    [Fact]
    public async Task SalesAssist_UnresolvedPlaceholder_WithholdsTheArgumentAndKeepsTheRest()
    {
        _gateway.Assist = _ => Ai([Member(_anchor)], pitch: "La tienes por {{precio}} hoy.", warnings: ["size_label_missing"]);

        var response = await AssistAsync(_operator, _anchor.Id, _pos.Id);
        var raw = await response.Content.ReadAsStringAsync();
        var body = JsonSerializer.Deserialize<SalesAssistResponse>(raw, Json)!;

        _gateway.AssistCalls.Should().Be(1);
        body.PitchStatus.Should().Be(PitchStatus.WithheldUnresolved);
        body.Groups.Should().NotBeEmpty();
        body.Warnings.Should().Contain("size_label_missing");
        raw.Should().NotContain("{{precio}}").And.NotContain("La tienes por");
    }

    /// <summary>
    /// The AI does not answer: the card comes from the catalog — the family as the business
    /// declared it, in its order and with its labels, only what this shop carries — with the
    /// stock and variants warnings computed here, and no argument.
    /// </summary>
    [Fact]
    public async Task SalesAssist_WhenAiUnavailable_ServesTheFamilyFromTheCatalog()
    {
        _gateway.Assist = _ => throw new AiUnavailableException("circuit open");

        var response = await AssistAsync(_operator, _anchor.Id, _pos.Id);

        response.StatusCode.Should().Be(HttpStatusCode.OK, "the card never breaks because of the AI");
        _gateway.AssistCalls.Should().Be(1);

        var body = await ReadAsync<SalesAssistResponse>(response);
        body.AiAvailable.Should().BeFalse();
        body.PitchStatus.Should().Be(PitchStatus.AiUnavailable);
        body.Pitch.Should().BeNull();
        body.Citations.Should().BeEmpty();

        var group = body.Groups.Single();
        group.FamilyLabel.Should().Be("Pendiente erizo");
        group.Members.Select(m => (m.Sku, m.VariantLabel)).Should().Equal(("ERIZO-S", "S"), ("ERIZO-M", "M"));
        body.Warnings.Should().Equal("family_has_variants", "family_members_out_of_stock");
    }

    [Fact]
    public async Task SalesAssist_WhenTheAiRejectsTheProduct_DegradesWithoutAServerError()
    {
        _gateway.Assist = _ => throw new AiRequestRejectedException(422, "not indexed");

        var response = await AssistAsync(_operator, _anchor.Id, _pos.Id);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        _gateway.AssistCalls.Should().Be(1);
        (await ReadAsync<SalesAssistResponse>(response)).AiAvailable.Should().BeFalse();
    }

    [Fact]
    public async Task SalesAssist_WhenSwitchedOff_DoesNotCallAi()
    {
        using var switchedOff = _sharedFactory.WithWebHostBuilder(builder =>
            builder.ConfigureServices(services => services.AddScoped<IAiGatewayClient>(_ => _gateway)));
        var client = await AuthenticateAsync(switchedOff, "cardoperator", "Test123!");

        var assist = await AssistAsync(client, _anchor.Id, _pos.Id);
        var substitutes = await SubstitutesAsync(client, _anchor.Id, _pos.Id);

        assist.StatusCode.Should().Be(HttpStatusCode.OK);
        (await ReadAsync<SalesAssistResponse>(assist)).AiAvailable.Should().BeFalse();
        (await ReadAsync<SubstitutesResponse>(substitutes)).Outcome.Should().Be(SubstitutesOutcome.AiUnavailable);
        _gateway.AssistCalls.Should().Be(0);
        _gateway.SubstitutesCalls.Should().Be(0);
    }

    // ---------------------------------------------------------------- substitutes (9.2)

    [Fact]
    public async Task Substitutes_OfferOnlyWhatTheShopCanSellToday_InTheOrderOfTheAi()
    {
        _gateway.Substitutes = _ => Window(_elsewhere, _sibling, _substituteB, _soldOut, _substituteA);

        var response = await SubstitutesAsync(_operator, _anchor.Id, _pos.Id);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        _gateway.SubstitutesCalls.Should().Be(1);
        _gateway.LastSubstitutesRequest!.TopK.Should().Be(20, "the largest window, in a single call");

        var body = await ReadAsync<SubstitutesResponse>(response);
        body.Outcome.Should().Be(SubstitutesOutcome.Ok);
        body.Results.Select(r => r.Sku).Should().Equal("SUB-B", "SUB-A");
        body.Results[0].Price.Should().Be(38.00m);
        body.CandidatesReturned.Should().Be(5);
        body.SurvivedHydration.Should().Be(4, "carried here, with or without units");

        var page = await ReadAsync<SubstitutesResponse>(await SubstitutesAsync(_operator, _anchor.Id, _pos.Id, pageSize: 1));
        page.Results.Select(r => r.Sku).Should().Equal("SUB-B");
    }

    public static TheoryData<string> FourOutcomes => new() { "ok", "none_in_stock", "product_not_indexed", "ai_unavailable" };

    [Theory]
    [MemberData(nameof(FourOutcomes))]
    public async Task Substitutes_TheFourOutcomesAreDistinguishable(string outcome)
    {
        _gateway.Substitutes = outcome switch
        {
            "ok" => _ => Window(_substituteA),
            "none_in_stock" => _ => Window(_soldOut, _sibling, _elsewhere),
            "product_not_indexed" => _ => throw new AiRequestRejectedException(422, "not indexed"),
            _ => _ => throw new AiUnavailableException("timeout")
        };

        var response = await SubstitutesAsync(_operator, _anchor.Id, _pos.Id);

        response.StatusCode.Should().Be(HttpStatusCode.OK, "none of the four is a server error");
        _gateway.SubstitutesCalls.Should().Be(1);
        (await response.Content.ReadAsStringAsync()).Should().Contain($"\"outcome\":\"{outcome}\"");
    }

    [Fact]
    public async Task Substitutes_OfASoldOutProduct_TellTheAiWhy()
    {
        _gateway.Substitutes = _ => Window(_substituteA);

        await SubstitutesAsync(_operator, _soldOut.Id, _pos.Id);

        _gateway.LastSubstitutesRequest!.Reason.Should().Be("sin_stock");
    }

    // ---------------------------------------------------------------- helpers

    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    private static async Task<T> ReadAsync<T>(HttpResponseMessage response)
    {
        response.StatusCode.Should().Be(HttpStatusCode.OK, await response.Content.ReadAsStringAsync());
        return (await response.Content.ReadFromJsonAsync<T>(Json))!;
    }

    private static Task<HttpResponseMessage> AssistAsync(HttpClient client, Guid productId, Guid posId, string? question = null) =>
        client.PostAsJsonAsync(
            $"/api/ai/products/{productId}/sales-assist",
            new SalesAssistRequest { PointOfSaleId = posId, Question = question });

    private static Task<HttpResponseMessage> SubstitutesAsync(HttpClient client, Guid productId, Guid posId, int? pageSize = null) =>
        client.GetAsync(
            $"/api/ai/products/{productId}/substitutes?pointOfSaleId={posId}"
            + (pageSize is null ? string.Empty : $"&pageSize={pageSize}"));

    private static async Task<HttpClient> AuthenticateAsync(WebApplicationFactory<Program> factory, string username, string password)
    {
        var client = factory.CreateClient();
        var login = await client.PostAsJsonAsync("/api/auth/login", new LoginRequest { Username = username, Password = password });
        login.EnsureSuccessStatusCode();
        return client;
    }

    private static AiAssistGroupMember Member(Product product, string? variant = null) =>
        new() { ProductId = product.Id.ToString(), Sku = product.SKU, VariantLabel = variant, Score = 0.8 };

    private static AiAssistSaleResponse Ai(params AiAssistGroupMember[] members) => Ai(members, warnings: null);

    private static AiAssistSaleResponse Ai(
        AiAssistGroupMember[] members,
        string pitch = Template,
        string[]? warnings = null,
        AiCitation[]? citations = null) => new()
    {
        TraceId = "trace-card",
        EffectivePosId = Guid.Empty.ToString(),
        Intent = "product_pitch",
        Groups = [new AiAssistGroup { FamilyId = "fam-1", FamilyLabel = "Pendiente erizo", Members = [.. members] }],
        Pitch = pitch,
        PromptVersion = "assist/v4",
        Warnings = [.. warnings ?? []],
        Citations = [.. citations ?? []],
        Usage = new AiUsage { PromptTokens = 900, CompletionTokens = 60, TotalTokens = 960, Model = "openai/gpt-4o-mini" }
    };

    private static AiSubstitutesResponse Window(params Product[] products) => new()
    {
        Results = products.Select(product => new AiSubstituteResult
        {
            ProductId = product.Id.ToString(),
            Sku = product.SKU,
            Score = 0.7,
            SimilaritySignals = new AiSimilaritySignals { MaterialOverlap = 1.0, StyleSimilarity = 0.6 }
        }).ToList(),
        CandidatesReturned = products.Length,
        TraceId = "trace-card",
        EffectivePosId = Guid.Empty.ToString()
    };

    /// <summary>
    /// The gateway double: answers what the test programs and counts what it is asked. Everything
    /// else throws, from the base class.
    /// </summary>
    private sealed class RecordingGateway : ThrowingAiGatewayClient
    {
        private int _assistCalls;
        private int _substitutesCalls;

        public Func<AiAssistSaleRequest, AiAssistSaleResponse> Assist { get; set; } =
            _ => throw new InvalidOperationException("No sale assistance response was programmed for this test.");

        public Func<AiSubstitutesRequest, AiSubstitutesResponse> Substitutes { get; set; } =
            _ => throw new InvalidOperationException("No substitutes response was programmed for this test.");

        public int AssistCalls => _assistCalls;

        public int SubstitutesCalls => _substitutesCalls;

        public AiAssistSaleRequest? LastAssistRequest { get; private set; }

        public AiSubstitutesRequest? LastSubstitutesRequest { get; private set; }

        public AiCallScope? LastScope { get; private set; }

        public override Task<AiAssistSaleResponse> AssistSaleAsync(
            AiAssistSaleRequest request, AiCallScope scope, CancellationToken cancellationToken = default)
        {
            Interlocked.Increment(ref _assistCalls);
            LastAssistRequest = request;
            LastScope = scope;
            return Task.FromResult(Assist(request));
        }

        public override Task<AiSubstitutesResponse> SubstitutesAsync(
            AiSubstitutesRequest request, AiCallScope scope, CancellationToken cancellationToken = default)
        {
            Interlocked.Increment(ref _substitutesCalls);
            LastSubstitutesRequest = request;
            LastScope = scope;
            return Task.FromResult(Substitutes(request));
        }
    }
}
