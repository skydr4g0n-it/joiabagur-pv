using FluentAssertions;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.Extensions;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// A missing or short index-feed key must stop the host, not look like a 401 on the first pull.
/// </summary>
public class IndexFeedRegistrationTests
{
    private const string ValidKey = "local-dev-index-feed-key-0123456789ab";

    private static ServiceProvider BuildProvider(Dictionary<string, string?> settings)
    {
        var configuration = new ConfigurationBuilder().AddInMemoryCollection(settings).Build();
        var services = new ServiceCollection();
        services.AddIndexFeed(configuration);
        return services.BuildServiceProvider();
    }

    private static Action ValidateStartup(ServiceProvider provider) =>
        () => provider.GetRequiredService<IStartupValidator>().Validate();

    [Fact]
    public void AddIndexFeed_WhenApiKeyMissing_FailsOnStart()
    {
        using var provider = BuildProvider([]);

        ValidateStartup(provider).Should().Throw<OptionsValidationException>()
            .WithMessage("*ApiKey*", "the error must name the key that is missing");
    }

    [Fact]
    public void AddIndexFeed_WhenApiKeyTooShort_FailsOnStart()
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["IndexFeed:ApiKey"] = "short"
        });

        ValidateStartup(provider).Should().Throw<OptionsValidationException>()
            .WithMessage("*ApiKey*");
    }

    [Fact]
    public void AddIndexFeed_WithValidPlaceholder_Starts()
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["IndexFeed:ApiKey"] = ValidKey
        });

        ValidateStartup(provider).Should().NotThrow();
        provider.GetRequiredService<IOptions<IndexFeedOptions>>().Value.ApiKey.Should().Be(ValidKey);
        ValidKey.Length.Should().BeGreaterThanOrEqualTo(IndexFeedOptions.MinimumSecretLength);
    }

    [Fact]
    public void AddIndexFeed_WhenPreviousIsEmpty_TreatsItAsUnset()
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["IndexFeed:ApiKey"] = ValidKey,
            ["IndexFeed:ApiKeyPrevious"] = ""
        });

        ValidateStartup(provider).Should().NotThrow();
        provider.GetRequiredService<IOptions<IndexFeedOptions>>().Value.ApiKeyPrevious
            .Should().BeEmpty();
    }

    [Fact]
    public void AddIndexFeed_WhenPreviousIsTooShort_FailsOnStart()
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["IndexFeed:ApiKey"] = ValidKey,
            ["IndexFeed:ApiKeyPrevious"] = "short"
        });

        ValidateStartup(provider).Should().Throw<OptionsValidationException>()
            .WithMessage("*ApiKeyPrevious*");
    }

    [Fact]
    public void AddIndexFeed_WithNoSalesAsOf_LeavesTheWallClockInCharge()
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["IndexFeed:ApiKey"] = ValidKey
        });

        ValidateStartup(provider).Should().NotThrow();
        provider.GetRequiredService<IOptions<IndexFeedOptions>>().Value.SalesAsOfUtc
            .Should().BeNull("an absent option must not change how anything behaves");
    }

    /// <summary>
    /// Binding an ISO-8601 string with a trailing <c>Z</c> yields the instant that was meant.
    /// </summary>
    /// <remarks>
    /// Pinned by test rather than trusted: the configuration binder converts through
    /// <see cref="DateTime"/>'s type converter, which parses the offset and then returns a
    /// <see cref="DateTimeKind.Local"/> value. Reading the raw property on a host outside UTC
    /// would silently shift every sales window, which is why the option is only ever read
    /// through its normalised form.
    /// </remarks>
    [Fact]
    public void AddIndexFeed_WithUtcSalesAsOf_BindsTheInstantThatWasMeant()
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["IndexFeed:ApiKey"] = ValidKey,
            ["IndexFeed:SalesAsOf"] = "2026-08-23T23:59:59Z"
        });

        ValidateStartup(provider).Should().NotThrow();

        var options = provider.GetRequiredService<IOptions<IndexFeedOptions>>().Value;
        options.SalesAsOfUtc.Should().Be(new DateTime(2026, 8, 23, 23, 59, 59, DateTimeKind.Utc));
        options.SalesAsOfUtc!.Value.Kind.Should().Be(DateTimeKind.Utc);
    }

    [Fact]
    public void AddIndexFeed_WhenSalesAsOfCarriesNoOffset_FailsOnStart()
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["IndexFeed:ApiKey"] = ValidKey,
            ["IndexFeed:SalesAsOf"] = "2026-08-23T23:59:59"
        });

        ValidateStartup(provider).Should().Throw<OptionsValidationException>()
            .WithMessage(
                "*SalesAsOf*",
                "an ambiguous clock must stop the host, not move the windows by a timezone");
    }

    [Fact]
    public void AddIndexFeed_WithConfiguredSalesAsOf_IsIdempotentAcrossReads()
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["IndexFeed:ApiKey"] = ValidKey,
            ["IndexFeed:SalesAsOf"] = "2026-08-23T23:59:59Z"
        });

        var options = provider.GetRequiredService<IOptions<IndexFeedOptions>>().Value;

        options.SalesAsOfUtc.Should().Be(
            options.SalesAsOfUtc,
            "normalising twice must not drift the instant");
    }
}
