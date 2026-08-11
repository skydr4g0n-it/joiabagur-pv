using FluentAssertions;
using JoiabagurPV.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Metadata;
using Microsoft.EntityFrameworkCore.Migrations;
using Microsoft.EntityFrameworkCore.Migrations.Internal;
using Xunit;

// Namespace deliberately not "...UnitTests.Infrastructure": inside it, the using directive for
// Microsoft.EntityFrameworkCore.Infrastructure fails to resolve, because using directives are
// matched against enclosing namespaces first.
namespace JoiabagurPV.Tests.UnitTests.Persistence;

/// <summary>
/// Guards the gap between what the model says and what the migrations built.
/// </summary>
/// <remarks>
/// This is the cheapest high-value assertion in the whole migration story, and it protects
/// every future migration rather than only the current one: changing an entity configuration
/// and forgetting to generate a migration leaves the code and the database silently out of
/// step, and whether the existing suite notices depends on whether some test happens to touch
/// that entity.
///
/// It needs no database. Two models are compared in memory, so it runs in milliseconds on
/// every build instead of waiting for a container.
/// </remarks>
public class MigrationModelDriftTests
{
    [Fact]
    public void Model_HasNoPendingMigrationDifferences()
    {
        // The connection is never opened: building the model requires a provider, not a server.
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseNpgsql("Host=localhost;Database=model-only;Username=none;Password=none")
            .Options;

        using var context = new ApplicationDbContext(options);

        var snapshot = context.GetService<IMigrationsAssembly>().ModelSnapshot;
        snapshot.Should().NotBeNull("the migrations assembly must carry a model snapshot");

        var snapshotModel = context.GetService<IModelRuntimeInitializer>()
            .Initialize(((IMutableModel)snapshot!.Model).FinalizeModel());

        var differences = context.GetService<IMigrationsModelDiffer>().GetDifferences(
            snapshotModel.GetRelationalModel(),
            context.GetService<IDesignTimeModel>().Model.GetRelationalModel());

        differences.Should().BeEmpty(
            "an entity configuration changed without a migration being generated — run "
            + "'dotnet ef migrations add <name> --project ../JoiabagurPV.Infrastructure' from the API project");
    }
}
