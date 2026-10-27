using JoiabagurPV.Domain.Entities;

namespace JoiabagurPV.Domain.GiftCards;

/// <summary>
/// Shared economic amount rules for gift card coverage.
/// </summary>
public static class GiftCardEconomics
{
    public static decimal GetSaleGross(Sale sale) => sale.Price * sale.Quantity;

    public static decimal GetEconomicSaleAmount(decimal gross, decimal netCoverageOnSale, bool isIssuanceSale)
    {
        if (isIssuanceSale || netCoverageOnSale <= 0)
            return gross;

        return gross - netCoverageOnSale;
    }

    public static decimal GetEconomicSaleAmount(Sale sale, decimal netCoverageOnSale, bool isIssuanceSale) =>
        GetEconomicSaleAmount(GetSaleGross(sale), netCoverageOnSale, isIssuanceSale);

    public static decimal GetReturnEconomicAmount(
        Sale sale,
        decimal netCoverageOnSale,
        int returnedQuantity)
    {
        if (returnedQuantity <= 0 || sale.Quantity <= 0)
            return 0m;

        var grossReturn = sale.Price * returnedQuantity;
        if (netCoverageOnSale <= 0)
            return grossReturn;

        var coverageShare = netCoverageOnSale * returnedQuantity / sale.Quantity;
        return grossReturn - coverageShare;
    }

    public static bool IsExpiredForRedemption(DateOnly expiryDateUtc)
    {
        var today = DateOnly.FromDateTime(DateTime.UtcNow);
        return today > expiryDateUtc;
    }

    public static bool IsValidExpiryForIssuance(DateOnly expiryDateUtc)
    {
        var today = DateOnly.FromDateTime(DateTime.UtcNow);
        return expiryDateUtc > today;
    }
}
