using FluentAssertions;
using JoiabagurPV.Tests.TestHelpers;
using Xunit;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Asserts the properties of the search-event schema that fail silently when they are wrong.
/// </summary>
/// <remarks>
/// Nothing here checks that the migration applied — the fixture already proves that before
/// every integration test, so a test asserting it would discard no hypothesis. What is checked
/// is the handful of declarations whose mistakes raise no error at all and only surface once
/// there is data to lose.
/// </remarks>
[Collection(RepositoryTestCollection.Name)]
public class ProductSearchEventSchemaTests
{
    private const string Table = "ProductSearchEvents";
    private readonly TestDatabaseFixture _fixture;

    public ProductSearchEventSchemaTests(TestDatabaseFixture fixture)
    {
        _fixture = fixture;
    }

    [Theory]
    [InlineData("FiltersJson")]
    [InlineData("ResultsJson")]
    public async Task Migration_JsonColumnsAreJsonbNotText(string column)
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var type = await schema.ColumnTypeAsync(Table, column);

        type.Should().Be("jsonb",
            "the column exists to be aggregated in SQL, and jsonb also makes a byte-truncated "
            + "document impossible to store — as text, both failures would be silent");
    }

    [Fact]
    public async Task Migration_QueryTextIsBoundedToTheContractLength()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var length = await schema.ColumnMaxLengthAsync(Table, "SearchText");

        length.Should().Be(500,
            "the bound comes from query.maxLength in the frozen ai-service/openapi.json contract");
    }

    [Fact]
    public async Task Migration_CompositeIndexOrdersPointOfSaleBeforeCreatedAt()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var columns = await schema.IndexColumnsAsync("IX_ProductSearchEvents_PointOfSaleId_CreatedAt");

        columns.Should().Equal(["PointOfSaleId", "CreatedAt"],
            "point of sale is the equality predicate of the dominant query; reversed, the index "
            + "still exists and simply stops serving it, without any error");
    }

    [Theory]
    [InlineData("SelectedProductId")]
    [InlineData("SelectedFromRank")]
    [InlineData("SelectedAt")]
    [InlineData("TraceId")]
    [InlineData("RetrievalMs")]
    [InlineData("TotalMs")]
    public async Task Migration_OptionalColumnsAcceptNull(string column)
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var isNullable = await schema.ColumnIsNullableAsync(Table, column);

        isNullable.Should().BeTrue("a search with no selection, no trace or no timing is a valid row");
    }

    [Theory]
    [InlineData("UserId")]
    [InlineData("PointOfSaleId")]
    [InlineData("SearchSessionId")]
    [InlineData("SearchText")]
    [InlineData("ResultsCount")]
    [InlineData("SearchOrigin")]
    public async Task Migration_RequiredColumnsRejectNull(string column)
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var isNullable = await schema.ColumnIsNullableAsync(Table, column);

        isNullable.Should().BeFalse();
    }

    [Theory]
    [InlineData("FK_ProductSearchEvents_Users_UserId")]
    [InlineData("FK_ProductSearchEvents_PointOfSales_PointOfSaleId")]
    [InlineData("FK_ProductSearchEvents_Products_SelectedProductId")]
    public async Task Migration_BusinessEntitiesDoNotCascadeIntoTelemetry(string constraint)
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var rule = await schema.ForeignKeyDeleteRuleAsync(constraint);

        rule.Should().Be("RESTRICT",
            "the framework default for a required relationship is CASCADE, which here would mean "
            + "deleting an employee deletes the evidence of how the system was used");
    }

    [Fact]
    public async Task Migration_PurgingTelemetryNullsSaleAttributionInsteadOfBlockingIt()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var rule = await schema.ForeignKeyDeleteRuleAsync("FK_Sales_ProductSearchEvents_SearchEventId");

        rule.Should().Be("SET NULL",
            "telemetry is expendable: purging it must neither destroy a sale (CASCADE) nor be "
            + "blocked by one (RESTRICT)");
    }
}
