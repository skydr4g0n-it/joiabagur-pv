namespace JoiabagurPV.Domain.Commission;

public sealed record SaleYtdEvent(Guid SaleId, DateTime SaleDateUtc, DateTime CreatedAtUtc, decimal Amount);

public sealed record ReturnYtdEvent(Guid ReturnId, DateTime ReturnDateUtc, DateTime CreatedAtUtc, decimal Amount);

public sealed record SaleReportLine(Guid SaleId, Guid PointOfSaleId, DateTime SaleDateUtc, decimal Amount);
