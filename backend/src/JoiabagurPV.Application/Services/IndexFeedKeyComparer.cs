using System.Security.Cryptography;
using System.Text;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Constant-time comparison of the index-feed API key against the configured secrets.
/// </summary>
/// <remarks>
/// <see cref="CryptographicOperations.FixedTimeEquals(ReadOnlySpan{byte}, ReadOnlySpan{byte})"/>
/// returns early when the spans have different lengths. Callers of this helper never take that
/// path: a dummy same-length comparison always runs first, so a wrong key of a different length
/// does not become a shorter code path.
/// </remarks>
public static class IndexFeedKeyComparer
{
    /// <summary>
    /// Whether <paramref name="provided"/> matches the current key, or the previous key when
    /// that value is configured and non-empty.
    /// </summary>
    public static bool Matches(string? provided, string current, string? previous)
    {
        ArgumentException.ThrowIfNullOrEmpty(current);

        var currentBytes = Encoding.UTF8.GetBytes(current);
        var previousSet = !string.IsNullOrWhiteSpace(previous);
        var previousBytes = previousSet ? Encoding.UTF8.GetBytes(previous!) : [];

        if (string.IsNullOrEmpty(provided))
        {
            DummyEquals(currentBytes);
            if (previousSet)
            {
                DummyEquals(previousBytes);
            }

            return false;
        }

        var providedBytes = Encoding.UTF8.GetBytes(provided);

        // Both comparisons always run when a previous key exists, using bitwise or so a match
        // on the current key does not skip the second FixedTimeEquals.
        var currentMatch = FixedTimeEquals(providedBytes, currentBytes);
        var previousMatch = previousSet && FixedTimeEquals(providedBytes, previousBytes);

        return currentMatch | previousMatch;
    }

    private static bool FixedTimeEquals(byte[] left, byte[] right)
    {
        if (left.Length == right.Length)
        {
            return CryptographicOperations.FixedTimeEquals(left, right);
        }

        DummyEquals(right);
        return false;
    }

    private static void DummyEquals(byte[] value) =>
        CryptographicOperations.FixedTimeEquals(value, value);
}
