using System.Net;
using System.Net.Http.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.DTOs.Products;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for product family management.
/// </summary>
/// <remarks>
/// Run against the real host because the things worth protecting here are all boundary behaviour:
/// the authorization split between writing and reading, the difference between an orphan product and
/// a missing one, and — above all — what the database does when a declaration reorders members that
/// three unique indexes are watching.
/// </remarks>
[Collection(IntegrationTestCollection.Name)]
public class ProductFamiliesControllerTests : IAsyncLifetime
{
    private const string Endpoint = "/api/product-families";

    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;

    private PointOfSale _pos = null!;
    private Product _small = null!;
    private Product _medium = null!;
    private Product _large = null!;
    private Product _loner = null!;

    public ProductFamiliesControllerTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();

        using var mother = new TestDataMother(_factory.Services);

        _pos = await mother.PointOfSale()
            .WithCode("FAMILY-POS")
            .WithName("Family Point of Sale")
            .WithAddress("Test Address")
            // Pinned: the generator produces phone numbers of varying length and the column is
            // varchar(20), so leaving it to chance makes the suite fail intermittently.
            .WithPhone("600123456")
            .CreateAsync();

        _small = await mother.Product().WithSku("ERIZO-S").WithName("Anillo erizo de mar").CreateAsync();
        _medium = await mother.Product().WithSku("ERIZO-M").WithName("Anillo erizo de mar").CreateAsync();
        _large = await mother.Product().WithSku("ERIZO-L").WithName("Anillo erizo de mar").CreateAsync();
        _loner = await mother.Product().WithSku("SOLO-1").WithName("Colgante único").CreateAsync();

        await mother.User()
            .WithUsername("familyoperator")
            .AsOperator()
            .AssignedTo(_pos.Id)
            .CreateAsync();
    }

    public Task DisposeAsync() => Task.CompletedTask;

    // ── Creation and ordering ─────────────────────────────────────────────────────────────────

    [Fact]
    public async Task CreateFamily_WithMembers_PersistsOrder()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.PostAsJsonAsync(Endpoint, new CreateProductFamilyRequest
        {
            Name = "Anillo erizo de mar",
            Members =
            [
                new ProductFamilyMemberRequest { ProductId = _small.Id, VariantLabel = "S" },
                new ProductFamilyMemberRequest { ProductId = _medium.Id, VariantLabel = "M" },
                new ProductFamilyMemberRequest { ProductId = _large.Id, VariantLabel = "L" }
            ]
        });

        response.StatusCode.Should().Be(HttpStatusCode.Created);

        var family = await response.Content.ReadFromJsonAsync<ProductFamilyDto>();
        family!.Members.Select(member => member.ProductId)
            .Should().Equal([_small.Id, _medium.Id, _large.Id],
                "the declared order is the order, and it is taken from the position in the list");
        family.Members.Select(member => member.SortOrder).Should().Equal([0, 1, 2]);
        family.Origin.Should().Be("Manual", "this change only ever creates families by hand");
    }

    [Fact]
    public async Task GetFamily_ReturnsSiblingsOrderedBySortOrder()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium), ("L", _large));

        var response = await admin.GetAsync($"/api/products/{_medium.Id}/family");

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var family = await response.Content.ReadFromJsonAsync<ProductFamilyDto>();
        family!.Id.Should().Be(familyId);
        family.Members.Select(member => member.VariantLabel).Should().Equal(["S", "M", "L"]);
        family.Members.Select(member => member.Sku).Should().Equal(["ERIZO-S", "ERIZO-M", "ERIZO-L"],
            "a sibling carries enough of its product to be identified without a second call");
    }

    // ── Single membership ─────────────────────────────────────────────────────────────────────

    [Fact]
    public async Task AddMember_WhenProductAlreadyInAnotherFamily_ReturnsConflict()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var first = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium));
        var second = await CreateFamilyAsync(admin, ("único", _loner));

        var response = await admin.PutAsJsonAsync(
            $"{Endpoint}/{second}/members",
            new ReplaceFamilyMembersRequest
            {
                Members =
                [
                    new ProductFamilyMemberRequest { ProductId = _loner.Id, VariantLabel = "único" },
                    new ProductFamilyMemberRequest { ProductId = _small.Id, VariantLabel = "S" }
                ]
            });

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);

        var body = await response.Content.ReadAsStringAsync();
        body.Should().Contain(_small.Id.ToString(), "the rejection has to name the offending product");
        body.Should().Contain(first.ToString(), "and the family that already holds it");

        await AssertMembershipAsync(_small.Id, first);
    }

    // ── Declarative replacement ───────────────────────────────────────────────────────────────

    [Fact]
    public async Task RemoveMember_KeepsFamilyWhenOthersRemain()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium), ("L", _large));

        var response = await ReplaceMembersAsync(admin, familyId, ("S", _small), ("L", _large));

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var family = await response.Content.ReadFromJsonAsync<ProductFamilyDto>();
        family!.Members.Select(member => member.ProductId).Should().Equal([_small.Id, _large.Id]);
        family.Members.Select(member => member.SortOrder).Should().Equal([0, 1],
            "the positions close up: what is left has no gap in it");

        await AssertNoMembershipAsync(_medium.Id);
    }

    [Fact]
    public async Task ReplaceMembers_WithEmptyList_LeavesFamilyWithoutMembers()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium));

        var response = await admin.PutAsJsonAsync(
            $"{Endpoint}/{familyId}/members",
            new ReplaceFamilyMembersRequest { Members = [] });

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var family = await response.Content.ReadFromJsonAsync<ProductFamilyDto>();
        family!.Members.Should().BeEmpty("emptying a family is how it is dissolved without deleting it");

        await AssertNoMembershipAsync(_small.Id);
        await AssertNoMembershipAsync(_medium.Id);

        (await admin.GetAsync($"{Endpoint}/{familyId}")).StatusCode.Should().Be(HttpStatusCode.OK,
            "the family itself survives losing every member");
    }

    /// <summary>
    /// The test that decides how the replacement is written.
    /// </summary>
    /// <remarks>
    /// Swapping two positions means each row moving to a value the other still holds, and a unique
    /// index over family and position is watching. Reconciling row by row would make this a cycle of
    /// updates the change tracker cannot order; deleting everything and inserting the new set leaves
    /// it an acyclic graph. If this ever goes red, the fix is to stage the write — delete and save,
    /// insert and save, commit — inside an explicit transaction.
    /// </remarks>
    [Fact]
    public async Task ReplaceMembers_ReorderingExistingMembers_Succeeds()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium), ("L", _large));

        var response = await ReplaceMembersAsync(
            admin, familyId, ("L", _large), ("M", _medium), ("S", _small));

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var family = await response.Content.ReadFromJsonAsync<ProductFamilyDto>();
        family!.Members.Select(member => member.ProductId)
            .Should().Equal([_large.Id, _medium.Id, _small.Id]);
        family.Members.Select(member => member.SortOrder).Should().Equal([0, 1, 2]);
    }

    /// <summary>
    /// The same hazard on the other unique index: correcting two labels that were swapped means each
    /// moving to the value the other holds.
    /// </summary>
    [Fact]
    public async Task ReplaceMembers_SwappingTwoVariantLabels_Succeeds()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium));

        var response = await ReplaceMembersAsync(admin, familyId, ("M", _small), ("S", _medium));

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var family = await response.Content.ReadFromJsonAsync<ProductFamilyDto>();
        family!.Members.Should().SatisfyRespectively(
            first => { first.ProductId.Should().Be(_small.Id); first.VariantLabel.Should().Be("M"); },
            second => { second.ProductId.Should().Be(_medium.Id); second.VariantLabel.Should().Be("S"); });
    }

    [Fact]
    public async Task ReplaceMembers_WithIdenticalList_DoesNotRewriteRows()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small), ("M", _medium));

        var before = await MemberTimestampsAsync(familyId);

        var response = await ReplaceMembersAsync(admin, familyId, ("S", _small), ("M", _medium));
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var after = await MemberTimestampsAsync(familyId);

        after.Should().Equal(before,
            "rewriting identical rows would bump their timestamps and hand the indexing feed a "
            + "change that did not happen, making it re-emit every member of the family for nothing");
    }

    [Fact]
    public async Task ReplaceMembers_WithTwoUnlabelledMembers_Succeeds()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small));

        var response = await ReplaceMembersAsync(admin, familyId, (null, _small), (null, _medium));

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "a member whose variant is not known yet is a legitimate state, and nulls do not "
            + "collide with each other in PostgreSQL");

        var family = await response.Content.ReadFromJsonAsync<ProductFamilyDto>();
        family!.Members.Should().HaveCount(2);
        family.Members.Should().OnlyContain(member => member.VariantLabel == null);
    }

    [Fact]
    public async Task ReplaceMembers_WithDuplicateVariantLabel_ReturnsBadRequest()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small));

        var response = await ReplaceMembersAsync(admin, familyId, ("M", _small), ("M", _medium));

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest,
            "two members labelled the same defeat the point of the family, and this is caught in "
            + "the request rather than as a constraint violation the caller cannot act on");
    }

    [Fact]
    public async Task ReplaceMembers_WithSameProductTwice_ReturnsBadRequest()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        var familyId = await CreateFamilyAsync(admin, ("S", _small));

        var response = await ReplaceMembersAsync(admin, familyId, ("S", _small), ("M", _small));

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    // ── Orphan versus missing ─────────────────────────────────────────────────────────────────

    [Fact]
    public async Task GetFamily_WhenProductHasNoFamily_Returns204()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.GetAsync($"/api/products/{_loner.Id}/family");

        response.StatusCode.Should().Be(HttpStatusCode.NoContent,
            "roughly one in seven products is an orphan by design, and the caller has to be able "
            + "to tell that from a bad identifier");
    }

    [Fact]
    public async Task GetFamily_WhenProductDoesNotExist_Returns404()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");

        var response = await admin.GetAsync($"/api/products/{Guid.NewGuid()}/family");

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    // ── Authorization ─────────────────────────────────────────────────────────────────────────

    [Fact]
    public async Task CreateFamily_AsOperator_Returns403()
    {
        var operatorClient = await AuthenticateAsync("familyoperator", "Test123!");

        var response = await operatorClient.PostAsJsonAsync(Endpoint, new CreateProductFamilyRequest
        {
            Name = "Familia del operador"
        });

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        (await context.ProductFamilies.CountAsync()).Should().Be(0,
            "a rejected write must leave the catalogue exactly as it found it");
    }

    /// <summary>
    /// Asks the factory for a fresh client on purpose. The one this class holds has performed
    /// logins, so it carries their cookies and is not anonymous — the trap that turns a genuine 401
    /// assertion into a passing 403 or 201.
    /// </summary>
    [Fact]
    public async Task CreateFamily_Unauthenticated_Returns401()
    {
        var anonymous = _factory.CreateClient();

        var response = await anonymous.PostAsJsonAsync(Endpoint, new CreateProductFamilyRequest
        {
            Name = "Familia anónima"
        });

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    /// <summary>
    /// Reading is open to any authenticated user and is not filtered by point of sale: which
    /// variants exist is a fact about the catalogue, not about where stock happens to sit. The
    /// operator here has no inventory at all, and still sees every sibling.
    /// </summary>
    [Fact]
    public async Task GetFamily_AsOperator_ReturnsFamily()
    {
        var admin = await AuthenticateAsync("admin", "Admin123!");
        await CreateFamilyAsync(admin, ("S", _small), ("M", _medium), ("L", _large));

        var operatorClient = await AuthenticateAsync("familyoperator", "Test123!");

        var response = await operatorClient.GetAsync($"/api/products/{_small.Id}/family");

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var family = await response.Content.ReadFromJsonAsync<ProductFamilyDto>();
        family!.Members.Should().HaveCount(3,
            "the sibling list an operator sees is the same one an administrator sees");
    }

    // ── Helpers ───────────────────────────────────────────────────────────────────────────────

    private async Task<Guid> CreateFamilyAsync(
        HttpClient client,
        params (string? Label, Product Product)[] members)
    {
        var response = await client.PostAsJsonAsync(Endpoint, new CreateProductFamilyRequest
        {
            Name = "Anillo erizo de mar",
            Members = members
                .Select(member => new ProductFamilyMemberRequest
                {
                    ProductId = member.Product.Id,
                    VariantLabel = member.Label
                })
                .ToList()
        });

        response.EnsureSuccessStatusCode();

        var family = await response.Content.ReadFromJsonAsync<ProductFamilyDto>();
        return family!.Id;
    }

    private static Task<HttpResponseMessage> ReplaceMembersAsync(
        HttpClient client,
        Guid familyId,
        params (string? Label, Product Product)[] members) =>
        client.PutAsJsonAsync(
            $"{Endpoint}/{familyId}/members",
            new ReplaceFamilyMembersRequest
            {
                Members = members
                    .Select(member => new ProductFamilyMemberRequest
                    {
                        ProductId = member.Product.Id,
                        VariantLabel = member.Label
                    })
                    .ToList()
            });

    private async Task<List<DateTime>> MemberTimestampsAsync(Guid familyId)
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        return await context.ProductFamilyMembers
            .Where(member => member.ProductFamilyId == familyId)
            .OrderBy(member => member.SortOrder)
            .Select(member => member.UpdatedAt)
            .ToListAsync();
    }

    private async Task AssertMembershipAsync(Guid productId, Guid expectedFamilyId)
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        var membership = await context.ProductFamilyMembers
            .SingleOrDefaultAsync(member => member.ProductId == productId);

        membership.Should().NotBeNull();
        membership!.ProductFamilyId.Should().Be(expectedFamilyId);
    }

    private async Task AssertNoMembershipAsync(Guid productId)
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        (await context.ProductFamilyMembers.AnyAsync(member => member.ProductId == productId))
            .Should().BeFalse("a product removed from a family belongs to none");
    }

    private async Task<HttpClient> AuthenticateAsync(string username, string password)
    {
        var login = await _client.PostAsJsonAsync(
            "/api/auth/login",
            new LoginRequest { Username = username, Password = password });
        login.EnsureSuccessStatusCode();

        var authenticated = _factory.CreateClient();
        foreach (var cookie in login.Headers.GetValues("Set-Cookie"))
        {
            var parts = cookie.Split(';')[0].Split('=');
            if (parts.Length == 2)
            {
                authenticated.DefaultRequestHeaders.Add("Cookie", $"{parts[0]}={parts[1]}");
            }
        }

        return authenticated;
    }
}
