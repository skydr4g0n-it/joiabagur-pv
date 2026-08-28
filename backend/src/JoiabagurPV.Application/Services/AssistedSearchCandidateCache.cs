using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Options;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Short-lived cache of the candidates the AI service returned for a query.
/// </summary>
/// <remarks>
/// <para>
/// Only identifiers, scores and match reasons are cached — never a price, a quantity or a photo.
/// Hydration runs again on every hit, so a cached search can never serve a stale figure. What is
/// cached is the similarity, which does not change between two consecutive requests; what is
/// recomputed is the number, which can.
/// </para>
/// <para>
/// <strong>The key carries the point of sale even though retrieval does not depend on it yet.</strong>
/// The retriever currently applies no point-of-sale filter, so today the same query returns the
/// same candidates everywhere and including the point of sale only lowers the hit rate. It is
/// included regardless, because the day the retriever gains that filter, a key without it turns
/// into a cross-point-of-sale leak — and nobody implementing a filter in another service is
/// going to think to audit a cache key over here. A lower hit rate is a price; an isolation
/// incident is not.
/// </para>
/// </remarks>
public class AssistedSearchCandidateCache : IAssistedSearchCandidateCache, IDisposable
{
    private readonly MemoryCache _cache;
    private readonly IOptionsMonitor<AiSearchOptions> _options;

    /// <summary>
    /// Builds the cache with a real entry cap.
    /// </summary>
    /// <remarks>
    /// A dedicated instance rather than the shared <c>IMemoryCache</c>, and that is not
    /// incidental: <c>SizeLimit</c> is a property of the cache, not of the entry, so setting it
    /// on the shared one would force every other consumer — the dashboard among them — to start
    /// declaring a size on entries that never had one, and those writes would throw.
    ///
    /// The cap is read once, at construction. Changing it needs a restart, unlike the list of
    /// enabled points of sale: that one exists to be flipped without a redeploy, this one is a
    /// memory bound nobody tunes live.
    /// </remarks>
    public AssistedSearchCandidateCache(IOptionsMonitor<AiSearchOptions> options)
    {
        _options = options;
        _cache = new MemoryCache(new MemoryCacheOptions
        {
            SizeLimit = Math.Max(1, options.CurrentValue.CandidateCacheSize)
        });
    }

    /// <inheritdoc/>
    public string BuildKey(Guid pointOfSaleId, string query, AiSearchFilters filters, int window)
    {
        var normalizedQuery = Normalize(query);

        // Filters are folded in order-insensitively so that selecting two materials in a
        // different order is the same search, which is what the operator means.
        var materials = string.Join(
            ",",
            filters.Materials
                .Select(Normalize)
                .Where(material => material.Length > 0)
                .OrderBy(material => material, StringComparer.Ordinal));

        var raw = string.Join(
            "|",
            pointOfSaleId.ToString("N"),
            window.ToString(CultureInfo.InvariantCulture),
            normalizedQuery,
            materials,
            Normalize(filters.Category ?? string.Empty),
            Normalize(filters.FamilyId ?? string.Empty));

        // Hashed rather than stored verbatim: the operator's query is free text that may
        // incidentally carry personal data, and a cache key is one of the places nobody
        // remembers to redact.
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(raw));
        return "ai-search:" + Convert.ToHexString(hash);
    }

    /// <inheritdoc/>
    public bool TryGet(string key, out AiSearchResponse? candidates) =>
        _cache.TryGetValue(key, out candidates);

    /// <inheritdoc/>
    public void Set(string key, AiSearchResponse candidates)
    {
        var options = _options.CurrentValue;

        _cache.Set(
            key,
            candidates,
            new MemoryCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow =
                    TimeSpan.FromSeconds(options.CandidateCacheTtlSeconds),

                // One unit per cached candidate set, so the configured limit reads as a number
                // of searches rather than as an opaque weight. Required: with SizeLimit set, an
                // entry without a size throws.
                Size = 1,

                // Sliding expiration is deliberately absent: a query repeated for ten minutes
                // should re-ask the retriever, not pin a stale ranking indefinitely.
                Priority = CacheItemPriority.Low
            });
    }

    /// <summary>Disposes the dedicated cache instance.</summary>
    public void Dispose()
    {
        _cache.Dispose();
        GC.SuppressFinalize(this);
    }

    /// <summary>
    /// Case-insensitive, accent-insensitive, whitespace-collapsed form, so that trivially
    /// different spellings of the same search share an entry.
    /// </summary>
    private static string Normalize(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        var decomposed = value.Trim().ToLowerInvariant().Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(decomposed.Length);
        var lastWasSpace = false;

        foreach (var character in decomposed)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            if (char.IsWhiteSpace(character))
            {
                if (!lastWasSpace && builder.Length > 0)
                {
                    builder.Append(' ');
                    lastWasSpace = true;
                }

                continue;
            }

            builder.Append(character);
            lastWasSpace = false;
        }

        return builder.ToString().TrimEnd().Normalize(NormalizationForm.FormC);
    }
}
