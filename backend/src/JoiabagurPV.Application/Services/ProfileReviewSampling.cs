using System.Security.Cryptography;
using System.Text;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// What one stratum contributed to a batch, and whether it had it to give.
/// </summary>
/// <param name="Stratum">The stratum drawn from.</param>
/// <param name="Items">The drawn items, in the order the seed dictates.</param>
/// <param name="Available">How many profiles the stratum holds in the corpus being drawn from.</param>
/// <param name="Quota">How many were asked for.</param>
/// <remarks>
/// <see cref="Available"/> travels because the published rate is weighted by the real size of
/// each stratum and not by its size in the sample. Without the figure beside the draw, the
/// weighting has to be re-derived somewhere else from a second query, which is the same mistake
/// as computing the stratum twice.
/// </remarks>
public record StratumDraw<TItem>(
    EvidenceStratum Stratum,
    IReadOnlyList<TItem> Items,
    int Available,
    int Quota)
{
    /// <summary>
    /// Whether the stratum ran out before its quota was met.
    /// </summary>
    /// <remarks>
    /// Reported rather than silently tolerated. A stratum that cannot fill its quota makes the
    /// interval around its rate wider than the design assumed, and a batch that quietly comes
    /// back short would be read as if every cell were full.
    /// </remarks>
    public bool Exhausted => Available < Quota;
}

/// <summary>
/// Draws a reproducible batch from each stratum. Pure: no database, no clock, no randomness.
/// </summary>
/// <remarks>
/// <para>
/// <strong>Reproducible, not stored.</strong> What the batch needs is that anyone can reconstruct
/// it from a published seed; storing it would need an entity, an entity would need a migration,
/// and the storage this capability runs on was reserved precisely so no further migration would
/// be required. A declared seed buys the same property for nothing.
/// </para>
/// <para>
/// Not <see cref="Random"/> with a seed, and not <see cref="object.GetHashCode"/>. The first is
/// only stable per runtime version by convention, and the second is explicitly not stable across
/// processes — a batch that differs between two runs of the same seed would make the published
/// figure unreconstructable, which is the one property this exists to provide.
/// </para>
/// </remarks>
public static class ProfileReviewSampling
{
    /// <summary>
    /// Separator between the product and the seed, so that moving characters across the boundary
    /// cannot produce the same key.
    /// </summary>
    private const char Separator = '';

    /// <summary>
    /// The ordering key of one product under one seed.
    /// </summary>
    /// <param name="productId">Product being ordered.</param>
    /// <param name="seed">The declared seed of the session.</param>
    /// <returns>A lowercase hexadecimal SHA-256 digest.</returns>
    /// <remarks>
    /// The identifier is rendered in its invariant <c>D</c> form rather than by its bytes, whose
    /// order differs between platforms for the first three groups of a GUID. A key that depends
    /// on the host's endianness would reproduce on one machine and not on another.
    /// </remarks>
    public static string OrderKey(Guid productId, string seed)
    {
        var canonical = string.Concat(
            productId.ToString("D", System.Globalization.CultureInfo.InvariantCulture),
            Separator,
            seed ?? string.Empty);

        return Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(canonical)));
    }

    /// <summary>
    /// Orders a stratum's profiles by the seed, deterministically and totally.
    /// </summary>
    /// <typeparam name="TItem">The item being ordered.</typeparam>
    /// <param name="items">The stratum's profiles.</param>
    /// <param name="productId">How to read the product identifier of an item.</param>
    /// <param name="seed">The declared seed of the session.</param>
    /// <returns>The profiles, in the order the seed dictates.</returns>
    public static IReadOnlyList<TItem> Order<TItem>(
        IEnumerable<TItem> items,
        Func<TItem, Guid> productId,
        string seed)
    {
        ArgumentNullException.ThrowIfNull(items);
        ArgumentNullException.ThrowIfNull(productId);

        // The identifier breaks a tie. Two products cannot collide on SHA-256 in practice, but
        // an ordering that is total by construction is one nobody has to reason about.
        return [.. items
            .OrderBy(item => OrderKey(productId(item), seed), StringComparer.Ordinal)
            .ThenBy(productId, Comparer<Guid>.Default)];
    }

    /// <summary>
    /// Draws one stratum's share of the batch.
    /// </summary>
    /// <typeparam name="TItem">The item being drawn.</typeparam>
    /// <param name="stratum">The stratum being drawn from.</param>
    /// <param name="items">Every profile of that stratum in the corpus.</param>
    /// <param name="productId">How to read the product identifier of an item.</param>
    /// <param name="seed">The declared seed of the session.</param>
    /// <param name="quota">How many to draw.</param>
    /// <returns>The draw, reporting what the stratum held as well as what it gave.</returns>
    /// <remarks>
    /// A stratum smaller than its quota contributes everything it has rather than failing. The
    /// batch is a sample and a short cell is a fact about the corpus; refusing to draw would
    /// trade a declared limitation for no batch at all.
    /// </remarks>
    public static StratumDraw<TItem> Draw<TItem>(
        EvidenceStratum stratum,
        IReadOnlyCollection<TItem> items,
        Func<TItem, Guid> productId,
        string seed,
        int quota)
    {
        ArgumentNullException.ThrowIfNull(items);
        ArgumentOutOfRangeException.ThrowIfNegative(quota);

        var ordered = Order(items, productId, seed);

        return new StratumDraw<TItem>(
            stratum,
            [.. ordered.Take(quota)],
            items.Count,
            quota);
    }
}
