namespace JoiabagurPV.Application.Services;

/// <summary>
/// Pure function <c>price-band/v1</c>. No HTTP, no EF. Changing the cuts requires a new
/// version string; C13 re-syncs without re-embedding because the band is not in
/// <c>doc_text</c>.
/// </summary>
public static class PriceBand
{
    /// <summary>Version of the cut table. A new table is a new version.</summary>
    public const string PriceBandVersion = "price-band/v1";

    public const string Lt30 = "lt-30";
    public const string From30To80 = "30-80";
    public const string From80To150 = "80-150";
    public const string From150To300 = "150-300";
    public const string Gte300 = "gte-300";

    /// <summary>
    /// Classifies a price in EUR into a <c>price-band/v1</c> bucket.
    /// </summary>
    /// <exception cref="ArgumentOutOfRangeException">Negative prices are a domain invariant, not <c>lt-30</c>.</exception>
    public static string From(decimal price)
    {
        if (price < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(price), price, "Price must be non-negative.");
        }

        if (price < 30m)
        {
            return Lt30;
        }

        if (price < 80m)
        {
            return From30To80;
        }

        if (price < 150m)
        {
            return From80To150;
        }

        if (price < 300m)
        {
            return From150To300;
        }

        return Gte300;
    }
}
