using JoiabagurPV.Application.Commission;
using JoiabagurPV.Application.DTOs.Sales;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Interfaces.Repositories;

namespace JoiabagurPV.Application.Services;

public class PosCommissionReportService : IPosCommissionReportService
{
    private readonly ISaleRepository _saleRepository;
    private readonly IReturnRepository _returnRepository;
    private readonly IPointOfSaleCommissionTierRepository _tierRepository;

    public PosCommissionReportService(
        ISaleRepository saleRepository,
        IReturnRepository returnRepository,
        IPointOfSaleCommissionTierRepository tierRepository)
    {
        _saleRepository = saleRepository;
        _returnRepository = returnRepository;
        _tierRepository = tierRepository;
    }

    public async Task<SalesReportCommissionResult> ComputeReportCommissionsAsync(
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
        bool? priceWasOverridden)
    {
        var saleLines = await _saleRepository.GetSaleLinesForCommissionReportAsync(
            authorizedPosIds, startDate, endDate, pointOfSaleId, productId, userId,
            paymentMethodId, search, amountMin, amountMax, hasPhoto, priceWasOverridden);

        var salesGross = saleLines.Sum(l => l.Amount);
        var returnsTotal = await _returnRepository.GetReturnAmountTotalInWindowAsync(
            authorizedPosIds, startDate, endDate, pointOfSaleId);

        var commissionBySale = await BuildCommissionMapForSalesAsync(saleLines);
        var totalCommission = saleLines.Sum(l => commissionBySale.GetValueOrDefault(l.SaleId, 0m));

        var result = new SalesReportCommissionResult
        {
            ReturnAdjustedGross = salesGross - returnsTotal,
            TotalCommission = totalCommission
        };

        var posIds = saleLines.Select(l => l.PointOfSaleId).Distinct().ToList();
        if (posIds.Count > 1)
        {
            var returnsByPos = await GetReturnTotalsByPosAsync(authorizedPosIds, startDate, endDate, pointOfSaleId, posIds);

            result.AggregatesByPointOfSale = posIds.Select(posId =>
            {
                var posSales = saleLines.Where(l => l.PointOfSaleId == posId).ToList();
                var posGross = posSales.Sum(l => l.Amount);
                var posReturns = returnsByPos.GetValueOrDefault(posId, 0m);
                var posCommission = posSales.Sum(l => commissionBySale.GetValueOrDefault(l.SaleId, 0m));
                return new SalesReportPosAggregateDto
                {
                    PointOfSaleId = posId,
                    TotalAmount = posGross - posReturns,
                    TotalCommission = posCommission,
                    TotalAmountNet = posGross - posReturns - posCommission
                };
            }).ToList();
        }

        return result;
    }

    public async Task<decimal> ComputeCommissionForSalesAsync(
        IEnumerable<SaleCommissionLine> sales,
        CancellationToken cancellationToken = default)
    {
        var lines = sales.Select(s => new Domain.Commission.SaleReportLine(
            s.SaleId, s.PointOfSaleId, s.SaleDateUtc, s.Amount)).ToList();

        var map = await BuildCommissionMapForSalesAsync(lines, cancellationToken);
        return lines.Sum(l => map.GetValueOrDefault(l.SaleId, 0m));
    }

    private async Task<Dictionary<Guid, decimal>> BuildCommissionMapForSalesAsync(
        List<Domain.Commission.SaleReportLine> saleLines,
        CancellationToken cancellationToken = default)
    {
        if (saleLines.Count == 0)
            return new Dictionary<Guid, decimal>();

        var posIds = saleLines.Select(l => l.PointOfSaleId).Distinct().ToList();
        var tierEntities = await _tierRepository.GetByPointOfSaleIdsAsync(posIds);
        var tiersByPos = tierEntities
            .GroupBy(t => t.PointOfSaleId)
            .ToDictionary(
                g => g.Key,
                g => (IReadOnlyList<CommissionTierBracket>)g
                    .OrderBy(t => t.MinAmountInclusive)
                    .Select(t => new CommissionTierBracket(t.MinAmountInclusive, t.MaxAmountInclusive, t.CommissionPercent))
                    .ToList());

        var years = saleLines
            .Select(l => l.SaleDateUtc.Year)
            .Distinct()
            .ToList();

        var commissionBySale = new Dictionary<Guid, decimal>();

        foreach (var posId in posIds)
        {
            var tiers = tiersByPos.GetValueOrDefault(posId, Array.Empty<CommissionTierBracket>());
            foreach (var year in years)
            {
                var yearStart = new DateTime(year, 1, 1, 0, 0, 0, DateTimeKind.Utc);
                var yearEnd = new DateTime(year, 12, 31, 23, 59, 59, DateTimeKind.Utc);

                var salesEvents = await _saleRepository.GetSaleYtdEventsForPosYearAsync(posId, yearStart, yearEnd);
                var returnEvents = await _returnRepository.GetReturnYtdEventsForPosYearAsync(posId, yearStart, yearEnd);

                var timeline = new List<CommissionTimelineEvent>();
                timeline.AddRange(salesEvents.Select(e => new CommissionTimelineEvent(
                    CommissionTimelineEventKind.Sale,
                    e.SaleDateUtc,
                    e.CreatedAtUtc,
                    e.SaleId,
                    e.Amount)));
                timeline.AddRange(returnEvents.Select(e => new CommissionTimelineEvent(
                    CommissionTimelineEventKind.Return,
                    e.ReturnDateUtc,
                    e.CreatedAtUtc,
                    null,
                    e.Amount)));

                var yearMap = PosCommissionCalculator.BuildSaleCommissionMap(timeline, tiers);
                foreach (var (saleId, commission) in yearMap)
                {
                    if (saleLines.Any(l => l.SaleId == saleId))
                        commissionBySale[saleId] = commission;
                }
            }
        }

        return commissionBySale;
    }

    private async Task<Dictionary<Guid, decimal>> GetReturnTotalsByPosAsync(
        IEnumerable<Guid>? authorizedPosIds,
        DateTime? startDate,
        DateTime? endDate,
        Guid? pointOfSaleId,
        List<Guid> posIdsInReport)
    {
        var result = new Dictionary<Guid, decimal>();
        foreach (var posId in posIdsInReport)
        {
            var total = await _returnRepository.GetReturnAmountTotalInWindowAsync(
                authorizedPosIds, startDate, endDate, posId);
            result[posId] = total;
        }

        return result;
    }
}
