using BCrypt.Net;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace JoiabagurPV.Infrastructure.Data;

/// <summary>
/// Seeds the database with initial required data.
/// </summary>
public class DatabaseSeeder
{
    private readonly ApplicationDbContext _context;
    private readonly ILogger<DatabaseSeeder> _logger;

    // Default admin credentials - should be changed after first login
    private const string DefaultAdminUsername = "admin";
    private const string DefaultAdminPassword = "Admin123!";
    private const string DefaultAdminFirstName = "Administrador";
    private const string DefaultAdminLastName = "Sistema";

    // Predefined payment methods
    private static readonly (string Code, string Name, string Description)[] DefaultPaymentMethods = new[]
    {
        ("CASH", "Efectivo", "Pago en efectivo"),
        ("BIZUM", "Bizum", "Pago mediante Bizum"),
        ("TRANSFER", "Transferencia", "Transferencia bancaria"),
        ("CARD_OWN", "Tarjeta propia", "Pago con tarjeta de crédito/débito propia"),
        ("CARD_POS", "Tarjeta TPV", "Pago con tarjeta en terminal punto de venta"),
        ("PAYPAL", "PayPal", "Pago mediante PayPal")
    };

    public DatabaseSeeder(ApplicationDbContext context, ILogger<DatabaseSeeder> logger)
    {
        _context = context;
        _logger = logger;
    }

    /// <summary>
    /// Seeds the database with initial data if not already present.
    /// </summary>
    public async Task SeedAsync()
    {
        await SeedDefaultAdminAsync();
        await SeedPaymentMethodsAsync();
        await GiftCardSeedHelper.EnsureGiftCardPaymentMethodAsync(_context, _logger);
        await GiftCardSeedHelper.EnsureGiftCardSystemProductAsync(_context, _logger);
        await GiftCardSeedHelper.EnsureGiftCardMethodAssignedToAllPosAsync(_context, _logger);
    }

    private async Task SeedDefaultAdminAsync()
    {
        // Check if admin user already exists
        var adminExists = await _context.Users
            .AnyAsync(u => u.Username.ToLower() == DefaultAdminUsername.ToLower());

        if (adminExists)
        {
            _logger.LogInformation("Default admin user already exists, skipping seed");
            return;
        }

        _logger.LogInformation("Creating default admin user...");

        var admin = new User
        {
            Username = DefaultAdminUsername,
            PasswordHash = BCrypt.Net.BCrypt.HashPassword(DefaultAdminPassword, workFactor: 12),
            FirstName = DefaultAdminFirstName,
            LastName = DefaultAdminLastName,
            Role = UserRole.Administrator,
            IsActive = true
        };

        await _context.Users.AddAsync(admin);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Default admin user created successfully. Username: {Username}", DefaultAdminUsername);
        _logger.LogWarning("Please change the default admin password after first login!");
    }

    private async Task SeedPaymentMethodsAsync()
    {
        foreach (var (code, name, description) in DefaultPaymentMethods)
        {
            var exists = await _context.PaymentMethods
                .AnyAsync(pm => pm.Code == code);

            if (exists)
            {
                continue;
            }

            _logger.LogInformation("Creating payment method {Code}...", code);

            var paymentMethod = new PaymentMethod
            {
                Code = code,
                Name = name,
                Description = description,
                IsActive = true
            };

            await _context.PaymentMethods.AddAsync(paymentMethod);
        }

        await _context.SaveChangesAsync();
        _logger.LogInformation("Payment methods seeded successfully");
    }
}
