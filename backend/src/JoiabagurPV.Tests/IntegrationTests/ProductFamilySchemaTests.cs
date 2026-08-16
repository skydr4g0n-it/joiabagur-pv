using FluentAssertions;
using JoiabagurPV.Tests.TestHelpers;
using Xunit;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Asserts the properties of the product family schema that fail silently when they are wrong.
/// </summary>
/// <remarks>
/// Nothing here checks that the migration applied — the fixture already proves that before every
/// integration test. What is checked is the handful of declarations whose mistakes raise no error at
/// all: three unique indexes that would still exist as plain indexes and still serve every query,
/// and two delete rules left at the framework default. All of them save data happily and are only
/// discovered once there is data to lose.
/// </remarks>
[Collection(RepositoryTestCollection.Name)]
public class ProductFamilySchemaTests
{
    private const string FamilyTable = "ProductFamilies";
    private const string MemberTable = "ProductFamilyMembers";

    private readonly TestDatabaseFixture _fixture;

    public ProductFamilySchemaTests(TestDatabaseFixture fixture)
    {
        _fixture = fixture;
    }

    [Fact]
    public async Task Migration_ProductIdIsUnique()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var isUnique = await schema.IndexIsUniqueAsync("IX_ProductFamilyMembers_ProductId");

        isUnique.Should().BeTrue(
            "a product belongs to at most one family, and that is the invariant the indexing feed "
            + "relies on; without uniqueness a second membership saves without any error and "
            + "surfaces later as two family identifiers emitted for one product");
    }

    [Fact]
    public async Task Migration_SortOrderIsUniqueWithinFamily()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var isUnique = await schema.IndexIsUniqueAsync(
            "IX_ProductFamilyMembers_ProductFamilyId_SortOrder");

        isUnique.Should().BeTrue(
            "two members sharing a position still save and still read back, and simply return the "
            + "siblings in an order that differs between reads — which in a disambiguation screen "
            + "is worse than having no order at all");
    }

    [Fact]
    public async Task Migration_VariantLabelIsUniqueWithinFamily()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var isUnique = await schema.IndexIsUniqueAsync(
            "IX_ProductFamilyMembers_ProductFamilyId_VariantLabel");

        isUnique.Should().BeTrue(
            "two members labelled \"M\" in one family defeat the entire point of the family; nulls "
            + "do not collide with each other in PostgreSQL, so this index still allows any number "
            + "of members whose variant is not known yet");
    }

    [Fact]
    public async Task Migration_MembershipIndexOrdersFamilyBeforeSortOrder()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var columns = await schema.IndexColumnsAsync(
            "IX_ProductFamilyMembers_ProductFamilyId_SortOrder");

        columns.Should().Equal(["ProductFamilyId", "SortOrder"],
            "the family is the equality predicate and the position is the ordering; reversed, the "
            + "index still exists and simply stops serving the sibling read, without any error");
    }

    [Fact]
    public async Task Migration_DeletingFamily_CascadesToMembers()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var rule = await schema.ForeignKeyDeleteRuleAsync(
            "FK_ProductFamilyMembers_ProductFamilies_ProductFamilyId");

        rule.Should().Be("CASCADE",
            "members have no life of their own — they are the family — so dissolving one takes "
            + "them with it, and leaving them behind would strand rows pointing at nothing");
    }

    [Theory]
    [InlineData("FK_ProductFamilyMembers_Products_ProductId")]
    [InlineData("FK_ProductFamilies_Users_ApprovedByUserId")]
    public async Task Migration_DeletingProduct_IsRestrictedNotCascaded(string constraint)
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var rule = await schema.ForeignKeyDeleteRuleAsync(constraint);

        rule.Should().Be("RESTRICT",
            "the framework default for a required relationship is CASCADE, which here would mean "
            + "that deleting a product — or the user who approved a family — silently destroys the "
            + "curation done on it; a product is retired with IsActive anyway");
    }

    [Theory]
    [InlineData("ApprovedByUserId")]
    [InlineData("ApprovedAt")]
    [InlineData("Description")]
    public async Task Migration_ApprovalColumnsAcceptNull(string column)
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var isNullable = await schema.ColumnIsNullableAsync(FamilyTable, column);

        isNullable.Should().BeTrue(
            "a family created by hand has no approver and no approval instant, and must not have "
            + "to invent one — a fabricated reviewer would corrupt the very figure the column "
            + "exists to make countable");
    }

    [Fact]
    public async Task Migration_VariantLabelAcceptsNull()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var isNullable = await schema.ColumnIsNullableAsync(MemberTable, "VariantLabel");

        isNullable.Should().BeTrue(
            "a member whose variant has not been determined yet is a legitimate state the "
            + "rule-based warnings are meant to report, not a defect to block on");
    }

    [Theory]
    [InlineData(FamilyTable, "Name")]
    [InlineData(FamilyTable, "Origin")]
    [InlineData(MemberTable, "ProductFamilyId")]
    [InlineData(MemberTable, "ProductId")]
    [InlineData(MemberTable, "SortOrder")]
    public async Task Migration_RequiredColumnsRejectNull(string table, string column)
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var isNullable = await schema.ColumnIsNullableAsync(table, column);

        isNullable.Should().BeFalse(
            "a family without a name, or a membership without a product, a family or a position, "
            + "is not a partial row but a meaningless one");
    }

    [Fact]
    public async Task Migration_OriginIsIntegerNotNativeEnum()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var type = await schema.ColumnTypeAsync(FamilyTable, "Origin");

        type.Should().Be("integer",
            "a native PostgreSQL enum type survives its table being dropped, so a rollback leaves "
            + "an orphan that makes a later migration fail with \"type already exists\" — weeks "
            + "later, and with no obvious connection to this change");
    }
}
