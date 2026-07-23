using System.Xml.Linq;
using PdfSharpCore;
using PdfSharpCore.Pdf;
using PdfSharpCore.Drawing;
using QRCoder;

namespace JoiabagurPV.Application.Services;

public class QrCodeService : Interfaces.IQrCodeService
{
    public string GenerateSvg(string sku, string? caption = null)
    {
        if (string.IsNullOrWhiteSpace(sku))
            throw new ArgumentException("SKU cannot be empty", nameof(sku));

        using var generator = new QRCodeGenerator();
        var qrData = generator.CreateQrCode(sku, QRCodeGenerator.ECCLevel.Q);
        var svg = new SvgQRCode(qrData);
        var svgContent = svg.GetGraphic(20);

        if (!string.IsNullOrEmpty(caption))
        {
            var doc = XDocument.Parse(svgContent);
            var svgElement = doc.Root!;
            var ns = svgElement.GetDefaultNamespace();

            svgElement.Add(new XElement(ns + "text",
                new XAttribute("x", "50%"),
                new XAttribute("y", "100%"),
                new XAttribute("text-anchor", "middle"),
                new XAttribute("font-family", "Arial, sans-serif"),
                new XAttribute("font-size", "14"),
                new XAttribute("fill", "#000"),
                caption
            ));

            svgContent = doc.ToString(SaveOptions.DisableFormatting);
        }

        return svgContent;
    }

    public byte[] GeneratePdf(IEnumerable<(string Sku, string Name)> products)
    {
        using var document = new PdfDocument();
        const int labelsPerPage = 24;
        const int cols = 4;
        const int rows = 6;

        var items = products.ToList();
        var pageIndex = 0;

        while (pageIndex * labelsPerPage < items.Count)
        {
            var page = document.AddPage();
            page.Size = PageSize.A4;
            page.Orientation = PageOrientation.Portrait;

            using var gfx = XGraphics.FromPdfPage(page);
            var pageItems = items.Skip(pageIndex * labelsPerPage).Take(labelsPerPage).ToList();

            var cellW = page.Width / cols;
            var cellH = page.Height / rows;
            var qrSize = Math.Min(cellW, cellH) * 0.6;

            for (var i = 0; i < pageItems.Count; i++)
            {
                var col = i % cols;
                var row = i / cols;
                var x = col * cellW + (cellW - qrSize) / 2;
                var y = row * cellH + 10;

                var (sku, name) = pageItems[i];

                using var generator = new QRCodeGenerator();
                var qrData = generator.CreateQrCode(sku, QRCodeGenerator.ECCLevel.Q);
                using var png = new PngByteQRCode(qrData);
                var pngBytes = png.GetGraphic(20);

                using var ms = new MemoryStream(pngBytes);
                var img = XImage.FromStream(ms);

                gfx.DrawImage(img, x, y, qrSize, qrSize);

                var font = new XFont("Arial", 8);
                gfx.DrawString(sku, font, XBrushes.Black,
                    new XRect(x, y + qrSize + 2, cellW, 14),
                    XStringFormats.TopCenter);
                gfx.DrawString(name, font, XBrushes.Black,
                    new XRect(x, y + qrSize + 14, cellW, 14),
                    XStringFormats.TopCenter);
            }

            pageIndex++;
        }

        using var outStream = new MemoryStream();
        document.Save(outStream);
        return outStream.ToArray();
    }
}
