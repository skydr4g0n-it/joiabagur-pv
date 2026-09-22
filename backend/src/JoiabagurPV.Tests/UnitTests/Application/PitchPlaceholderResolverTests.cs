using System.Globalization;
using FluentAssertions;
using JoiabagurPV.Application.Services;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// The resolver as a pure unit: no service, no database, no AI.
/// </summary>
/// <remarks>
/// Expected prices are formatted with the same culture rather than written out by hand: es-ES puts
/// a non-breaking space before the euro sign, and a literal in a test is how that character gets
/// silently replaced by an ordinary space and the test starts failing for the wrong reason.
/// </remarks>
public class PitchPlaceholderResolverTests
{
    private static readonly CultureInfo Spanish = CultureInfo.GetCultureInfo("es-ES");

    [Fact]
    public void PlaceholderResolver_ReplacesBothTokens_WithAnchorValues()
    {
        var resolution = PitchPlaceholderResolver.Resolve(
            "Disponibles por {{price}} y tenemos {{stock}} en tienda.",
            new PitchAnchor(39.90m, 3));

        resolution.IsResolved.Should().BeTrue();
        resolution.Text.Should().Be($"Disponibles por {39.90m.ToString("C2", Spanish)} y tenemos 3 en tienda.");
        resolution.Text.Should().Contain("39,90").And.Contain("€").And.NotContain("{{").And.NotContain("}}");
    }

    [Fact]
    public void PlaceholderResolver_ReplacesEveryOccurrence()
    {
        var resolution = PitchPlaceholderResolver.Resolve(
            "{{price}}, sí, {{price}}; quedan {{stock}} y luego {{stock}}.", new PitchAnchor(10m, 2));

        resolution.Text.Should().Be($"{10m.ToString("C2", Spanish)}, sí, {10m.ToString("C2", Spanish)}; quedan 2 y luego 2.");
    }

    /// <summary>A whole number in the invariant culture: no thousands separator can creep in.</summary>
    [Fact]
    public void PlaceholderResolver_Stock_IsAnInvariantWholeNumber()
    {
        var resolution = PitchPlaceholderResolver.Resolve("Tenemos {{stock}}.", new PitchAnchor(1m, 1234));

        resolution.Text.Should().Be("Tenemos 1234.");
    }

    [Fact]
    public void PlaceholderResolver_ZeroStock_IsResolvedToZero()
    {
        var resolution = PitchPlaceholderResolver.Resolve("Quedan {{stock}}.", new PitchAnchor(1m, 0));

        resolution.IsResolved.Should().BeTrue();
        resolution.Text.Should().Be("Quedan 0.");
    }

    [Theory]
    [InlineData("Por {{precio}} en tienda.")]
    [InlineData("Por {{price}} y {{discount}}.")]
    public void PlaceholderResolver_UnknownPlaceholder_Withholds(string template)
    {
        var resolution = PitchPlaceholderResolver.Resolve(template, new PitchAnchor(39.90m, 3));

        resolution.Should().Be(PitchResolution.Withheld);
        resolution.Text.Should().BeNull("the raw template is never handed back");
    }

    /// <summary>Only the exact tokens: normalising a spelling would be guessing what the model meant.</summary>
    [Theory]
    [InlineData("Por {{ price }}.")]
    [InlineData("Por {{Price}}.")]
    [InlineData("Quedan {{STOCK}}.")]
    [InlineData("Quedan {{stock }}.")]
    public void PlaceholderResolver_VariantSpelling_Withholds(string template)
    {
        PitchPlaceholderResolver.Resolve(template, new PitchAnchor(39.90m, 3))
            .Should().Be(PitchResolution.Withheld);
    }

    [Theory]
    [InlineData("Por {{price y quedan {{stock}}.")]
    [InlineData("Quedan stock}} unidades.")]
    [InlineData("Una llave {{ suelta.")]
    public void PlaceholderResolver_MalformedToken_Withholds(string template)
    {
        PitchPlaceholderResolver.Resolve(template, new PitchAnchor(39.90m, 3))
            .Should().Be(PitchResolution.Withheld);
    }

    /// <summary>
    /// The placeholders name no product. Without an anchor there is nothing to resolve them against,
    /// and guessing would put the price of one piece next to the description of another.
    /// </summary>
    [Theory]
    [InlineData("Disponibles por {{price}}.")]
    [InlineData("Un texto sin marcadores.")]
    public void PlaceholderResolver_WithoutAnchor_Withholds(string template)
    {
        PitchPlaceholderResolver.Resolve(template, anchor: null)
            .Should().Be(PitchResolution.Withheld);
    }

    [Fact]
    public void PlaceholderResolver_TextWithoutPlaceholders_IsDeliveredAsIs()
    {
        var resolution = PitchPlaceholderResolver.Resolve("Plata de ley 925.", new PitchAnchor(1m, 1));

        resolution.IsResolved.Should().BeTrue();
        resolution.Text.Should().Be("Plata de ley 925.");
    }
}
