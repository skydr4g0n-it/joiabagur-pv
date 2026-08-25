using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.ApplicationParts;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;
using Respawn;
using Testcontainers.PostgreSql;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Custom WebApplicationFactory for integration testing.
/// Uses Testcontainers for PostgreSQL database and Respawn for database cleanup.
/// </summary>
public class ApiWebApplicationFactory : WebApplicationFactory<Program>, IAsyncLifetime
{
    private readonly PostgreSqlContainer _postgresContainer;
    private Respawner? _respawner;
    private string? _connectionString;

    public ApiWebApplicationFactory()
    {
        _postgresContainer = new PostgreSqlBuilder()
            .WithImage("postgres:15")
            .WithDatabase("testdb")
            .WithUsername("testuser")
            .WithPassword("testpassword")
            .WithCleanUp(true)
            .Build();
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        // Set configuration values BEFORE services are configured
        builder.UseSetting("Jwt:SecretKey", "TestSecretKeyForIntegrationTestingThatIsLongEnough12345!");
        builder.UseSetting("Jwt:Issuer", "TestIssuer");
        builder.UseSetting("Jwt:Audience", "TestAudience");
        builder.UseSetting("Jwt:AccessTokenExpirationMinutes", "60");
        builder.UseSetting("Jwt:RefreshTokenExpirationHours", "8");
        builder.UseSetting("Testing:SkipSwagger", "true");
        builder.UseSetting("IndexFeed:ApiKey", IndexFeedTestKeys.ApiKey);
        
        // Set the connection string for the test database
        builder.UseSetting("ConnectionStrings:DefaultConnection", _postgresContainer.GetConnectionString());

        builder.ConfigureServices(services =>
        {
            // Remove the existing DbContext registration to ensure we use the test connection string
            var descriptor = services.SingleOrDefault(
                d => d.ServiceType == typeof(DbContextOptions<ApplicationDbContext>));
            if (descriptor != null)
            {
                services.Remove(descriptor);
            }

            // Add DbContext using test container connection string
            services.AddDbContext<ApplicationDbContext>(options =>
            {
                options.UseNpgsql(_postgresContainer.GetConnectionString());
            });

            // Remove Swashbuckle assemblies from application parts to avoid .NET 10 compatibility issues
            var partManager = services.BuildServiceProvider().GetService<ApplicationPartManager>();
            if (partManager != null)
            {
                var partsToRemove = partManager.ApplicationParts
                    .Where(p => p.Name.Contains("Swashbuckle", StringComparison.OrdinalIgnoreCase))
                    .ToList();
                
                foreach (var part in partsToRemove)
                {
                    partManager.ApplicationParts.Remove(part);
                }
            }
        });

        builder.UseEnvironment("Testing");
    }

    public async Task InitializeAsync()
    {
        await _postgresContainer.StartAsync();
        _connectionString = _postgresContainer.GetConnectionString();
        
        // Initialize Respawn after the container is started
        // Note: Respawner will be created after first database access to ensure schema exists
    }

    async Task IAsyncLifetime.DisposeAsync()
    {
        await _postgresContainer.StopAsync();
    }

    /// <summary>
    /// Creates a scope and returns the ApplicationDbContext.
    /// </summary>
    public ApplicationDbContext CreateDbContext()
    {
        var scope = Services.CreateScope();
        return scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
    }

    /// <summary>
    /// Resets the database using Respawn for reliable cleanup.
    /// Automatically handles schema changes without manual SQL updates.
    /// </summary>
    public async Task ResetDatabaseAsync()
    {
        if (_connectionString == null)
        {
            throw new InvalidOperationException("Database not initialized. Call InitializeAsync first.");
        }

        // Initialize Respawner on first use (after schema is created)
        if (_respawner == null)
        {
            await using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync();
            
            _respawner = await Respawner.CreateAsync(connection, new RespawnerOptions
            {
                DbAdapter = DbAdapter.Postgres,
                SchemasToInclude = ["public"],
                // Exclude EF Core migrations table
                TablesToIgnore = ["__EFMigrationsHistory"]
            });
        }

        // Reset database using Respawn
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();
        await _respawner.ResetAsync(conn);

        // Re-seed the database with initial data
        using var scope = Services.CreateScope();
        var seeder = scope.ServiceProvider.GetRequiredService<DatabaseSeeder>();
        await seeder.SeedAsync();
    }
}
