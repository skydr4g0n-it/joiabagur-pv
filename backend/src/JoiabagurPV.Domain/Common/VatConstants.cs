namespace JoiabagurPV.Domain.Common;

/// <summary>
/// Shared VAT rate. Sale prices are stored VAT-inclusive and every line uses this rate.
/// </summary>
public static class VatConstants
{
    /// <summary>
    /// Standard VAT rate (21%). Divisor for a gross amount is <c>1 + StandardRate</c>.
    /// </summary>
    public const decimal StandardRate = 0.21m;
}
