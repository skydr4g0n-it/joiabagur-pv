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
public class AssistedSearchCandidateCache : IAssistedSearchCandidateCache
{
    private readonly IMemoryCache _cache;
    private readonly IOptionsMonitor<AiSearchOptions> _options;

    public AssistedSearchCandidateCache(IMemoryCache cache, IOptionsMonitor<AiSearchOptions> options)
    {
        _cache = cache;
        _options = options;
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

                // The shared memory cache has no size limit configured, so a size is only
                // meaningful if one is set. Sliding expiration is deliberately absent: a query
                // repeated for ten minutes should re-ask the retriever, not pin a stale ranking.
                Priority = CacheItemPriority.Low
            });
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
