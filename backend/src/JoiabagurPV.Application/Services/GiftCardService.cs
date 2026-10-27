using JoiabagurPV.Application.DTOs.GiftCards;
using JoiabagurPV.Application.GiftCards;
using JoiabagurPV.Domain.GiftCards;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Common;
using JoiabagurPV.Domain.Constants;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using JoiabagurPV.Domain.Interfaces.Services;
using Microsoft.EntityFrameworkCore;

namespace JoiabagurPV.Application.Services;

public class GiftCardService : IGiftCardService
{
    private readonly IGiftCardRepository _giftCardRepository;
    private readonly ISaleRepository _saleRepository;
    private readonly IProductRepository _productRepository;
    private readonly IPointOfSaleRepository _pointOfSaleRepository;
    private readonly IUserPointOfSaleRepository _userPointOfSaleRepository;
    private readonly IPaymentMethodValidationService _paymentMethodValidationService;
    private readonly IReturnRepository _returnRepository;
    private readonly IReturnSaleRepository _returnSaleRepository;
    private readonly IInventoryService _inventoryService;
    private readonly IStockValidationService _stockValidationService;
    private readonly IUnitOfWork _unitOfWork;
    private readonly IDashboardService _dashboardService;
    private readonly GiftCardCodeGenerator _codeGenerator;

    private const int ExchangeWindowDays = 30;

    public GiftCardService(
        IGiftCardRepository giftCardRepository,
        ISaleRepository saleRepository,
        IProductRepository productRepository,
        IPointOfSaleRepository pointOfSaleRepository,
        IUserPointOfSaleRepository userPointOfSaleRepository,
        IPaymentMethodValidationService paymentMethodValidationService,
        IReturnRepository returnRepository,
        IReturnSaleRepository returnSaleRepository,
        IInventoryService inventoryService,
        IStockValidationService stockValidationService,
        IUnitOfWork unitOfWork,
        IDashboardService dashboardService,
        GiftCardCodeGenerator codeGenerator)
    {
        _giftCardRepository = giftCardRepository;
        _saleRepository = saleRepository;
        _productRepository = productRepository;
        _pointOfSaleRepository = pointOfSaleRepository;
        _userPointOfSaleRepository = userPointOfSaleRepository;
        _paymentMethodValidationService = paymentMethodValidationService;
        _returnRepository = returnRepository;
        _returnSaleRepository = returnSaleRepository;
        _inventoryService = inventoryService;
        _stockValidationService = stockValidationService;
        _unitOfWork = unitOfWork;
        _dashboardService = dashboardService;
        _codeGenerator = codeGenerator;
    }

    public async Task<IssueGiftCardResult> IssueAsync(
        IssueGiftCardRequest request,
        Guid userId,
        bool isAdmin,
        string? idempotencyKey)
    {
        if (!string.IsNullOrWhiteSpace(idempotencyKey))
        {
            var existing = await _giftCardRepository.GetByIssuanceIdempotencyKeyAsync(idempotencyKey);
            if (existing != null)
            {
                var detail = await MapDetailAsync(existing);
                return new IssueGiftCardResult { Success = true, Card = detail };
            }
        }

        if (!isAdmin)
        {
            var assigned = await _userPointOfSaleRepository.GetAll()
                .AnyAsync(u => u.UserId == userId && u.PointOfSaleId == request.PointOfSaleId && u.IsActive);
            if (!assigned)
                return new IssueGiftCardResult { Success = false, IsForbidden = true, ErrorMessage = "El operador no está asignado a este punto de venta." };
        }

        var pos = await _pointOfSaleRepository.GetByIdAsync(request.PointOfSaleId);
        if (pos == null)
            return new IssueGiftCardResult { Success = false, ErrorMessage = "Punto de venta no encontrado." };

        try
        {
            await _paymentMethodValidationService.ValidatePaymentMethodAsync(request.PaymentMethodId, request.PointOfSaleId);
        }
        catch (InvalidOperationException ex)
        {
            return new IssueGiftCardResult { Success = false, ErrorMessage = ex.Message };
        }

        var systemProduct = await _productRepository.GetAll()
            .FirstOrDefaultAsync(p => p.SystemProductKind == SystemProductKind.GiftCard);
        if (systemProduct == null)
            return new IssueGiftCardResult { Success = false, ErrorMessage = "El producto de sistema de tarjeta regalo no está configurado." };

        await _unitOfWork.BeginTransactionAsync();
        try
        {
            var sale = new Sale
            {
                ProductId = systemProduct.Id,
                PointOfSaleId = request.PointOfSaleId,
                UserId = userId,
                PaymentMethodId = request.PaymentMethodId,
                Price = request.NominalAmount,
                Quantity = 1,
                PriceWasOverridden = false,
                SaleDate = DateTime.UtcNow
            };
            sale = await _saleRepository.AddAsync(sale);
            await _unitOfWork.SaveChangesAsync();

            string code;
            GiftCard? card = null;
            for (var attempt = 0; attempt < 10; attempt++)
            {
                code = _codeGenerator.GenerateCode();
                if (await _giftCardRepository.GetByCodeAsync(code) != null)
                    continue;

                card = new GiftCard
                {
                    Code = code,
                    PointOfSaleId = request.PointOfSaleId,
                    HolderName = request.HolderName,
                    NominalAmount = request.NominalAmount,
                    SpendableBalance = request.NominalAmount,
                    ExpiryDate = request.ExpiryDate,
                    IssuanceSaleId = sale.Id,
                    IssuedByUserId = userId,
                    IssuanceIdempotencyKey = string.IsNullOrWhiteSpace(idempotencyKey) ? null : idempotencyKey
                };
                card = await _giftCardRepository.AddAsync(card);
                await _unitOfWork.SaveChangesAsync();
                break;
            }

            if (card == null)
            {
                await _unitOfWork.RollbackTransactionAsync();
                return new IssueGiftCardResult { Success = false, ErrorMessage = "No se pudo generar un código único de tarjeta regalo." };
            }

            await _unitOfWork.CommitTransactionAsync();
            _dashboardService.InvalidateDashboardCache();

            var loaded = await _giftCardRepository.GetByIdWithDetailsAsync(card.Id);
            return new IssueGiftCardResult { Success = true, Card = await MapDetailAsync(loaded!) };
        }
        catch
        {
            await _unitOfWork.RollbackTransactionAsync();
            throw;
        }
    }

    public async Task<GiftCardListResponse> ListAsync(int page, int pageSize, Guid userId, bool isAdmin)
    {
        page = Math.Max(1, page);
        pageSize = Math.Min(Math.Max(1, pageSize), PaginationConstants.MaxPageSize);
        var skip = (page - 1) * pageSize;

        IEnumerable<Guid>? posFilter = null;
        if (!isAdmin)
        {
            posFilter = await _userPointOfSaleRepository.GetAll()
                .Where(u => u.UserId == userId && u.IsActive)
                .Select(u => u.PointOfSaleId)
                .ToListAsync();
        }

        var (items, total) = await _giftCardRepository.ListAsync(posFilter, skip, pageSize);
        var dtoItems = new List<GiftCardListItemDto>();
        foreach (var card in items)
        {
            dtoItems.Add(await MapListItemAsync(card));
        }

        var totalPages = (int)Math.Ceiling(total / (double)pageSize);
        return new GiftCardListResponse
        {
            Items = dtoItems,
            TotalCount = total,
            Page = page,
            PageSize = pageSize,
            TotalPages = totalPages
        };
    }

    public async Task<GiftCardDetailDto?> GetDetailAsync(Guid id, Guid userId, bool isAdmin)
    {
        var card = await _giftCardRepository.GetByIdWithDetailsAsync(id);
        if (card == null)
            return null;

        if (!isAdmin)
        {
            var assigned = await _userPointOfSaleRepository.GetAll()
                .AnyAsync(u => u.UserId == userId && u.PointOfSaleId == card.PointOfSaleId && u.IsActive);
            if (!assigned)
                return null;
        }

        return await MapDetailAsync(card);
    }

    public async Task<(GiftCardByCodeDto? Card, string? ErrorMessage)> GetByCodeForPosAsync(string code, Guid pointOfSaleId)
    {
        var card = await _giftCardRepository.GetByCodeAsync(code);
        if (card == null)
            return (null, "Tarjeta regalo no encontrada.");

        if (card.PointOfSaleId != pointOfSaleId)
            return (null, "La tarjeta regalo no es válida en este punto de venta.");

        if (GiftCardEconomics.IsExpiredForRedemption(card.ExpiryDate))
            return (null, "La tarjeta regalo está caducada.");

        if (card.SpendableBalance <= 0)
            return (null, "La tarjeta regalo ya se ha utilizado.");

        return (new GiftCardByCodeDto
        {
            Id = card.Id,
            Code = card.Code,
            NominalAmount = card.NominalAmount,
            SpendableBalance = card.SpendableBalance,
            ExpiryDate = card.ExpiryDate,
            PointOfSaleId = card.PointOfSaleId
        }, null);
    }

    public async Task<ReassignGiftCardResult> ReassignAsync(
        Guid giftCardId,
        ReassignGiftCardRequest request,
        Guid userId,
        bool isAdmin)
    {
        if (!isAdmin)
            return new ReassignGiftCardResult { Success = false, IsForbidden = true, ErrorMessage = "Solo los administradores pueden reasignar tarjetas regalo." };

        var card = await _giftCardRepository.GetByIdWithDetailsAsync(giftCardId);
        if (card == null)
            return new ReassignGiftCardResult { Success = false, ErrorMessage = "Tarjeta regalo no encontrada." };

        if (card.PointOfSaleId == request.ToPointOfSaleId)
            return new ReassignGiftCardResult { Success = true, Card = await MapDetailAsync(card) };

        var targetPos = await _pointOfSaleRepository.GetByIdAsync(request.ToPointOfSaleId);
        if (targetPos == null)
            return new ReassignGiftCardResult { Success = false, ErrorMessage = "El punto de venta de destino no existe." };

        var fromPosId = card.PointOfSaleId;
        card.PointOfSaleId = request.ToPointOfSaleId;
        await _giftCardRepository.UpdateAsync(card);

        await _giftCardRepository.AddReassignmentAsync(new GiftCardReassignment
        {
            GiftCardId = card.Id,
            FromPointOfSaleId = fromPosId,
            ToPointOfSaleId = request.ToPointOfSaleId,
            UserId = userId,
            OccurredAt = DateTime.UtcNow
        });
        await _unitOfWork.SaveChangesAsync();

        var reloaded = await _giftCardRepository.GetByIdWithDetailsAsync(card.Id);
        return new ReassignGiftCardResult { Success = true, Card = await MapDetailAsync(reloaded!) };
    }

    public async Task<ExchangeGiftCardResult> ExchangeAsync(
        Guid giftCardId,
        ExchangeGiftCardRequest request,
        Guid userId,
        bool isAdmin,
        string? idempotencyKey)
    {
        if (!string.IsNullOrWhiteSpace(idempotencyKey))
        {
            var previous = await _giftCardRepository.GetExchangeByIdempotencyKeyAsync(giftCardId, idempotencyKey);
            if (previous != null)
                return MapExchangeOperationResult(previous);
        }

        if (!isAdmin)
        {
            var assigned = await _userPointOfSaleRepository.GetAll()
                .AnyAsync(u => u.UserId == userId && u.PointOfSaleId == request.PointOfSaleId && u.IsActive);
            if (!assigned)
                return new ExchangeGiftCardResult { Success = false, ErrorMessage = "El operador no está asignado a este punto de venta." };
        }

        var card = await _giftCardRepository.GetByIdWithDetailsAsync(giftCardId);
        if (card == null)
            return new ExchangeGiftCardResult { Success = false, ErrorMessage = "Tarjeta regalo no encontrada." };

        if (card.PointOfSaleId != request.PointOfSaleId)
            return new ExchangeGiftCardResult { Success = false, ErrorMessage = "La tarjeta regalo no es válida en este punto de venta." };

        try
        {
            await _paymentMethodValidationService.ValidatePaymentMethodAsync(request.PaymentMethodId, request.PointOfSaleId);
        }
        catch (InvalidOperationException ex)
        {
            return new ExchangeGiftCardResult { Success = false, ErrorMessage = ex.Message };
        }

        var cutoff = DateTime.UtcNow.AddDays(-ExchangeWindowDays);
        var returnSales = new List<(Sale Sale, int Quantity)>();
        foreach (var line in request.ReturnLines)
        {
            var sale = await _saleRepository.GetByIdWithDetailsAsync(line.SaleId);
            if (sale == null)
                return new ExchangeGiftCardResult { Success = false, ErrorMessage = $"Venta {line.SaleId} no encontrada." };

            if (sale.PointOfSaleId != request.PointOfSaleId)
                return new ExchangeGiftCardResult { Success = false, ErrorMessage = "La venta no corresponde a este punto de venta." };

            if (sale.SaleDate < cutoff)
                return new ExchangeGiftCardResult { Success = false, ErrorMessage = "La venta está fuera del plazo de cambio de 30 días." };

            var hasApply = card.CoverageEntries.Any(e =>
                e.SaleId == sale.Id && e.EntryType == GiftCardCoverageEntryType.Apply);
            if (!hasApply)
                return new ExchangeGiftCardResult { Success = false, ErrorMessage = "La venta no está vinculada a esta tarjeta regalo." };

            var returned = await _returnSaleRepository.GetReturnedQuantityForSaleAsync(sale.Id);
            var available = sale.Quantity - returned;
            if (line.Quantity > available)
                return new ExchangeGiftCardResult { Success = false, ErrorMessage = "La cantidad a devolver supera la cantidad disponible." };

            returnSales.Add((sale, line.Quantity));
        }

        var newProducts = new List<(Product Product, int Quantity)>();
        foreach (var np in request.NewProducts)
        {
            var product = await _productRepository.GetByIdAsync(np.ProductId);
            if (product == null || !product.IsActive || product.SystemProductKind != null)
                return new ExchangeGiftCardResult { Success = false, ErrorMessage = "El producto de reemplazo no es válido." };

            foreach (var (oldSale, _) in returnSales)
            {
                if (oldSale.ProductId == np.ProductId)
                    return new ExchangeGiftCardResult { Success = false, ErrorMessage = "El producto nuevo tiene que ser distinto del devuelto." };
            }

            var stock = await _stockValidationService.ValidateStockAvailabilityAsync(np.ProductId, request.PointOfSaleId, np.Quantity);
            if (!stock.IsValid)
                return new ExchangeGiftCardResult { Success = false, ErrorMessage = stock.ErrorMessage ?? "Stock insuficiente." };

            newProducts.Add((product, np.Quantity));
        }

        var returnedTotal = returnSales.Sum(r => r.Sale.Price * r.Quantity);
        var newTotal = newProducts.Sum(p => p.Product.Price * p.Quantity);
        var now = DateTime.UtcNow;
        var bulkId = Guid.NewGuid();
        var newSaleIds = new List<Guid>();
        var returnIds = new List<Guid>();
        decimal totalReleased = 0m;

        await _unitOfWork.BeginTransactionAsync();
        try
        {
            foreach (var group in returnSales.GroupBy(r => r.Sale.ProductId))
            {
                var productId = group.Key;
                var totalQty = group.Sum(g => g.Quantity);
                var returnEntity = new Return
                {
                    ProductId = productId,
                    PointOfSaleId = request.PointOfSaleId,
                    UserId = userId,
                    Quantity = totalQty,
                    Category = request.ReturnCategory,
                    Reason = request.Reason,
                    ReturnDate = now
                };
                returnEntity = await _returnRepository.AddAsync(returnEntity);
                await _unitOfWork.SaveChangesAsync();

                foreach (var (sale, qty) in group)
                {
                    await _returnSaleRepository.AddAsync(new ReturnSale
                    {
                        ReturnId = returnEntity.Id,
                        SaleId = sale.Id,
                        Quantity = qty,
                        UnitPrice = sale.Price
                    });

                    var netCoverage = await _giftCardRepository.GetNetCoverageOnSaleAsync(sale.Id);
                    var releaseAmount = sale.Quantity > 0 ? netCoverage * qty / sale.Quantity : 0m;
                    if (releaseAmount > 0)
                    {
                        totalReleased += releaseAmount;
                        await _giftCardRepository.AddCoverageEntryAsync(new GiftCardCoverageEntry
                        {
                            GiftCardId = card.Id,
                            SaleId = sale.Id,
                            EntryType = GiftCardCoverageEntryType.Release,
                            Amount = releaseAmount,
                            EntryDate = now
                        });
                    }
                }

                await _unitOfWork.SaveChangesAsync();

                var movement = await _inventoryService.CreateReturnMovementAsync(productId, request.PointOfSaleId, returnEntity.Id, totalQty, userId);
                if (!movement.Success)
                {
                    await _unitOfWork.RollbackTransactionAsync();
                    return new ExchangeGiftCardResult { Success = false, ErrorMessage = movement.ErrorMessage };
                }

                returnIds.Add(returnEntity.Id);
            }

            var remainder = await _giftCardRepository.GetAccountedRemainderAsync(card.Id);
            var lineStates = newProducts
                .Select((p, i) => new GiftCardAllocationLineState(i, p.Product.Price * p.Quantity, p.Product.Price * p.Quantity))
                .ToList();

            var (applies, _) = GiftCardAllocation.Allocate(
                lineStates,
                new[] { ("__card__", remainder) });

            var applyByLine = applies
                .GroupBy(a => a.LineIndex)
                .ToDictionary(g => g.Key, g => g.Sum(x => x.Amount));

            decimal newlyApplied = 0m;
            for (var i = 0; i < newProducts.Count; i++)
            {
                var (product, qty) = newProducts[i];
                var sale = new Sale
                {
                    ProductId = product.Id,
                    PointOfSaleId = request.PointOfSaleId,
                    UserId = userId,
                    PaymentMethodId = request.PaymentMethodId,
                    Price = product.Price,
                    Quantity = qty,
                    BulkOperationId = bulkId,
                    SaleDate = now
                };
                sale = await _saleRepository.AddAsync(sale);
                await _unitOfWork.SaveChangesAsync();

                var movement = await _inventoryService.CreateSaleMovementAsync(product.Id, request.PointOfSaleId, sale.Id, qty, userId);
                if (!movement.Success)
                {
                    await _unitOfWork.RollbackTransactionAsync();
                    return new ExchangeGiftCardResult { Success = false, ErrorMessage = movement.ErrorMessage };
                }

                var applyAmount = applyByLine.GetValueOrDefault(i, 0m);
                if (applyAmount > 0)
                {
                    await _giftCardRepository.AddCoverageEntryAsync(new GiftCardCoverageEntry
                    {
                        GiftCardId = card.Id,
                        SaleId = sale.Id,
                        EntryType = GiftCardCoverageEntryType.Apply,
                        Amount = applyAmount,
                        EntryDate = now
                    });
                    newlyApplied += applyAmount;
                }

                newSaleIds.Add(sale.Id);
            }

            var cashDue = Math.Max(0m, newTotal - returnedTotal - newlyApplied + totalReleased);

            if (!string.IsNullOrWhiteSpace(idempotencyKey))
            {
                await _giftCardRepository.AddExchangeOperationAsync(new GiftCardExchangeOperation
                {
                    GiftCardId = card.Id,
                    IdempotencyKey = idempotencyKey,
                    CashDue = cashDue,
                    NewSaleIdsCsv = string.Join(',', newSaleIds),
                    ReturnIdsCsv = string.Join(',', returnIds)
                });
            }

            await _unitOfWork.SaveChangesAsync();
            await _unitOfWork.CommitTransactionAsync();
            _dashboardService.InvalidateDashboardCache();
            return new ExchangeGiftCardResult
            {
                Success = true,
                CashDue = cashDue,
                NewSaleIds = newSaleIds,
                ReturnIds = returnIds
            };
        }
        catch
        {
            await _unitOfWork.RollbackTransactionAsync();
            throw;
        }
    }

    private static ExchangeGiftCardResult MapExchangeOperationResult(GiftCardExchangeOperation operation)
    {
        static List<Guid> ParseIds(string csv)
        {
            if (string.IsNullOrWhiteSpace(csv))
                return new List<Guid>();
            return csv.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Select(Guid.Parse)
                .ToList();
        }

        return new ExchangeGiftCardResult
        {
            Success = true,
            CashDue = operation.CashDue,
            NewSaleIds = ParseIds(operation.NewSaleIdsCsv),
            ReturnIds = ParseIds(operation.ReturnIdsCsv)
        };
    }

    private async Task<GiftCardListItemDto> MapListItemAsync(GiftCard card)
    {
        var remainder = await _giftCardRepository.GetAccountedRemainderAsync(card.Id);
        return new GiftCardListItemDto
        {
            Id = card.Id,
            Code = card.Code,
            PointOfSaleId = card.PointOfSaleId,
            PointOfSaleName = card.PointOfSale?.Name ?? string.Empty,
            HolderName = card.HolderName,
            NominalAmount = card.NominalAmount,
            SpendableBalance = card.SpendableBalance,
            AccountedRemainder = remainder,
            ExpiryDate = card.ExpiryDate,
            CreatedAt = card.CreatedAt
        };
    }

    private async Task<GiftCardDetailDto> MapDetailAsync(GiftCard card)
    {
        var remainder = await _giftCardRepository.GetAccountedRemainderAsync(card.Id);
        var links = card.CoverageEntries
            .Where(e => e.EntryType == GiftCardCoverageEntryType.Apply)
            .GroupBy(e => e.SaleId)
            .Select(g =>
            {
                var sale = g.First().Sale;
                var net = g.Sum(x => x.Amount) - card.CoverageEntries
                    .Where(e => e.SaleId == g.Key && e.EntryType == GiftCardCoverageEntryType.Release)
                    .Sum(e => e.Amount);
                return new GiftCardCoverageLinkDto
                {
                    SaleId = g.Key,
                    ProductSku = sale?.Product?.SKU ?? string.Empty,
                    ProductName = sale?.Product?.Name ?? string.Empty,
                    CoverageAmount = net,
                    SaleDate = sale?.SaleDate ?? DateTime.MinValue
                };
            })
            .Where(l => l.CoverageAmount > 0)
            .OrderBy(l => l.SaleDate)
            .ToList();

        var operations = new List<GiftCardOperationDto>
        {
            new()
            {
                Type = "Issuance",
                OccurredAt = card.IssuanceSale?.SaleDate ?? card.CreatedAt,
                Detail = $"Issued for {card.NominalAmount:F2} EUR"
            }
        };

        foreach (var r in card.Reassignments.OrderBy(x => x.OccurredAt))
        {
            operations.Add(new GiftCardOperationDto
            {
                Type = "Reassignment",
                OccurredAt = r.OccurredAt,
                Detail = $"From {r.FromPointOfSale?.Name} to {r.ToPointOfSale?.Name}"
            });
        }

        foreach (var entry in card.CoverageEntries.OrderBy(e => e.EntryDate))
        {
            operations.Add(new GiftCardOperationDto
            {
                Type = entry.EntryType.ToString(),
                OccurredAt = entry.EntryDate,
                Detail = $"{entry.Amount:F2} EUR on sale {entry.SaleId}"
            });
        }

        return new GiftCardDetailDto
        {
            Id = card.Id,
            Code = card.Code,
            PointOfSaleId = card.PointOfSaleId,
            PointOfSaleName = card.PointOfSale?.Name ?? string.Empty,
            IssuanceSalePointOfSaleId = card.IssuanceSale?.PointOfSaleId ?? card.PointOfSaleId,
            IssuanceSalePointOfSaleName = card.IssuanceSale?.PointOfSale?.Name ?? string.Empty,
            HolderName = card.HolderName,
            NominalAmount = card.NominalAmount,
            SpendableBalance = card.SpendableBalance,
            AccountedRemainder = remainder,
            ExpiryDate = card.ExpiryDate,
            IssuanceSaleId = card.IssuanceSaleId,
            IssuanceSaleDate = card.IssuanceSale?.SaleDate ?? card.CreatedAt,
            LinkedProducts = links,
            Operations = operations
        };
    }
}
