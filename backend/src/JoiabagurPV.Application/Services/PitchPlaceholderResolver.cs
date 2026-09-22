using System.Globalization;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// The values the two placeholders of a generated argument are resolved to: those of the anchored
/// product at the point of sale of the request.
/// </summary>
public readonly record struct PitchAnchor(decimal Price, int Quantity);

/// <summary>The outcome of resolving an argument: the text, or nothing.</summary>
public sealed record PitchResolution(bool IsResolved, string? Text)
{
    /// <summary>The argument cannot be shipped. Never carries the raw template.</summary>
    public static readonly PitchResolution Withheld = new(false, null);
}

/// <summary>
/// Resolves <c>{{price}}</c> and <c>{{stock}}</c> in a generated argument against the anchored
/// product, and withholds the argument when anything is left unresolved.
/// </summary>
/// <remarks>
/// <para>
/// <strong>Only the two exact tokens are replaced.</strong> Afterwards any remaining <c>{{</c> or
/// <c>}}</c> — a variant spelling like <c>{{ price }}</c>, an unknown name like <c>{{precio}}</c>,
/// a malformed token — withholds the argument. That is the closed failure: normalising spellings
/// would be guessing what the model meant, and the raw template must never reach the operator.
/// </para>
/// <para>
/// <c>{{price}}</c> becomes the catalog price in Spanish currency — «39,90 €», with the
/// non-breaking space the culture puts before the symbol. <c>{{stock}}</c> becomes a bare whole
/// number: 188 of the 213 arguments of the C30b pass (88.3 %) write it where a number reads
/// naturally — «y tenemos {{stock}} en tienda» — while «N unidades» would break the four already
/// followed by «unidades» and a label would break all 188.
/// </para>
/// <para>
/// <strong>No anchor, no resolution.</strong> The placeholders name no product. C34 always
/// anchors, but the first consumer of the free query or of the agent — where one argument speaks
/// about several pieces with the same two tokens — would otherwise put the price of one piece next
/// to the description of another. Called without an anchor, this withholds, always.
/// </para>
/// </remarks>
public static class PitchPlaceholderResolver
{
    /// <summary>The price placeholder, exactly as the service writes it.</summary>
    public const string PriceToken = "{{price}}";

    /// <summary>The stock placeholder, exactly as the service writes it.</summary>
    public const string StockToken = "{{stock}}";

    private static readonly CultureInfo Spanish = CultureInfo.GetCultureInfo("es-ES");

    /// <summary>
    /// Resolves the two placeholders of <paramref name="template"/> against <paramref name="anchor"/>.
    /// </summary>
    /// <returns>The resolved text, or <see cref="PitchResolution.Withheld"/>.</returns>
    public static PitchResolution Resolve(string template, PitchAnchor? anchor)
    {
        ArgumentNullException.ThrowIfNull(template);

        if (anchor is not { } values)
        {
            return PitchResolution.Withheld;
        }

        var text = template
            .Replace(PriceToken, values.Price.ToString("C2", Spanish), StringComparison.Ordinal)
            .Replace(StockToken, values.Quantity.ToString(CultureInfo.InvariantCulture), StringComparison.Ordinal);

        if (text.Contains("{{", StringComparison.Ordinal) || text.Contains("}}", StringComparison.Ordinal))
        {
            return PitchResolution.Withheld;
        }

        return new PitchResolution(true, text);
    }
}
