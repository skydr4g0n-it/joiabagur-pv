using FluentAssertions;
using JoiabagurPV.Application.Extensions;
using JoiabagurPV.Application.Interfaces;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// Start-up validation exists to remove the most banal cause of an unexplainable 401: a
/// configuration key that was never set. Lazy validation would surface it inside a request
/// instead, which is the failure mode being designed out.
/// </summary>
public class AiGatewayRegistrationTests
{
    private const string ValidSecret = "test-jwt-secret-0123456789abcdefghij";

    private static ServiceProvider BuildProvider(Dictionary<string, string?> settings)
    {
        var configuration = new ConfigurationBuilder().AddInMemoryCollection(settings).Build();

        var services = new ServiceCollection();
        services.AddLogging();
        services.AddSingleton<ITraceContextAccessor>(new FixedTraceContextAccessor());
        services.AddAiGateway(configuration);

        return services.BuildServiceProvider();
    }

    /// <summary>Runs the same validation the host runs on start-up.</summary>
    private static Action ValidateStartup(ServiceProvider provider) =>
        () => provider.GetRequiredService<IStartupValidator>().Validate();

    [Fact]
    public void AddAiGateway_WhenSecretMissing_FailsOnStart()
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["AiGateway:BaseUrl"] = "http://localhost:8001"
        });

        ValidateStartup(provider).Should().Throw<OptionsValidationException>()
            .WithMessage("*JwtSecret*", "the error must name the key that is missing");
    }

    [Fact]
    public void AddAiGateway_WhenSecretTooShortForHs256_FailsOnStart()
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["AiGateway:BaseUrl"] = "http://localhost:8001",
            ["AiGateway:JwtSecret"] = "short"
        });

        ValidateStartup(provider).Should().Throw<OptionsValidationException>()
            .WithMessage("*JwtSecret*");
    }

    [Fact]
    public void AddAiGateway_WhenBaseUrlIsNotAbsolute_FailsOnStart()
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["AiGateway:BaseUrl"] = "localhost:8001",
            ["AiGateway:JwtSecret"] = ValidSecret
        });

        ValidateStartup(provider).Should().Throw<OptionsValidationException>()
            .WithMessage("*BaseUrl*", "the error must name the offending key");
    }

    [Fact]
    public void AddAiGateway_WithValidConfiguration_ResolvesTheClient()
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["AiGateway:BaseUrl"] = "http://localhost:8001",
            ["AiGateway:JwtSecret"] = ValidSecret
        });

        ValidateStartup(provider).Should().NotThrow();
        provider.GetRequiredService<IAiGatewayClient>().Should().NotBeNull();
        provider.GetRequiredService<IAiServiceTokenFactory>().Should().NotBeNull();
    }

    /// <summary>
    /// A disabled integration must not be able to stop the API from starting, even if its
    /// remaining settings are absent.
    /// </summary>
    [Fact]
    public void AddAiGateway_WhenDisabled_RegistersNothingAndDoesNotValidate()
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["AiGateway:Enabled"] = "false"
        });

        // Nothing was registered, so there is no start-up validation to run and nothing to resolve.
        provider.GetService<IStartupValidator>().Should().BeNull();
        provider.GetService<IAiGatewayClient>().Should().BeNull();
    }

    private sealed class FixedTraceContextAccessor : ITraceContextAccessor
    {
        public string CurrentTraceId => "trace-registration-test";
    }
}
