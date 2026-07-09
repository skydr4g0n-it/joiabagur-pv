using JoiabagurPV.Application.DTOs.Inventory;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Interfaces.Repositories;

namespace JoiabagurPV.Application.Services;

public class InventoryMovementReportService : IInventoryMovementReportService
{
    private readonly IInventoryMovementRepository _movementRepository;
    private const int ExportLimit = 50_000;

    public InventoryMovementReportService(IInventoryMovementRepository movementRepository)
    {
        _movementRepository = movementRepository;
    }

    public async Task<InventoryMovementReportResponse> GetReportAsync(InventoryMovementReportFilterRequest request)
    {
        if (IsDetail(request))
        {
            var (detailItems, detailTotalCount) = await _movementRepository.GetMovementDetailRowsAsync(
                request.StartDate!.Value,
                request.EndDate!.Value,
                request.PointOfSaleId,
                request.ProductSearch,
                request.Page,
                request.PageSize);

            return new InventoryMovementReportResponse
            {
                Items = detailItems.Select(ToDetailRow).Cast<object>().ToList(),
                TotalCount = detailTotalCount,
                Page = request.Page,
                PageSize = request.PageSize,
                TotalPages = (int)Math.Ceiling(detailTotalCount / (double)request.PageSize)
            };
        }

        var allItems = await _movementRepository.GetMovementSummaryByProductAsync(
            request.StartDate!.Value,
            request.EndDate!.Value,
            request.PointOfSaleId,
            request.ProductSearch);

        var sorted = ApplySorting(allItems, request.SortBy, request.SortDirection);

        var totalCount = sorted.Count;
        var totalPages = (int)Math.Ceiling(totalCount / (double)request.PageSize);

        var page = sorted
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .ToList();

        return new InventoryMovementReportResponse
        {
            Items = page.Select(ToSummaryRow).Cast<object>().ToList(),
            TotalCount = totalCount,
            Page = request.Page,
            PageSize = request.PageSize,
            TotalPages = totalPages
        };
    }

    public async Task<(MemoryStream Stream, int TotalCount)> ExportReportAsync(InventoryMovementReportFilterRequest request)
    {
        if (IsDetail(request))
        {
            var (detailItems, detailTotalCount) = await _movementRepository.GetMovementDetailRowsAsync(
                request.StartDate!.Value,
                request.EndDate!.Value,
                request.PointOfSaleId,
                request.ProductSearch);

            if (detailTotalCount > ExportLimit)
            {
                throw new InvalidOperationException($"EXPORT_LIMIT_EXCEEDED:{detailTotalCount}");
            }

            var detailStream = GenerateDetailExcel(detailItems.Take(ExportLimit).ToList());
            return (detailStream, detailTotalCount);
        }

        var allItems = await _movementRepository.GetMovementSummaryByProductAsync(
            request.StartDate!.Value,
            request.EndDate!.Value,
            request.PointOfSaleId,
            request.ProductSearch);

        var totalCount = allItems.Count;

        if (totalCount > ExportLimit)
        {
            throw new InvalidOperationException($"EXPORT_LIMIT_EXCEEDED:{totalCount}");
        }

        var sorted = ApplySorting(allItems, request.SortBy, request.SortDirection);

        var items = sorted.Take(ExportLimit).ToList();

        var stream = GenerateSummaryExcel(items);
        return (stream, totalCount);
    }

    private static bool IsDetail(InventoryMovementReportFilterRequest request)
    {
        return string.Equals(request.OutputModel, "detail", StringComparison.OrdinalIgnoreCase);
    }

    private static InventoryMovementSummaryRow ToSummaryRow(MovementSummaryProjection p)
    {
        return new InventoryMovementSummaryRow
        {
            ProductId = p.ProductId,
            ProductName = p.ProductName,
            ProductSku = p.ProductSku,
            Additions = p.Additions,
            Subtractions = p.Subtractions,
            Difference = p.Difference
        };
    }

    private static InventoryMovementDetailRow ToDetailRow(MovementDetailProjection p)
    {
        return new InventoryMovementDetailRow
        {
            Id = p.Id,
            InventoryId = p.InventoryId,
            ProductId = p.ProductId,
            ProductName = p.ProductName,
            ProductSku = p.ProductSku,
            PointOfSaleId = p.PointOfSaleId,
            PointOfSaleName = p.PointOfSaleName,
            MovementType = p.MovementType,
            QuantityChange = p.QuantityChange,
            QuantityBefore = p.QuantityBefore,
            QuantityAfter = p.QuantityAfter,
            UserId = p.UserId,
            UserName = p.UserName,
            Reason = p.Reason,
            MovementDate = p.MovementDate,
            SaleId = p.SaleId,
            ReturnId = p.ReturnId
        };
    }

    private static List<MovementSummaryProjection> ApplySorting(
        List<MovementSummaryProjection> items,
        string? sortBy,
        string? sortDirection)
    {
        var desc = string.Equals(sortDirection, "desc", StringComparison.OrdinalIgnoreCase);

        IEnumerable<MovementSummaryProjection> sorted = sortBy?.ToLowerInvariant() switch
        {
            "additions" => desc ? items.OrderByDescending(r => r.Additions) : items.OrderBy(r => r.Additions),
            "subtractions" => desc ? items.OrderByDescending(r => r.Subtractions) : items.OrderBy(r => r.Subtractions),
            "difference" => desc ? items.OrderByDescending(r => r.Difference) : items.OrderBy(r => r.Difference),
            _ => desc ? items.OrderByDescending(r => r.ProductName) : items.OrderBy(r => r.ProductName),
        };

        return sorted.ToList();
    }

    private static MemoryStream GenerateSummaryExcel(List<MovementSummaryProjection> items)
    {
        using var workbook = new ClosedXML.Excel.XLWorkbook();
        var ws = workbook.Worksheets.Add("Resumen movimientos");

        var headers = new[] { "Producto", "SKU", "Adiciones", "Sustracciones", "Diferencia" };
        for (var c = 0; c < headers.Length; c++)
            ws.Cell(1, c + 1).Value = headers[c];

        var headerRange = ws.Range(1, 1, 1, headers.Length);
        headerRange.Style.Font.Bold = true;
        headerRange.Style.Fill.BackgroundColor = ClosedXML.Excel.XLColor.LightGray;

        for (var i = 0; i < items.Count; i++)
        {
            var row = i + 2;
            var item = items[i];
            ws.Cell(row, 1).Value = item.ProductName;
            ws.Cell(row, 2).Value = item.ProductSku;
            ws.Cell(row, 3).Value = item.Additions;
            ws.Cell(row, 4).Value = item.Subtractions;
            ws.Cell(row, 5).Value = item.Difference;
        }

        ws.Columns(3, 5).Style.NumberFormat.Format = "#,##0";
        ws.Columns().AdjustToContents();

        var ms = new MemoryStream();
        workbook.SaveAs(ms);
        ms.Position = 0;
        return ms;
    }

    private static MemoryStream GenerateDetailExcel(List<MovementDetailProjection> items)
    {
        using var workbook = new ClosedXML.Excel.XLWorkbook();
        var ws = workbook.Worksheets.Add("Detalle movimientos");

        var headers = new[]
        {
            "Fecha",
            "Tipo",
            "Producto",
            "SKU",
            "Punto de Venta",
            "Cambio",
            "Antes",
            "Después",
            "Usuario",
            "Motivo",
            "Venta",
            "Devolución"
        };
        for (var c = 0; c < headers.Length; c++)
            ws.Cell(1, c + 1).Value = headers[c];

        var headerRange = ws.Range(1, 1, 1, headers.Length);
        headerRange.Style.Font.Bold = true;
        headerRange.Style.Fill.BackgroundColor = ClosedXML.Excel.XLColor.LightGray;

        for (var i = 0; i < items.Count; i++)
        {
            var row = i + 2;
            var item = items[i];
            ws.Cell(row, 1).Value = item.MovementDate;
            ws.Cell(row, 2).Value = item.MovementType.ToString();
            ws.Cell(row, 3).Value = item.ProductName;
            ws.Cell(row, 4).Value = item.ProductSku;
            ws.Cell(row, 5).Value = item.PointOfSaleName;
            ws.Cell(row, 6).Value = item.QuantityChange;
            ws.Cell(row, 7).Value = item.QuantityBefore;
            ws.Cell(row, 8).Value = item.QuantityAfter;
            ws.Cell(row, 9).Value = item.UserName;
            ws.Cell(row, 10).Value = item.Reason;
            ws.Cell(row, 11).Value = item.SaleId?.ToString();
            ws.Cell(row, 12).Value = item.ReturnId?.ToString();
        }

        ws.Column(1).Style.DateFormat.Format = "yyyy-mm-dd hh:mm";
        ws.Columns(6, 8).Style.NumberFormat.Format = "#,##0";
        ws.Columns().AdjustToContents();

        var ms = new MemoryStream();
        workbook.SaveAs(ms);
        ms.Position = 0;
        return ms;
    }
}
