using FluentAssertions;
using JoiabagurPV.Tests.TestHelpers;
using Microsoft.Extensions.Configuration;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// Guards the environment-dependent log rendering, and specifically the merge trap behind it.
/// </summary>
/// <remarks>
/// Serilog's configuration provider merges a `WriteTo` array BY INDEX. Had the sink stayed an
/// array, the production file would have added its formatter next to the base file's `theme`
/// and `outputTemplate` instead of replacing them, and production would have kept rendering
/// text while looking correctly configured. The keyed form is what makes the override total,
/// and this test is what stops someone from turning it back into an array.
/// </remarks>
public class SerilogEnvironmentProfileTests
{
    private static IConfigurationRoot BuildConfiguration(string? environment)
    {
        var apiDirectory = RepositoryRoot.Resolve("backend", "src", "JoiabagurPV.API");

        var builder = new ConfigurationBuilder()
            .SetBasePath(apiDirectory)
            .AddJsonFile("appsettings.json", optional: false);

        if (environment is not null)
        {
            builder.AddJsonFile($"appsettings.{environment}.json", optional: false);
        }

        return builder.Build();
    }

    [Fact]
    public void DevelopmentProfile_RendersHumanReadableConsole()
    {
        var console = BuildConfiguration("Development").GetSection("Serilog:WriteTo:console");

        console["Name"].Should().Be("Console");
        console["Args:outputTemplate"].Should().NotBeNullOrWhiteSpace();
        console["Args:formatter"].Should().BeNull();
    }

    /// <summary>
    /// Any environment without its own file must still get a sink. With no
    /// `launchSettings.json` in this repository, an unset `ASPNETCORE_ENVIRONMENT` resolves to
    /// Production, so a base file that declared no sink at all would be a silent outage.
    /// </summary>
    [Fact]
    public void BaseProfile_DeclaresTheSinkWithoutArguments()
    {
        var console = BuildConfiguration(environment: null).GetSection("Serilog:WriteTo:console");

        console["Name"].Should().Be("Console");
        console.GetSection("Args").GetChildren().Should().BeEmpty(
            "arguments declared here would survive every environment override and collide with it");
    }

    [Fact]
    public void ProductionProfile_ReplacesConsoleSinkWithJsonFormatter()
    {
        var console = BuildConfiguration("Production").GetSection("Serilog:WriteTo:console");

        console["Args:formatter"].Should().Contain("CompactJsonFormatter");
    }

    /// <summary>
    /// The heart of it: after the override there must be exactly one sink, and it must not have
    /// inherited the text rendering from the base file.
    /// </summary>
    [Fact]
    public void ProductionProfile_LeavesNoTextRenderingBehind()
    {
        var writeTo = BuildConfiguration("Production").GetSection("Serilog:WriteTo");

        writeTo.GetChildren().Should().ContainSingle()
            .Which.Key.Should().Be("console", "an array-shaped override would leave two sinks");

        var console = writeTo.GetSection("console");
        console["Args:outputTemplate"].Should().BeNull(
            "the production override must replace the console entry, not merge into it");
        console["Args:theme"].Should().BeNull();
    }
}
