using Amazon.S3;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Interfaces.Repositories;
using JoiabagurPV.Domain.Interfaces.Services;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Infrastructure.Data.Repositories;
using JoiabagurPV.Infrastructure.Services;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;

namespace JoiabagurPV.Infrastructure.Extensions;

/// <summary>
/// Extension methods for configuring infrastructure services.
/// </summary>
public static class ServiceCollectionExtensions
{
    /// <summary>
    /// Adds infrastructure services to the dependency injection container.
    /// </summary>
    /// <param name="services">The service collection.</param>
    /// <param name="configuration">The application configuration.</param>
    /// <returns>The service collection with infrastructure services added.</returns>
    public static IServiceCollection AddInfrastructure(this IServiceCollection services, IConfiguration configuration)
    {
        // Database context
        services.AddDbContext<ApplicationDbContext>(options =>
        {
            options.UseNpgsql(configuration.GetConnectionString("DefaultConnection"),
                npgsqlOptions =>
                {
                    // Configure connection pooling for free-tier optimization
                    npgsqlOptions.CommandTimeout(30); // 30 second timeout
                });

            // Configure connection string with pooling parameters
            var connectionString = configuration.GetConnectionString("DefaultConnection");
            var builder = new NpgsqlConnectionStringBuilder(connectionString)
            {
                MaxPoolSize = 10,  // Max 10 connections for free-tier
                MinPoolSize = 1,   // Min 1 connection
                ConnectionIdleLifetime = 60, // 1 minute
                ConnectionPruningInterval = 10 // Check every 10 seconds
            };

            options.UseNpgsql(builder.ConnectionString);

            // Enable sensitive data logging in development
            if (Environment.GetEnvironmentVariable("ASPNETCORE_ENVIRONMENT") == "Development")
            {
                options.EnableSensitiveDataLogging();
                options.EnableDetailedErrors();
            }
        });

        // Register repositories
        services.AddScoped(typeof(IRepository<>), typeof(Repository<>));
        services.AddScoped<IUserRepository, UserRepository>();
        services.AddScoped<IUserPointOfSaleRepository, UserPointOfSaleRepository>();
        services.AddScoped<IRefreshTokenRepository, RefreshTokenRepository>();
        services.AddScoped<IPointOfSaleRepository, PointOfSaleRepository>();
        services.AddScoped<IPaymentMethodRepository, PaymentMethodRepository>();
        services.AddScoped<IPointOfSalePaymentMethodRepository, PointOfSalePaymentMethodRepository>();
        services.AddScoped<IProductRepository, ProductRepository>();
        services.AddScoped<IProductPhotoRepository, ProductPhotoRepository>();
        services.AddScoped<ICollectionRepository, CollectionRepository>();
        services.AddScoped<IInventoryRepository, InventoryRepository>();
        services.AddScoped<IInventoryMovementRepository, InventoryMovementRepository>();
        services.AddScoped<ISaleRepository, SaleRepository>();
        services.AddScoped<ISalePhotoRepository, SalePhotoRepository>();
        services.AddScoped<IReturnRepository, ReturnRepository>();
        services.AddScoped<IReturnSaleRepository, ReturnSaleRepository>();
        services.AddScoped<IReturnPhotoRepository, ReturnPhotoRepository>();
        services.AddScoped<IModelMetadataRepository, ModelMetadataRepository>();
        services.AddScoped<IModelTrainingJobRepository, ModelTrainingJobRepository>();

        services.AddScoped<IProductPhotoEmbeddingRepository, ProductPhotoEmbeddingRepository>();

        // Register component management repositories (EP10)
        services.AddScoped<IProductComponentRepository, ProductComponentRepository>();
        services.AddScoped<IProductComponentAssignmentRepository, ProductComponentAssignmentRepository>();
        services.AddScoped<IComponentTemplateRepository, ComponentTemplateRepository>();

        // Register product family repositories (EP13)
        services.AddScoped<IProductFamilyRepository, ProductFamilyRepository>();

        // Indexing feed keyset queries (C12). No new tables.
        services.AddScoped<IIndexFeedRepository, IndexFeedRepository>();

        // Assisted search reads (C15): set-based hydration and the degraded Spanish full-text
        // searcher. No new tables and no index: at this catalog size an inverted index would buy
        // stemming rather than speed, and the stemming is obtained without it.
        services.AddScoped<IAssistedSearchRepository, AssistedSearchRepository>();

        // Register unit of work
        services.AddScoped<IUnitOfWork, UnitOfWork>();

        // Register database seeder
        services.AddScoped<DatabaseSeeder>();

        // Register file storage service based on configuration
        var storageProvider = configuration["FileStorage:Provider"]?.ToLowerInvariant() ?? "local";
        if (storageProvider == "s3")
        {
            // Register AWS S3 client for dependency injection
            services.AddAWSService<IAmazonS3>();
            services.AddScoped<IFileStorageService, S3FileStorageService>();
        }
        else
        {
            services.AddScoped<IFileStorageService, LocalFileStorageService>();
        }

        return services;
    }
}