using FluentValidation;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Application.Extensions;

/// <summary>
/// Extension methods for configuring application services.
/// </summary>
public static class ServiceCollectionExtensions
{
    /// <summary>
    /// Adds application services to the dependency injection container.
    /// </summary>
    /// <param name="services">The service collection.</param>
    /// <returns>The service collection with application services added.</returns>
    public static IServiceCollection AddApplication(this IServiceCollection services)
    {
        // Register validators from the assembly
        services.AddValidatorsFromAssembly(typeof(ServiceCollectionExtensions).Assembly);

        // Register authentication services
        services.AddScoped<IJwtTokenService, JwtTokenService>();
        services.AddScoped<IAuthenticationService, AuthenticationService>();

        // Register user management services
        services.AddScoped<IUserService, UserService>();
        services.AddScoped<IUserPointOfSaleService, UserPointOfSaleService>();

        // Register point of sale management services
        services.AddScoped<IPointOfSaleService, PointOfSaleService>();

        // Register payment method management services
        services.AddScoped<IPaymentMethodService, PaymentMethodService>();

        // Register shared services
        services.AddSingleton<IExcelTemplateService, ExcelTemplateService>();

        // Register product management services
        services.AddScoped<IProductService, ProductService>();
        services.AddScoped<IExcelImportService, ExcelImportService>();
        services.AddScoped<IProductPhotoService, ProductPhotoService>();

        // Register inventory management services
        services.AddScoped<IInventoryService, InventoryService>();
        services.AddScoped<IStockImportService, StockImportService>();
        services.AddScoped<IInventoryMovementService, InventoryMovementService>();
        services.AddScoped<IStockValidationService, StockValidationService>();

        // Register sales management services
        services.AddScoped<ISalesService, SalesService>();
        services.AddScoped<IPaymentMethodValidationService, PaymentMethodValidationService>();
        services.AddScoped<IImageCompressionService, ImageCompressionService>();

        // Register returns management services
        services.AddScoped<IReturnService, ReturnService>();

        // Register dashboard services
        services.AddMemoryCache();
        services.AddScoped<IDashboardService, DashboardService>();

        // Register component management services (EP10)
        services.AddScoped<IProductComponentService, ProductComponentService>();
        services.AddScoped<IComponentAssignmentService, ComponentAssignmentService>();
        services.AddScoped<IComponentTemplateService, ComponentTemplateService>();
        services.AddScoped<IComponentReportService, ComponentReportService>();

        // Register report services
        services.AddScoped<IInventoryMovementReportService, InventoryMovementReportService>();

        // Register image recognition services
        services.AddScoped<IImageRecognitionService, ImageRecognitionService>();
        services.AddScoped<IModelHealthService, ModelHealthService>();

        // Register QR code services
        services.AddScoped<IQrCodeService, QrCodeService>();

        // Register assisted-search telemetry
        services.AddScoped<IProductSearchEventService, ProductSearchEventService>();

        // Register catalog AI profiles. The policy is a singleton: it holds no state beyond its
        // configured thresholds, and making it scoped would rebuild it once per request for no
        // reason.
        services.AddSingleton<IProfileReviewPolicy, ProfileReviewPolicy>();
        services.AddScoped<IProductAiProfileService, ProductAiProfileService>();

        // Register product families (EP13)
        services.AddScoped<IProductFamilyService, ProductFamilyService>();
        services.AddScoped<IFamilySuggestionService, FamilySuggestionService>();
        services.AddScoped<IFamilyAuditService, FamilyAuditService>();

        // Indexing feeds (catalog + POS). Options are bound separately in AddIndexFeed so
        // start-up validation runs even if this registration is reused from a test host.
        services.AddScoped<IIndexFeedService, IndexFeedService>();

        // Register background services
        services.AddHostedService<ModelTrainingBackgroundService>();

        return services;
    }

    /// <summary>
    /// Binds and validates the thresholds of the hybrid profile review policy.
    /// </summary>
    /// <remarks>
    /// Validated at start-up rather than lazily, for the same reason the gateway options are: a
    /// threshold outside the range zero to one would otherwise surface inside a request, having
    /// already routed a batch of profiles by a rule that cannot be satisfied.
    /// </remarks>
    public static IServiceCollection AddProfileReview(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configuration);

        services
            .AddOptions<ProfileReviewOptions>()
            .Bind(configuration.GetSection(ProfileReviewOptions.SectionName))
            .Validate(
                o => o.TagAutoApproveThreshold is >= 0 and <= 1,
                $"{ProfileReviewOptions.SectionName}:TagAutoApproveThreshold must be between 0 and 1.")
            .Validate(
                o => o.MinimumFieldConfidence is >= 0 and <= 1,
                $"{ProfileReviewOptions.SectionName}:MinimumFieldConfidence must be between 0 and 1.")
            .ValidateOnStart();

        return services;
    }

    /// <summary>
    /// Binds and validates the index-feed API key at start-up. A missing or short key must
    /// stop the host, not surface as a 401 on the first pull.
    /// </summary>
    public static IServiceCollection AddIndexFeed(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configuration);

        services
            .AddOptions<IndexFeedOptions>()
            .Bind(configuration.GetSection(IndexFeedOptions.SectionName))
            .Validate(
                o => !string.IsNullOrWhiteSpace(o.ApiKey),
                $"{IndexFeedOptions.SectionName}:ApiKey is not configured. It must be a dedicated service secret, distinct from Jwt:SecretKey and AiGateway:JwtSecret.")
            .Validate(
                o => o.ApiKey.Length >= IndexFeedOptions.MinimumSecretLength,
                $"{IndexFeedOptions.SectionName}:ApiKey is too short; at least {IndexFeedOptions.MinimumSecretLength} characters are required.")
            .Validate(
                o => string.IsNullOrWhiteSpace(o.ApiKeyPrevious)
                     || o.ApiKeyPrevious.Length >= IndexFeedOptions.MinimumSecretLength,
                $"{IndexFeedOptions.SectionName}:ApiKeyPrevious is set but shorter than {IndexFeedOptions.MinimumSecretLength} characters.")
            .Validate(
                o => o.SalesAsOf is not { Kind: DateTimeKind.Unspecified },
                $"{IndexFeedOptions.SectionName}:SalesAsOf must carry a UTC offset, for example 2026-08-23T23:59:59Z. Without one it binds as an unspecified kind and would be read as the host's local time, which is the ambiguity this setting exists to remove.")
            .Validate(
                o => o.SalesAsOf != default(DateTime),
                $"{IndexFeedOptions.SectionName}:SalesAsOf is set to an empty or unparseable instant. Leave it out entirely to count the sales windows against the wall clock.")
            .ValidateOnStart();

        if (services.All(d => d.ServiceType != typeof(TimeProvider)))
        {
            services.AddSingleton(TimeProvider.System);
        }

        return services;
    }
}