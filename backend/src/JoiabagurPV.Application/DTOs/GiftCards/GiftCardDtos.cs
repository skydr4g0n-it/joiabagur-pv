namespace JoiabagurPV.Application.DTOs.GiftCards;

public class IssueGiftCardRequest
{
    public Guid PointOfSaleId { get; set; }
    public decimal NominalAmount { get; set; }
    public DateOnly ExpiryDate { get; set; }
    public string? HolderName { get; set; }
    public Guid PaymentMethodId { get; set; }
}

public class IssueGiftCardResult
{
    public bool Success { get; set; }
    public string? ErrorMessage { get; set; }
    public bool IsForbidden { get; set; }
    public GiftCardDetailDto? Card { get; set; }
}

public class GiftCardListItemDto
{
    public Guid Id { get; set; }
    public string Code { get; set; } = string.Empty;
    public Guid PointOfSaleId { get; set; }
    public string PointOfSaleName { get; set; } = string.Empty;
    public string? HolderName { get; set; }
    public decimal NominalAmount { get; set; }
    public decimal SpendableBalance { get; set; }
    public decimal AccountedRemainder { get; set; }
    public DateOnly ExpiryDate { get; set; }
    public DateTime CreatedAt { get; set; }
}

public class GiftCardListResponse
{
    public List<GiftCardListItemDto> Items { get; set; } = new();
    public int TotalCount { get; set; }
    public int Page { get; set; }
    public int PageSize { get; set; }
    public int TotalPages { get; set; }
}

public class GiftCardCoverageLinkDto
{
    public Guid SaleId { get; set; }
    public string ProductSku { get; set; } = string.Empty;
    public string ProductName { get; set; } = string.Empty;
    public decimal CoverageAmount { get; set; }
    public DateTime SaleDate { get; set; }
}

public class GiftCardOperationDto
{
    public string Type { get; set; } = string.Empty;
    public DateTime OccurredAt { get; set; }
    public string? Detail { get; set; }
}

public class GiftCardDetailDto
{
    public Guid Id { get; set; }
    public string Code { get; set; } = string.Empty;
    public Guid PointOfSaleId { get; set; }
    public string PointOfSaleName { get; set; } = string.Empty;
    public Guid IssuanceSalePointOfSaleId { get; set; }
    public string IssuanceSalePointOfSaleName { get; set; } = string.Empty;
    public string? HolderName { get; set; }
    public decimal NominalAmount { get; set; }
    public decimal SpendableBalance { get; set; }
    public decimal AccountedRemainder { get; set; }
    public DateOnly ExpiryDate { get; set; }
    public Guid IssuanceSaleId { get; set; }
    public DateTime IssuanceSaleDate { get; set; }
    public List<GiftCardCoverageLinkDto> LinkedProducts { get; set; } = new();
    public List<GiftCardOperationDto> Operations { get; set; } = new();
}

public class GiftCardByCodeDto
{
    public Guid Id { get; set; }
    public string Code { get; set; } = string.Empty;
    public decimal NominalAmount { get; set; }
    public decimal SpendableBalance { get; set; }
    public DateOnly ExpiryDate { get; set; }
    public Guid PointOfSaleId { get; set; }
}

public class ReassignGiftCardRequest
{
    public Guid ToPointOfSaleId { get; set; }
}

public class ReassignGiftCardResult
{
    public bool Success { get; set; }
    public string? ErrorMessage { get; set; }
    public bool IsForbidden { get; set; }
    public GiftCardDetailDto? Card { get; set; }
}

public class GiftCardExchangeLineRequest
{
    public Guid SaleId { get; set; }
    public int Quantity { get; set; }
}

public class GiftCardExchangeNewProductRequest
{
    public Guid ProductId { get; set; }
    public int Quantity { get; set; }
}

public class ExchangeGiftCardRequest
{
    public Guid PointOfSaleId { get; set; }
    public Domain.Enums.ReturnCategory ReturnCategory { get; set; }
    public string? Reason { get; set; }
    public Guid PaymentMethodId { get; set; }
    public List<GiftCardExchangeLineRequest> ReturnLines { get; set; } = new();
    public List<GiftCardExchangeNewProductRequest> NewProducts { get; set; } = new();
}

public class ExchangeGiftCardResult
{
    public bool Success { get; set; }
    public string? ErrorMessage { get; set; }
    public decimal CashDue { get; set; }
    public List<Guid> NewSaleIds { get; set; } = new();
    public List<Guid> ReturnIds { get; set; } = new();
}
