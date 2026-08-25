namespace JoiabagurPV.Application.Services;

/// <summary>
/// Stock buckets for the POS availability feed. Exact quantity must not leave this process.
/// </summary>
public static class QtyBucket
{
    public const string Zero = "0";
    public const string OneOrTwo = "1-2";
    public const string ThreeOrMore = "3+";

    /// <summary>Maps an inventory quantity to <c>0</c>, <c>1-2</c> or <c>3+</c>.</summary>
    public static string From(int quantity)
    {
        if (quantity <= 0)
        {
            return Zero;
        }

        if (quantity <= 2)
        {
            return OneOrTwo;
        }

        return ThreeOrMore;
    }
}
