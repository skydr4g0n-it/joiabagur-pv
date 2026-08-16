using System.Security.Cryptography;
using System.Text;
using JoiabagurPV.Domain.Entities;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Hashes the product inputs an enrichment proposal was derived from.
/// </summary>
/// <remarks>
/// <para>
/// <strong>Not the indexer's hash.</strong> The Python side computes its own
/// <c>source_hash</c> over the canonical document text of an approved profile, to decide whether
/// an embedding must be recomputed. This one covers the inputs, and answers two different
/// questions: whether re-running a batch has to pay for a model call, and whether re-running it
/// would overwrite work a person already did.
/// </para>
/// <para>
/// Both of those matter equally. At ~1.000 products a repeated batch is real money; and a
/// silent overwrite of a reviewed profile is the kind of loss that is only noticed once the
/// review campaign is over.
/// </para>
/// </remarks>
public static class ProductEnrichmentSourceHash
{
    /// <summary>
    /// Separator between fields. A character that cannot appear in any of them, so that moving
    /// text across field boundaries cannot produce the same digest.
    /// </summary>
    private const char Separator = '';

    /// <summary>
    /// Computes the digest for a product, in a fixed field order.
    /// </summary>
    /// <param name="product">Product whose text feeds the extractor.</param>
    /// <param name="collectionName">Collection name, or null when the product has none.</param>
    /// <returns>A lowercase hexadecimal SHA-256 digest.</returns>
    public static string Compute(Product product, string? collectionName)
    {
        ArgumentNullException.ThrowIfNull(product);

        // Order is fixed and the fields are exactly those sent for enrichment. Adding a field
        // here that the extractor never sees would invalidate every stored profile without any
        // proposal actually changing.
        var canonical = string.Join(
            Separator,
            product.SKU,
            product.Name,
            product.Description ?? string.Empty,
            collectionName ?? string.Empty);

        var digest = SHA256.HashData(Encoding.UTF8.GetBytes(canonical));

        return Convert.ToHexStringLower(digest);
    }
}
