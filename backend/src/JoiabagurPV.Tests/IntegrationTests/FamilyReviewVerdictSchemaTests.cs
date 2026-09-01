using FluentAssertions;
using JoiabagurPV.Tests.TestHelpers;
using Xunit;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Asserts the properties of the family review verdict schema that fail silently when wrong.
/// </summary>
/// <remarks>
/// Every declaration checked here saves data happily when it is missing, and is only discovered
/// once there is something to lose: a pair that can be judged twice, a cascade that leaves
/// judgements pointing at a family that is gone, and two delete rules left at the framework
/// default where the default destroys evidence.
/// </remarks>
[Collection(RepositoryTestCollection.Name)]
public class FamilyReviewVerdictSchemaTests
{
    private const string Table = "FamilyReviewVerdicts";

    private readonly TestDatabaseFixture _fixture;

    public FamilyReviewVerdictSchemaTests(TestDatabaseFixture fixture)
    {
        _fixture = fixture;
    }

    [Fact]
    public async Task Migration_ProductAndFamilyPairIsUnique()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var isUnique = await schema.IndexIsUniqueAsync(
            "IX_FamilyReviewVerdicts_ProductId_ProductFamilyId");

        isUnique.Should().BeTrue(
            "the pair is the identity of a judgement, so judging it again is a correction and not "
            + "a second opinion; without uniqueness a reviewer who changes their mind leaves two "
            + "contradictory rows and the audit filter starts depending on which one it reads");
    }

    [Fact]
    public async Task Migration_PairIndexCoversBothColumnsInOrder()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var columns = await schema.IndexColumnsAsync(
            "IX_FamilyReviewVerdicts_ProductId_ProductFamilyId");

        columns.Should().Equal(
            ["ProductId", "ProductFamilyId"],
            "the audit filters by the pair, and an index over one column alone would still be "
            + "unique on nothing useful");
    }

    [Fact]
    public async Task Migration_DeletingAFamilyCascadesToItsVerdicts()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var rule = await schema.ForeignKeyDeleteRuleAsync(
            "FK_FamilyReviewVerdicts_ProductFamilies_ProductFamilyId");

        rule.Should().Be(
            "CASCADE",
            "a judgement about a family that no longer exists answers a question nobody can ask, "
            + "and leaving the rows behind would have the audit filtering against records that "
            + "point at nothing");
    }

    [Fact]
    public async Task Migration_DeletingAProductDoesNotDestroyItsVerdicts()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var rule = await schema.ForeignKeyDeleteRuleAsync(
            "FK_FamilyReviewVerdicts_Products_ProductId");

        rule.Should().Be(
            "RESTRICT",
            "products are deactivated rather than deleted in this catalog, but if one ever is, "
            + "losing what a person decided about it would be silent and unrecoverable");
    }

    [Fact]
    public async Task Migration_DeletingAReviewerDoesNotDestroyTheirReviews()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var rule = await schema.ForeignKeyDeleteRuleAsync(
            "FK_FamilyReviewVerdicts_Users_ReviewedByUserId");

        rule.Should().Be(
            "RESTRICT",
            "these rows are the evidence behind the human-review figures the delivery checklist "
            + "asks for, and deleting a user must not quietly reduce them");
    }

    [Fact]
    public async Task Migration_OutcomeIsStoredAsAnInteger()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var type = await schema.ColumnTypeAsync(Table, "Outcome");

        type.Should().Be(
            "integer",
            "a native PostgreSQL enum type survives its table being dropped, so a rollback leaves "
            + "an orphan that makes a later migration fail with \"type already exists\" — weeks "
            + "later, and with no obvious connection to this change");
    }

    [Fact]
    public async Task Migration_MarginAtReviewIsNullable()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var isNullable = await schema.ColumnIsNullableAsync(Table, "MarginAtReview");

        isNullable.Should().BeTrue(
            "a judgement made outside the audit has no margin, and that is a legitimate state "
            + "rather than a missing value; a non-null column would force a fabricated zero that "
            + "reads as \"the evidence was exactly balanced\"");
    }

    [Fact]
    public async Task Migration_NoteLengthMatchesTheValidatedBound()
    {
        await using var schema = await SchemaAssert.OpenAsync(_fixture.ConnectionString);

        var length = await schema.ColumnMaxLengthAsync(Table, "Note");

        length.Should().Be(
            500,
            "the request validators enforce the same number from the entity constant, and a bound "
            + "enforced in one place and guessed in the other is how a request passes validation "
            + "and then fails at the database");
    }
}
