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
}
