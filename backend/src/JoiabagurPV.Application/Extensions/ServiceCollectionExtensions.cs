using FluentValidation;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;
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

        // Register background services
        services.AddHostedService<ModelTrainingBackgroundService>();

        return services;
    }
}