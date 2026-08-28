using JoiabagurPV.API.Extensions;
using JoiabagurPV.API.Middleware;
using JoiabagurPV.Application.Extensions;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Infrastructure.Extensions;
using Microsoft.AspNetCore.HttpOverrides;
using Microsoft.EntityFrameworkCore;
using Scalar.AspNetCore;
using Serilog;

var builder = WebApplication.CreateBuilder(args);

// Configure Serilog
builder.Host.UseSerilog((context, configuration) =>
{
    configuration.ReadFrom.Configuration(context.Configuration);
});

// Add layers
builder.Services.AddInfrastructure(builder.Configuration);
builder.Services.AddApplication();

// Outbound integration with the jbg-ai service. Its own line rather than a parameter on
// AddApplication(), whose signature the integration tests already depend on. Configuration is
// validated during start-up: a missing secret stops the host instead of surfacing later as a
// 401 the AI service is required not to explain.
builder.Services.AddAiGateway(builder.Configuration);

// Thresholds of the hybrid profile review policy, validated at start-up for the same reason:
// a value outside its range must stop the host, not route a batch of profiles by a rule that
// cannot be satisfied.
builder.Services.AddProfileReview(builder.Configuration);

// Index-feed API key. Validated at start-up for the same reason as the gateway secret: a
// missing or short key must stop the host, not look like a 401 from the first C13 pull.
builder.Services.AddIndexFeed(builder.Configuration);

// Assisted search (C15). Bound through IOptionsMonitor because the per-point-of-sale switch has
// to be flippable without a redeploy: that reloadability is why it lives in configuration rather
// than in a column.
builder.Services.AddAssistedSearch(builder.Configuration);

// Add API services
builder.Services.AddApiServices(builder.Configuration);

// Behind nginx on the same host: trust forwarded proto/host so Request.Scheme is https and UseHttpsRedirection does not break the SPA.
builder.Services.Configure<ForwardedHeadersOptions>(options =>
{
    options.ForwardedHeaders = ForwardedHeaders.XForwardedFor | ForwardedHeaders.XForwardedProto;
    options.KnownNetworks.Clear();
    options.KnownProxies.Clear();
});

var app = builder.Build();

// Apply migrations and seed database
using (var scope = app.Services.CreateScope())
{
    var services = scope.ServiceProvider;
    try
    {
        var context = services.GetRequiredService<ApplicationDbContext>();
        await context.Database.MigrateAsync();

        var seeder = services.GetRequiredService<DatabaseSeeder>();
        await seeder.SeedAsync();
    }
    catch (Exception ex)
    {
        var logger = services.GetRequiredService<ILogger<Program>>();
        logger.LogError(ex, "An error occurred while migrating or seeding the database");
        throw;
    }
}

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    // Map OpenAPI specification endpoint
    app.MapOpenApi(); // Available at: /openapi/v1.json
    
    // Map Scalar API reference UI
    app.MapScalarApiReference(); // Available at: /scalar/v1
}

// Must be first: reverse proxy headers (nginx → Kestrel).
app.UseForwardedHeaders();

// Add CORS BEFORE static files and HTTPS redirection to handle preflight requests correctly,
// and to ensure CORS headers are present on static file responses for cross-origin requests.
app.UseCors(app.Environment.IsDevelopment() ? "Development" : "Production");

// Serve static files from wwwroot/ (e.g., bundled React SPA in production).
// Safe when wwwroot/ is absent or empty — middleware simply passes through.
app.UseStaticFiles();

// HTTPS redirection - skip OPTIONS requests (preflight) and HTTP requests in development to avoid CORS issues
// In development, allow HTTP connections from frontend without redirecting
app.UseWhen(context => 
    context.Request.Method != "OPTIONS" && 
    (app.Environment.IsProduction() || context.Request.IsHttps), 
    appBuilder =>
{
    appBuilder.UseHttpsRedirection();
});

// Add rate limiting
app.UseRateLimiter();

// Add middleware
app.UseMiddleware<ExceptionHandlingMiddleware>();

// Add authentication and authorization
app.UseAuthentication();
app.UseAuthorization();

// Map controllers
app.MapControllers();

// SPA fallback: serve index.html for / and client routes; unknown /api/* stays 404 (no HTML).
app.MapFallback(async context =>
{
    if (context.Request.Path.StartsWithSegments("/api", StringComparison.OrdinalIgnoreCase))
    {
        context.Response.StatusCode = StatusCodes.Status404NotFound;
        return;
    }

    var webRoot = app.Environment.WebRootPath;
    if (string.IsNullOrEmpty(webRoot))
    {
        context.Response.StatusCode = StatusCodes.Status404NotFound;
        return;
    }

    var indexPath = Path.Combine(webRoot, "index.html");
    if (!File.Exists(indexPath))
    {
        context.Response.StatusCode = StatusCodes.Status404NotFound;
        return;
    }

    context.Response.ContentType = "text/html; charset=utf-8";
    await context.Response.SendFileAsync(indexPath);
});

app.Run();