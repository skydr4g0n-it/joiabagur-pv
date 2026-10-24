using JoiabagurPV.Application.DTOs.Sales;

namespace JoiabagurPV.Application.Interfaces;

public interface IPosCommissionReportService
{
    Task<SalesReportCommissionResult> ComputeReportCommissionsAsync(
        IEnumerable<Guid>? authorizedPosIds,
        DateTime? startDate,
        DateTime? endDate,
        Guid? pointOfSaleId,
        Guid? productId,
        Guid? userId,
        Guid? paymentMethodId,
        string? search,
        decimal? amountMin,
        decimal? amountMax,
        bool? hasPhoto,
        bool? priceWasOverridden);

    Task<decimal> ComputeCommissionForSalesAsync(
        IEnumerable<SaleCommissionLine> sales,
        CancellationToken cancellationToken = default);
}

public sealed record SaleCommissionLine(Guid SaleId, Guid PointOfSaleId, DateTime SaleDateUtc, decimal Amount);

public class SalesReportCommissionResult
{
    public decimal ReturnAdjustedGross { get; set; }
    public decimal TotalCommission { get; set; }
    public decimal TotalAmountNet => ReturnAdjustedGross - TotalCommission;
    public List<SalesReportPosAggregateDto> AggregatesByPointOfSale { get; set; } = new();
}
