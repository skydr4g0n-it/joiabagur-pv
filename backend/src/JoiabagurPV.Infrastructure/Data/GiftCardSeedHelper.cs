using JoiabagurPV.Domain.Constants;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace JoiabagurPV.Infrastructure.Data;

/// <summary>
/// Idempotent seed helpers for gift card system product and payment method.
/// </summary>
public static class GiftCardSeedHelper
{
    public static async Task EnsureGiftCardPaymentMethodAsync(ApplicationDbContext context, ILogger logger)
    {
        var giftCardMethod = await context.PaymentMethods
            .FirstOrDefaultAsync(pm => pm.Code == GiftCardConstants.GiftCardPaymentMethodCode);

        if (giftCardMethod == null)
        {
            logger.LogInformation("Creating payment method {Code}...", GiftCardConstants.GiftCardPaymentMethodCode);
            giftCardMethod = new PaymentMethod
            {
                Code = GiftCardConstants.GiftCardPaymentMethodCode,
                Name = "Tarjeta regalo",
                Description = "Cobertura con tarjeta regalo (sistema)",
                IsActive = true
            };
            await context.PaymentMethods.AddAsync(giftCardMethod);
            await context.SaveChangesAsync();
        }
    }

    public static async Task EnsureGiftCardSystemProductAsync(ApplicationDbContext context, ILogger logger)
    {
        var exists = await context.Products
            .AnyAsync(p => p.SKU == GiftCardConstants.SystemProductSku);

        if (exists)
        {
            return;
        }

        logger.LogInformation("Creating system product {Sku}...", GiftCardConstants.SystemProductSku);
        var product = new Product
        {
            SKU = GiftCardConstants.SystemProductSku,
            Name = "Tarjeta regalo",
            Description = "Producto de sistema para emisión de tarjetas regalo",
            Price = 0.01m,
            IsActive = true,
            SystemProductKind = SystemProductKind.GiftCard
        };
        await context.Products.AddAsync(product);
        await context.SaveChangesAsync();
    }

    public static async Task EnsureGiftCardMethodAssignedToAllPosAsync(ApplicationDbContext context, ILogger logger)
    {
        var giftCardMethod = await context.PaymentMethods
            .FirstAsync(pm => pm.Code == GiftCardConstants.GiftCardPaymentMethodCode);

        var posIds = await context.PointOfSales.Select(p => p.Id).ToListAsync();
        foreach (var posId in posIds)
        {
            await EnsureGiftCardMethodAssignedToPosAsync(context, giftCardMethod.Id, posId, logger);
        }
    }

    public static async Task EnsureGiftCardMethodAssignedToPosAsync(
        ApplicationDbContext context,
        Guid giftCardPaymentMethodId,
        Guid pointOfSaleId,
        ILogger logger)
    {
        var assignment = await context.PointOfSalePaymentMethods
            .FirstOrDefaultAsync(a => a.PointOfSaleId == pointOfSaleId && a.PaymentMethodId == giftCardPaymentMethodId);

        if (assignment == null)
        {
            logger.LogInformation(
                "Assigning {Code} to POS {PosId}",
                GiftCardConstants.GiftCardPaymentMethodCode,
                pointOfSaleId);

            await context.PointOfSalePaymentMethods.AddAsync(new PointOfSalePaymentMethod
            {
                PointOfSaleId = pointOfSaleId,
                PaymentMethodId = giftCardPaymentMethodId,
                IsActive = true
            });
            await context.SaveChangesAsync();
            return;
        }

        if (!assignment.IsActive)
        {
            assignment.IsActive = true;
            assignment.DeactivatedAt = null;
            await context.SaveChangesAsync();
        }
    }
}
