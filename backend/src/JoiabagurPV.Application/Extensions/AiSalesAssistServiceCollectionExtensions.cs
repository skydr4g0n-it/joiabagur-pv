using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Application.Extensions;

/// <summary>
/// Registers the sale card routes (C34): options with start-up validation and the two services.
/// </summary>
/// <remarks>
/// A registration of its own, like assisted search, and not a line in <c>AddApplication()</c>:
/// the options need the configuration, and that method's signature is one the integration tests
/// depend on.
/// </remarks>
public static class AiSalesAssistServiceCollectionExtensions
{
    /// <summary>
    /// Adds sale assistance and substitutes, and validates their configuration at start-up.
    /// </summary>
    public static IServiceCollection AddSalesAssist(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configuration);

        const string section = AiSalesAssistOptions.SectionName;

        services
            .AddOptions<AiSalesAssistOptions>()
            .Bind(configuration.GetSection(section))
            .Validate(
                options => options.StockCriticalThreshold >= 1,
                $"{section}:StockCriticalThreshold must be at least 1. Zero units is a state of the member, never a critical-stock warning.")
            .Validate(
                options => options.SubstitutesCandidateWindow >= 1
                           && options.SubstitutesCandidateWindow <= AiSubstitutesRequest.MaxTopK,
                $"{section}:SubstitutesCandidateWindow must be between 1 and {AiSubstitutesRequest.MaxTopK}, which is the largest top_k the frozen jbg-ai contract accepts.")
            .Validate(
                options => options.SubstitutesMaxPageSize >= 1 && options.SubstitutesMaxPageSize <= 50,
                $"{section}:SubstitutesMaxPageSize must be between 1 and 50, the pagination ceiling of the project.")
            .Validate(
                options => options.SubstitutesDefaultPageSize >= 1
                           && options.SubstitutesDefaultPageSize <= options.SubstitutesMaxPageSize,
                $"{section}:SubstitutesDefaultPageSize must be at least 1 and no larger than SubstitutesMaxPageSize.")
            .Validate(
                options => options.RateLimitPermitLimit > 0 && options.RateLimitWindowSeconds > 0,
                $"{section}:RateLimitPermitLimit and {section}:RateLimitWindowSeconds must be positive.")
            .ValidateOnStart();

        services.AddScoped<ISalesAssistService, SalesAssistService>();
        services.AddScoped<ISubstitutesService, SubstitutesService>();

        return services;
    }
}
