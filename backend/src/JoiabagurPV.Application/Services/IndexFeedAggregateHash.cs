using System.Security.Cryptography;
using System.Text;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// SHA-256 digest of the global indexable set. Computed once per request, never over a page.
/// </summary>
public static class IndexFeedAggregateHash
{
    /// <summary>
    /// Hex lowercase SHA-256 of the UTF-8 concatenation of canonical <c>D</c>-format product
    /// identifiers, sorted. Fixed-width values make a separator unnecessary.
    /// </summary>
    public static string OfProductIds(IEnumerable<Guid> productIds)
    {
        ArgumentNullException.ThrowIfNull(productIds);

        var payload = string.Concat(productIds.OrderBy(id => id).Select(id => id.ToString("D")));
        return Sha256Hex(payload);
    }

    /// <summary>
    /// Hex lowercase SHA-256 of the UTF-8 concatenation of canonical <c>D</c>-format
    /// <c>(pointOfSaleId, productId)</c> pairs of currently assigned active inventory, sorted
    /// by those two identifiers.
    /// </summary>
    public static string OfPosPairs(IEnumerable<(Guid PointOfSaleId, Guid ProductId)> pairs)
    {
        ArgumentNullException.ThrowIfNull(pairs);

        var payload = string.Concat(
            pairs
                .OrderBy(pair => pair.PointOfSaleId)
                .ThenBy(pair => pair.ProductId)
                .Select(pair => pair.PointOfSaleId.ToString("D") + pair.ProductId.ToString("D")));

        return Sha256Hex(payload);
    }

    private static string Sha256Hex(string payload)
    {
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(payload));
        return Convert.ToHexString(hash).ToLowerInvariant();
    }
}
