using FluentAssertions;
using JoiabagurPV.Tests.TestHelpers;
using Xunit;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Asserts the properties of the AI profile schema that fail silently when they are wrong.
/// </summary>
/// <remarks>
/// Nothing here checks that the migration applied — the fixture already proves that before every
/// integration test. What is checked is the handful of declarations whose mistakes raise no error
/// at all: a JSON column landing as text, an index that exists but does not enforce uniqueness,
/// and a delete rule left at the framework default. All three save data happily and are only
/// discovered once there is data to lose.
/// </remarks>
[Collection(RepositoryTestCollection.Name)]
public class ProductAiProfileSchemaTests
{
    private const string Table = "ProductAiProfiles";
    private readonly TestDatabaseFixture _fixture;

    public ProductAiProfileSchemaTests(TestDatabaseFixture fixture)
    {
        _fixture = fixture;
    }

    [Theory]
    [InlineData("MaterialsJson")]
    [InlineData("ColorTagsJson")]
    [InlineData("StyleTagsJson")]
    [InlineData("OccasionTagsJson")]
    [InlineData("FieldConfidenceJson")]
    [InlineData("FieldSourceJson")]
    [InlineData("ProposedProfileJson")]
    public async Task Migration_JsonColumnsAreJsonbNotText(string column)
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var type = await schema.ColumnTypeAsync(Table, column);

        type.Should().Be("jsonb",
            "these columns exist to be compared and aggregated in SQL — the correction rate per "
            + "field is a comparison between two of them — and as text both that and an invalid "
            + "stored document would fail silently");
    }

    [Fact]
    public async Task Migration_ProductIdIsUnique()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var isUnique = await schema.IndexIsUniqueAsync("IX_ProductAiProfiles_ProductId");

        isUnique.Should().BeTrue(
            "one profile per product is the invariant the indexing feed relies on; without "
            + "uniqueness a second profile saves without any error and surfaces later as "
            + "duplicated documents in the vector index");
    }

    [Theory]
    [InlineData("FK_ProductAiProfiles_Products_ProductId")]
    [InlineData("FK_ProductAiProfiles_Users_ReviewedByUserId")]
    public async Task Migration_DeletingProduct_IsRestrictedNotCascaded(string constraint)
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var rule = await schema.ForeignKeyDeleteRuleAsync(constraint);

        rule.Should().Be("RESTRICT",
            "the framework default for a required relationship is CASCADE, which here would mean "
            + "that deleting a product — or a user — silently destroys the record of the review "
            + "work done on it");
    }

    [Theory]
    [InlineData("PieceType")]
    [InlineData("StoneType")]
    [InlineData("SizeLabel")]
    [InlineData("GeneratedByModel")]
    [InlineData("PromptVersion")]
    [InlineData("ReviewedByUserId")]
    [InlineData("ReviewedAt")]
    [InlineData("ReviewDurationMs")]
    public async Task Migration_OptionalColumnsAcceptNull(string column)
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var isNullable = await schema.ColumnIsNullableAsync(Table, column);

        isNullable.Should().BeTrue(
            "a profile with no stone, no size, or no human review yet is a valid row");
    }

    [Theory]
    [InlineData("MaterialsJson")]
    [InlineData("ColorTagsJson")]
    [InlineData("StyleTagsJson")]
    [InlineData("OccasionTagsJson")]
    [InlineData("FieldConfidenceJson")]
    [InlineData("FieldSourceJson")]
    [InlineData("ProposedProfileJson")]
    [InlineData("SourceHash")]
    [InlineData("ReviewStatus")]
    [InlineData("ReviewOrigin")]
    public async Task Migration_RequiredColumnsRejectNull(string column)
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var isNullable = await schema.ColumnIsNullableAsync(Table, column);

        isNullable.Should().BeFalse(
            "an absence of evidence is an empty JSON array, never a null: a nullable list column "
            + "would force every reader to handle two shapes of nothing");
    }

    [Fact]
    public async Task Migration_ReviewQueueIndexOrdersStatusBeforeOrigin()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var columns = await schema.IndexColumnsAsync("IX_ProductAiProfiles_ReviewStatus_ReviewOrigin");

        columns.Should().Equal(["ReviewStatus", "ReviewOrigin"],
            "status is the equality predicate of both the indexing feed and the review queue; "
            + "reversed, the index still exists and simply stops serving them, without any error");
    }
}
