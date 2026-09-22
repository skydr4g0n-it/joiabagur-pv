using System.Text.Json;
using FluentAssertions;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Extensions;
using JoiabagurPV.Application.Validators;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;
using Moq;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// The configuration of the sale card: documented defaults, start-up validation, request
/// validation, and the wire shape of the two enumerations the card of C36 reads.
/// </summary>
public class SalesAssistConfigurationTests
{
    // ---------------------------------------------------------------- defaults (5.1)

    [Fact]
    public void Options_AreSwitchedOffByDefault()
    {
        var options = new AiSalesAssistOptions();

        options.EnabledByDefault.Should().BeFalse("enabling a shop is an explicit act, as for search");
        options.EnabledPointOfSaleIds.Should().BeEmpty();
        options.IsEnabledFor(Guid.NewGuid()).Should().BeFalse();
    }

    [Fact]
    public void Options_CriticalStockThreshold_DefaultsToTwo() =>
        new AiSalesAssistOptions().StockCriticalThreshold.Should().Be(2);

    [Fact]
    public void Options_SubstitutesWindow_DefaultsToTwenty() =>
        new AiSalesAssistOptions().SubstitutesCandidateWindow.Should().Be(20);

    [Fact]
    public void Options_SubstitutesPages_DefaultToFiveAndTwenty()
    {
        var options = new AiSalesAssistOptions();

        options.SubstitutesDefaultPageSize.Should().Be(5);
        options.SubstitutesMaxPageSize.Should().Be(20);
    }

    [Fact]
    public void Options_RateLimit_DefaultsToTenPerMinute()
    {
        var options = new AiSalesAssistOptions();

        options.RateLimitPermitLimit.Should().Be(10);
        options.RateLimitWindowSeconds.Should().Be(60);
    }

    [Fact]
    public void Options_IsEnabledFor_ListOrDefault()
    {
        var listed = Guid.NewGuid();
        var options = new AiSalesAssistOptions { EnabledPointOfSaleIds = [listed] };

        options.IsEnabledFor(listed).Should().BeTrue();
        options.IsEnabledFor(Guid.NewGuid()).Should().BeFalse();

        options.EnabledByDefault = true;
        options.IsEnabledFor(Guid.NewGuid()).Should().BeTrue();
    }

    [Fact]
    public void AddSalesAssist_WithNoConfiguration_StartsWithTheDocumentedDefaults()
    {
        using var provider = BuildProvider([]);

        ValidateStartup(provider).Should().NotThrow();
        provider.GetRequiredService<IOptionsMonitor<AiSalesAssistOptions>>().CurrentValue
            .StockCriticalThreshold.Should().Be(2);
    }

    [Fact]
    public void AddSalesAssist_ReadsTheSwitchFromConfiguration()
    {
        var pos = Guid.NewGuid();
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            ["AiSalesAssist:EnabledPointOfSaleIds:0"] = pos.ToString()
        });

        provider.GetRequiredService<IOptionsMonitor<AiSalesAssistOptions>>().CurrentValue
            .IsEnabledFor(pos).Should().BeTrue();
    }

    // ---------------------------------------------------------------- start-up validation (5.2)

    [Theory]
    [InlineData("StockCriticalThreshold", "0")]
    [InlineData("SubstitutesCandidateWindow", "0")]
    [InlineData("SubstitutesCandidateWindow", "51")]
    [InlineData("SubstitutesMaxPageSize", "0")]
    [InlineData("SubstitutesMaxPageSize", "51")]
    [InlineData("SubstitutesDefaultPageSize", "0")]
    [InlineData("SubstitutesDefaultPageSize", "21")]
    [InlineData("RateLimitPermitLimit", "0")]
    [InlineData("RateLimitWindowSeconds", "0")]
    public void AddSalesAssist_WithAValueOutOfRange_FailsAtStartup_NamingTheKey(string key, string value)
    {
        using var provider = BuildProvider(new Dictionary<string, string?>
        {
            [$"AiSalesAssist:{key}"] = value
        });

        ValidateStartup(provider).Should().Throw<OptionsValidationException>()
            .WithMessage($"*AiSalesAssist:{key}*", "the error must name the offending key");
    }

    // ---------------------------------------------------------------- request validation (8.2)

    [Fact]
    public void SalesAssistValidator_WithoutPointOfSale_IsInvalid()
    {
        var result = new SalesAssistRequestValidator().Validate(new SalesAssistRequest());

        result.IsValid.Should().BeFalse();
        result.Errors.Should().ContainSingle(e => e.ErrorMessage.Contains("punto de venta"));
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public void SalesAssistValidator_BlankQuestion_IsInvalid(string question)
    {
        new SalesAssistRequestValidator()
            .Validate(new SalesAssistRequest { PointOfSaleId = Guid.NewGuid(), Question = question })
            .IsValid.Should().BeFalse("a present question may not be blank");
    }

    [Fact]
    public void SalesAssistValidator_QuestionLongerThanTheContract_IsInvalid()
    {
        new SalesAssistRequestValidator()
            .Validate(new SalesAssistRequest { PointOfSaleId = Guid.NewGuid(), Question = new string('a', 501) })
            .IsValid.Should().BeFalse();
    }

    [Theory]
    [InlineData(null)]
    [InlineData("¿Se puede mojar?")]
    public void SalesAssistValidator_NoQuestionOrAReasonableOne_IsValid(string? question)
    {
        new SalesAssistRequestValidator()
            .Validate(new SalesAssistRequest { PointOfSaleId = Guid.NewGuid(), Question = question })
            .IsValid.Should().BeTrue();
    }

    [Fact]
    public void SalesAssistValidator_QuestionAtTheContractMaximumAfterTrimming_IsValid()
    {
        new SalesAssistRequestValidator()
            .Validate(new SalesAssistRequest { PointOfSaleId = Guid.NewGuid(), Question = "  " + new string('a', 500) + "  " })
            .IsValid.Should().BeTrue("what is measured is what is sent, and it is sent trimmed");
    }

    [Fact]
    public void SubstitutesValidator_WithoutPointOfSale_IsInvalid() =>
        SubstitutesValidator().Validate(new SubstitutesRequest()).IsValid.Should().BeFalse();

    [Theory]
    [InlineData(0, false)]
    [InlineData(1, true)]
    [InlineData(20, true)]
    [InlineData(21, false)]
    public void SubstitutesValidator_PageSize_IsBoundedByConfiguration(int pageSize, bool valid) =>
        SubstitutesValidator()
            .Validate(new SubstitutesRequest { PointOfSaleId = Guid.NewGuid(), PageSize = pageSize })
            .IsValid.Should().Be(valid);

    // ---------------------------------------------------------------- wire shape (8.1)

    /// <summary>
    /// Serialized through the options the API uses for every response: camelCase names, and the
    /// enumerations as their snake_case strings.
    /// </summary>
    [Theory]
    [InlineData(PitchStatus.Generated, "generated")]
    [InlineData(PitchStatus.NotGenerated, "not_generated")]
    [InlineData(PitchStatus.WithheldByAi, "withheld_by_ai")]
    [InlineData(PitchStatus.WithheldOutOfStock, "withheld_out_of_stock")]
    [InlineData(PitchStatus.WithheldUnresolved, "withheld_unresolved")]
    [InlineData(PitchStatus.AiUnavailable, "ai_unavailable")]
    public void PitchStatus_SerializesAsSnakeCase(PitchStatus status, string wire)
    {
        var json = JsonSerializer.Serialize(new SalesAssistResponse { PitchStatus = status }, ApiJson);

        JsonDocument.Parse(json).RootElement.GetProperty("pitchStatus").GetString().Should().Be(wire);
    }

    [Theory]
    [InlineData(SubstitutesOutcome.Ok, "ok")]
    [InlineData(SubstitutesOutcome.NoneInStock, "none_in_stock")]
    [InlineData(SubstitutesOutcome.ProductNotIndexed, "product_not_indexed")]
    [InlineData(SubstitutesOutcome.AiUnavailable, "ai_unavailable")]
    public void SubstitutesOutcome_SerializesAsSnakeCase(SubstitutesOutcome outcome, string wire)
    {
        var json = JsonSerializer.Serialize(new SubstitutesResponse { Outcome = outcome }, ApiJson);

        JsonDocument.Parse(json).RootElement.GetProperty("outcome").GetString().Should().Be(wire);
    }

    /// <summary>What the API configures for responses (camelCase, nothing else).</summary>
    private static readonly JsonSerializerOptions ApiJson = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };

    private static SubstitutesRequestValidator SubstitutesValidator() =>
        new(Mock.Of<IOptionsMonitor<AiSalesAssistOptions>>(m => m.CurrentValue == new AiSalesAssistOptions()));

    private static ServiceProvider BuildProvider(Dictionary<string, string?> settings)
    {
        var configuration = new ConfigurationBuilder().AddInMemoryCollection(settings).Build();

        var services = new ServiceCollection();
        services.AddSalesAssist(configuration);

        return services.BuildServiceProvider();
    }

    private static Action ValidateStartup(ServiceProvider provider) =>
        () => provider.GetRequiredService<IStartupValidator>().Validate();
}
