using JoiabagurPV.API.Services;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.IdentityModel.Tokens;
using System.Text;
using System.Text.Json;
using System.Threading.RateLimiting;

namespace JoiabagurPV.API.Extensions;

/// <summary>
/// Extension methods for configuring API services.
/// </summary>
public static class ServiceCollectionExtensions
{
    /// <summary>
    /// Adds API services to the dependency injection container.
    /// </summary>
    /// <param name="services">The service collection.</param>
    /// <param name="configuration">The application configuration.</param>
    /// <returns>The service collection with API services added.</returns>
    public static IServiceCollection AddApiServices(this IServiceCollection services, IConfiguration configuration)
    {
        // Configure JSON options for camelCase
        services.AddControllers(options =>
        {
            // Add global filters if needed
        })
        .AddJsonOptions(options =>
        {
            options.JsonSerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
            options.JsonSerializerOptions.WriteIndented = false;
        });

        // Configure API behavior
        services.Configure<ApiBehaviorOptions>(options =>
        {
            options.SuppressModelStateInvalidFilter = true; // We'll handle validation manually
        });

        // Add HttpContextAccessor for CurrentUserService
        services.AddHttpContextAccessor();
        services.AddScoped<ICurrentUserService, CurrentUserService>();

        // Correlation identifier for outbound calls (AI gateway). Same layering as
        // CurrentUserService: interface in Application, implementation here.
        services.AddScoped<ITraceContextAccessor, TraceContextAccessor>();

        // Add JWT Authentication
        var jwtSecretKey = configuration["Jwt:SecretKey"] ?? throw new InvalidOperationException("JWT SecretKey not configured");
        var jwtIssuer = configuration["Jwt:Issuer"] ?? "JoiabagurPV";
        var jwtAudience = configuration["Jwt:Audience"] ?? "JoiabagurPV";

        services.AddAuthentication(options =>
        {
            options.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
            options.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
        })
        .AddJwtBearer(options =>
        {
            options.TokenValidationParameters = new TokenValidationParameters
            {
                ValidateIssuerSigningKey = true,
                IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtSecretKey)),
                ValidateIssuer = true,
                ValidIssuer = jwtIssuer,
                ValidateAudience = true,
                ValidAudience = jwtAudience,
                ValidateLifetime = true,
                ClockSkew = TimeSpan.Zero
            };

            // Read token from cookie
            options.Events = new JwtBearerEvents
            {
                OnMessageReceived = context =>
                {
                    // Try to get token from cookie first
                    if (context.Request.Cookies.TryGetValue("access_token", out var token))
                    {
                        context.Token = token;
                    }
                    return Task.CompletedTask;
                }
            };
        });

        services.AddAuthorization();

        // Add rate limiting for login endpoint (disabled in testing)
        var isTestingEnvironment = configuration.GetValue<bool>("Testing:SkipSwagger");
        services.AddRateLimiter(options =>
        {
            options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;

            options.AddPolicy("LoginRateLimit", httpContext =>
                RateLimitPartition.GetFixedWindowLimiter(
                    partitionKey: httpContext.Connection.RemoteIpAddress?.ToString() ?? "unknown",
                    factory: _ => new FixedWindowRateLimiterOptions
                    {
                        // Use high limit for tests, normal limit for production
                        PermitLimit = isTestingEnvironment ? 1000 : 30,
                        Window = TimeSpan.FromMinutes(10),
                        QueueLimit = 0
                    }));
        });

        // Add OpenAPI documentation with Scalar UI (skip in testing environments)
        var skipOpenApi = configuration.GetValue<bool>("Testing:SkipSwagger");
        if (!skipOpenApi)
        {
            services.AddOpenApi(); // .NET 10 built-in OpenAPI support
        }

        // Add CORS
        services.AddCors(options =>
        {
            options.AddPolicy("Development", policy =>
            {
                // Development CORS policy - allow specific origins with credentials
                var allowedOrigins = configuration.GetSection("Cors:AllowedOrigins").Get<string[]>() 
                    ?? new[] { "http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:3003", "http://localhost:5173" };
                
                policy.WithOrigins(allowedOrigins)
                      .AllowAnyMethod()
                      .AllowAnyHeader()
                      .AllowCredentials(); // Required for cookie-based auth
            });

            options.AddPolicy("Production", policy =>
            {
                // Configure production CORS policy based on environment
                var allowedOrigins = configuration.GetSection("Cors:AllowedOrigins").Get<string[]>() ?? Array.Empty<string>();
                policy.WithOrigins(allowedOrigins)
                      .AllowAnyMethod()
                      .AllowAnyHeader()
                      .AllowCredentials();
            });
        });

        // Add health checks
        services.AddHealthChecks();

        return services;
    }
}