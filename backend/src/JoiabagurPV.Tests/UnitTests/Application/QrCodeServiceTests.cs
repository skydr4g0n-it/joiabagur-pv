using FluentAssertions;
using JoiabagurPV.Application.Services;

namespace JoiabagurPV.Tests.UnitTests.Application;

public class QrCodeServiceTests
{
    private readonly QrCodeService _sut;

    public QrCodeServiceTests()
    {
        _sut = new QrCodeService();
    }

    [Fact]
    public void GenerateSvg_WithValidSku_ReturnsValidSvg()
    {
        var result = _sut.GenerateSvg("TEST-SKU-001");

        result.Should().NotBeNullOrWhiteSpace();
        result.Should().Contain("<svg");
        result.Should().Contain("</svg>");
        result.Should().Contain("xmlns=\"http://www.w3.org/2000/svg\"");
    }

    [Fact]
    public void GenerateSvg_WithValidSkuAndCaption_IncludesCaption()
    {
        var result = _sut.GenerateSvg("SKU-001", "Test Product");

        result.Should().Contain("Test Product");
        result.Should().Contain("<text");
    }

    [Fact]
    public async Task GenerateSvg_WithEmptySku_ThrowsException()
    {
        var act = () => _sut.GenerateSvg("");

        await Task.FromResult(act.Should().Throw<ArgumentException>());
    }

    [Fact]
    public async Task GenerateSvg_WithWhitespaceSku_ThrowsException()
    {
        var act = () => _sut.GenerateSvg("   ");

        await Task.FromResult(act.Should().Throw<ArgumentException>());
    }

    [Fact]
    public void GeneratePdf_WithValidProducts_ReturnsPdfBytes()
    {
        var products = new[] { ("SKU-001", "Product 1"), ("SKU-002", "Product 2") };

        var result = _sut.GeneratePdf(products);

        result.Should().NotBeNull();
        result.Should().HaveCountGreaterThan(0);
        result[0].Should().Be(0x25); // PDF magic byte '%'
        result[1].Should().Be(0x50); // 'P'
        result[2].Should().Be(0x44); // 'D'
        result[3].Should().Be(0x46); // 'F'
    }

    [Fact]
    public void GeneratePdf_WithEmptyList_ReturnsEmptyPdf()
    {
        var products = Array.Empty<(string, string)>();

        var result = _sut.GeneratePdf(products);

        result.Should().NotBeNull();
    }
}
