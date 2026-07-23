namespace JoiabagurPV.Application.Interfaces;

public interface IQrCodeService
{
    string GenerateSvg(string sku, string? caption = null);
    byte[] GeneratePdf(IEnumerable<(string Sku, string Name)> products);
}
