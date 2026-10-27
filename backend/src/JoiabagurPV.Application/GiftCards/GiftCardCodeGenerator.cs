using System.Security.Cryptography;
using System.Text;
using JoiabagurPV.Domain.Constants;

namespace JoiabagurPV.Application.GiftCards;

/// <summary>
/// Generates unique GC- prefixed Crockford base32 codes.
/// </summary>
public class GiftCardCodeGenerator
{
    private const string CrockfordAlphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
    private const int SuffixLength = 8;

    public string GenerateCode()
    {
        var bytes = RandomNumberGenerator.GetBytes(SuffixLength);
        var builder = new StringBuilder(GiftCardConstants.CodePrefix, GiftCardConstants.CodePrefix.Length + SuffixLength);
        foreach (var b in bytes)
        {
            builder.Append(CrockfordAlphabet[b % CrockfordAlphabet.Length]);
        }

        return builder.ToString();
    }
}
