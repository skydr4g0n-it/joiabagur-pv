using JoiabagurPV.Application.DTOs.Returns;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Common;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Interfaces.Repositories;
using JoiabagurPV.Domain.Interfaces.Services;
using Microsoft.EntityFrameworkCore;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Service for returns management operations.
/// </summary>
public class ReturnService : IReturnService
{
    private readonly IReturnRepository _returnRepository;
    private readonly IReturnSaleRepository _returnSaleRepository;
    private readonly IReturnPhotoRepository _returnPhotoRepository;
    private readonly ISaleRepository _saleRepository;
    private readonly IProductRepository _productRepository;
    private readonly IUserPointOfSaleRepository _userPointOfSaleRepository;
    private readonly IInventoryService _inventoryService;
    private readonly IFileStorageService _fileStorageService;
    private readonly IUnitOfWork _unitOfWork;
    private readonly IDashboardService _dashboardService;
    private readonly IGiftCardRepository _giftCardRepository;

    private const int ReturnWindowDays = 30;

    public ReturnService(
        IReturnRepository returnRepository,
        IReturnSaleRepository returnSaleRepository,
        IReturnPhotoRepository returnPhotoRepository,
        ISaleRepository saleRepository,
        IProductRepository productRepository,
        IUserPointOfSaleRepository userPointOfSaleRepository,
        IInventoryService inventoryService,
        IFileStorageService fileStorageService,
        IUnitOfWork unitOfWork,
        IDashboardService dashboardService,
        IGiftCardRepository giftCardRepository)
    {
        _returnRepository = returnRepository ?? throw new ArgumentNullException(nameof(returnRepository));
        _returnSaleRepository = returnSaleRepository ?? throw new ArgumentNullException(nameof(returnSaleRepository));
        _returnPhotoRepository = returnPhotoRepository ?? throw new ArgumentNullException(nameof(returnPhotoRepository));
        _saleRepository = saleRepository ?? throw new ArgumentNullException(nameof(saleRepository));
        _productRepository = productRepository ?? throw new ArgumentNullException(nameof(productRepository));
        _userPointOfSaleRepository = userPointOfSaleRepository ?? throw new ArgumentNullException(nameof(userPointOfSaleRepository));
        _inventoryService = inventoryService ?? throw new ArgumentNullException(nameof(inventoryService));
        _fileStorageService = fileStorageService ?? throw new ArgumentNullException(nameof(fileStorageService));
        _unitOfWork = unitOfWork ?? throw new ArgumentNullException(nameof(unitOfWork));
        _dashboardService = dashboardService ?? throw new ArgumentNullException(nameof(dashboardService));
        _giftCardRepository = giftCardRepository ?? throw new ArgumentNullException(nameof(giftCardRepository));
    }

    /// <inheritdoc/>
    public async Task<CreateReturnResult> CreateReturnAsync(CreateReturnRequest request, Guid userId, bool isAdmin)
    {
        try
        {
            // Validate quantity
            if (request.Quantity <= 0)
            {
                return new CreateReturnResult
                {
                    Success = false,
                    ErrorMessage = "La cantidad debe ser mayor que cero."
                };
            }

            // Validate sale associations
            if (request.SaleAssociations == null || !request.SaleAssociations.Any())
            {
                return new CreateReturnResult
                {
                    Success = false,
                    ErrorMessage = "Debe seleccionar al menos una venta para asociar con la devolución."
                };
            }

            // Validate total quantity matches associations
            var totalAssociatedQuantity = request.SaleAssociations.Sum(sa => sa.Quantity);
            if (totalAssociatedQuantity != request.Quantity)
            {
                return new CreateReturnResult
                {
                    Success = false,
                    ErrorMessage = $"La cantidad total ({request.Quantity}) no coincide con la suma de las cantidades seleccionadas ({totalAssociatedQuantity})."
                };
            }

            // Validate operator is assigned to point of sale (admins can return from any POS)
            if (!isAdmin)
            {
                var isAssigned = await _userPointOfSaleRepository
                    .GetAll()
                    .AnyAsync(ups => ups.UserId == userId &&
                                    ups.PointOfSaleId == request.PointOfSaleId &&
                                    ups.IsActive);

                if (!isAssigned)
                {
                    return new CreateReturnResult
                    {
                        Success = false,
                        ErrorMessage = "El operador no está asignado a este punto de venta."
                    };
                }
            }

            // Validate product exists and is active
            var product = await _productRepository.GetByIdAsync(request.ProductId);
            if (product == null)
            {
                return new CreateReturnResult
                {
                    Success = false,
                    ErrorMessage = $"Producto con ID {request.ProductId} no encontrado."
                };
            }

            // Validate each sale association
            var cutoffDate = DateTime.UtcNow.AddDays(-ReturnWindowDays);
            var saleAssociationsToCreate = new List<(Sale Sale, int Quantity)>();

            foreach (var association in request.SaleAssociations)
            {
                if (association.Quantity <= 0)
                {
                    return new CreateReturnResult
                    {
                        Success = false,
                        ErrorMessage = "Cada asociación de venta debe tener una cantidad mayor que cero."
                    };
                }

                var sale = await _saleRepository.GetByIdWithDetailsAsync(association.SaleId);
                if (sale == null)
                {
                    return new CreateReturnResult
                    {
                        Success = false,
                        ErrorMessage = $"Venta con ID {association.SaleId} no encontrada."
                    };
                }

                // Validate sale is for the same product
                if (sale.ProductId != request.ProductId)
                {
                    return new CreateReturnResult
                    {
                        Success = false,
                        ErrorMessage = $"La venta {association.SaleId} no corresponde al producto seleccionado."
                    };
                }

                // Validate sale is from the same POS
                if (sale.PointOfSaleId != request.PointOfSaleId)
                {
                    return new CreateReturnResult
                    {
                        Success = false,
                        ErrorMessage = $"La venta {association.SaleId} no corresponde al punto de venta seleccionado."
                    };
                }

                if (await _giftCardRepository.IsIssuanceSaleAsync(sale.Id))
                {
                    return new CreateReturnResult
                    {
                        Success = false,
                        ErrorMessage = "No se puede devolver la venta de emisión de una tarjeta regalo por este flujo."
                    };
                }

                if (await _giftCardRepository.SaleHasGiftCardCoverageAsync(sale.Id))
                {
                    return new CreateReturnResult
                    {
                        Success = false,
                        ErrorMessage = "No se puede devolver una venta cubierta por tarjeta regalo por este flujo."
                    };
                }

                // Validate sale is within return window
                if (sale.SaleDate < cutoffDate)
                {
                    return new CreateReturnResult
                    {
                        Success = false,
                        ErrorMessage = $"La venta del {sale.SaleDate:dd/MM/yyyy} está fuera del período de devolución de {ReturnWindowDays} días."
                    };
                }

                // Validate available quantity
                var alreadyReturned = await _returnSaleRepository.GetReturnedQuantityForSaleAsync(sale.Id);
                var availableForReturn = sale.Quantity - alreadyReturned;

                if (association.Quantity > availableForReturn)
                {
                    return new CreateReturnResult
                    {
                        Success = false,
                        ErrorMessage = $"Cantidad solicitada ({association.Quantity}) excede la cantidad disponible para devolución ({availableForReturn}) de la venta del {sale.SaleDate:dd/MM/yyyy}."
                    };
                }

                saleAssociationsToCreate.Add((sale, association.Quantity));
            }

            // Begin transaction
            await _unitOfWork.BeginTransactionAsync();

            try
            {
                // Create Return record
                var returnEntity = new Return
                {
                    ProductId = request.ProductId,
                    PointOfSaleId = request.PointOfSaleId,
                    UserId = userId,
                    Quantity = request.Quantity,
                    Category = request.Category,
                    Reason = request.Reason,
                    ReturnDate = DateTime.UtcNow
                };

                returnEntity = await _returnRepository.AddAsync(returnEntity);
                await _unitOfWork.SaveChangesAsync();

                // Create ReturnSale associations
                foreach (var (sale, quantity) in saleAssociationsToCreate)
                {
                    var returnSale = new ReturnSale
                    {
                        ReturnId = returnEntity.Id,
                        SaleId = sale.Id,
                        Quantity = quantity,
                        UnitPrice = sale.Price // Price snapshot from original sale
                    };

                    await _returnSaleRepository.AddAsync(returnSale);
                }

                await _unitOfWork.SaveChangesAsync();

                // Handle photo if provided
                if (!string.IsNullOrEmpty(request.PhotoBase64))
                {
                    try
                    {
                        var photoBytes = Convert.FromBase64String(request.PhotoBase64);
                        var fileName = $"return_{returnEntity.Id}_{DateTime.UtcNow:yyyyMMddHHmmss}.jpg";

                        // Save photo to storage
                        using var photoStream = new MemoryStream(photoBytes);
                        var storedFileName = await _fileStorageService.UploadAsync(
                            photoStream,
                            fileName,
                            "image/jpeg",
                            $"returns/{returnEntity.Id}");

                        // Create ReturnPhoto record
                        var returnPhoto = new ReturnPhoto
                        {
                            ReturnId = returnEntity.Id,
                            FilePath = storedFileName,
                            FileName = request.PhotoFileName ?? fileName,
                            FileSize = photoBytes.Length,
                            MimeType = "image/jpeg"
                        };

                        await _returnPhotoRepository.AddAsync(returnPhoto);
                        await _unitOfWork.SaveChangesAsync();
                    }
                    catch (Exception)
                    {
                        // Photo save failed, but don't fail the entire return
                        // Log the error but continue with the transaction
                        Console.WriteLine("Failed to save return photo");
                    }
                }

                // Create inventory movement (automatic stock update)
                var movementResult = await _inventoryService.CreateReturnMovementAsync(
                    request.ProductId,
                    request.PointOfSaleId,
                    returnEntity.Id,
                    request.Quantity,
                    userId);

                if (!movementResult.Success)
                {
                    await _unitOfWork.RollbackTransactionAsync();
                    return new CreateReturnResult
                    {
                        Success = false,
                        ErrorMessage = movementResult.ErrorMessage ?? "Error al crear el movimiento de inventario."
                    };
                }

                // Commit transaction
                await _unitOfWork.CommitTransactionAsync();

                _dashboardService.InvalidateDashboardCache();

                // Load return with details for response
                var returnWithDetails = await _returnRepository.GetByIdWithDetailsAsync(returnEntity.Id);

                return new CreateReturnResult
                {
                    Success = true,
                    Return = MapToDto(returnWithDetails!),
                    NewStockQuantity = movementResult.QuantityAfter
                };
            }
            catch (Exception)
            {
                await _unitOfWork.RollbackTransactionAsync();
                throw;
            }
        }
        catch (Exception ex)
        {
            return new CreateReturnResult
            {
                Success = false,
                ErrorMessage = $"Ocurrió un error al crear la devolución: {ex.Message}"
            };
        }
    }

    /// <inheritdoc/>
    public async Task<ReturnDto?> GetReturnByIdAsync(Guid id, Guid userId, bool isAdmin)
    {
        var returnEntity = await _returnRepository.GetByIdWithDetailsAsync(id);
        if (returnEntity == null)
        {
            return null;
        }

        // Check authorization
        if (!isAdmin)
        {
            // Check if operator is assigned to this point of sale
            var isAssigned = await _userPointOfSaleRepository
                .GetAll()
                .AnyAsync(ups => ups.UserId == userId &&
                                ups.PointOfSaleId == returnEntity.PointOfSaleId &&
                                ups.IsActive);

            if (!isAssigned)
            {
                return null; // Not authorized
            }
        }

        return MapToDto(returnEntity);
    }

    /// <inheritdoc/>
    public async Task<ReturnsHistoryResponse> GetReturnsHistoryAsync(
        ReturnsHistoryFilterRequest request,
        Guid userId,
        bool isAdmin)
    {
        List<Return> returns;
        int totalCount;

        var skip = (request.Page - 1) * request.PageSize;
        var take = Math.Min(request.PageSize, PaginationConstants.MaxPageSize);

        if (isAdmin)
        {
            // Admins can see all returns
            (returns, totalCount) = await _returnRepository.GetAllReturnsAsync(
                request.StartDate,
                request.EndDate,
                request.PointOfSaleId,
                request.ProductId,
                skip,
                take);
        }
        else
        {
            // Operators can only see returns from their assigned points of sale
            var assignedPosIds = await _userPointOfSaleRepository
                .GetAll()
                .Where(ups => ups.UserId == userId && ups.IsActive)
                .Select(ups => ups.PointOfSaleId)
                .ToListAsync();

            if (!assignedPosIds.Any())
            {
                // No assigned points of sale
                return new ReturnsHistoryResponse
                {
                    Returns = new List<ReturnDto>(),
                    TotalCount = 0,
                    Page = request.Page,
                    PageSize = request.PageSize,
                    TotalPages = 0,
                    HasNextPage = false,
                    HasPreviousPage = false
                };
            }

            (returns, totalCount) = await _returnRepository.GetByPointOfSalesAsync(
                assignedPosIds,
                request.StartDate,
                request.EndDate,
                request.ProductId,
                skip,
                take);
        }

        var totalPages = (int)Math.Ceiling(totalCount / (double)request.PageSize);

        return new ReturnsHistoryResponse
        {
            Returns = returns.Select(MapToDto).ToList(),
            TotalCount = totalCount,
            Page = request.Page,
            PageSize = request.PageSize,
            TotalPages = totalPages,
            HasNextPage = request.Page < totalPages,
            HasPreviousPage = request.Page > 1
        };
    }

    /// <inheritdoc/>
    public async Task<EligibleSalesResponse?> GetEligibleSalesAsync(
        Guid productId,
        Guid pointOfSaleId,
        Guid userId,
        bool isAdmin)
    {
        // Validate operator is assigned to point of sale (admins can query any POS)
        if (!isAdmin)
        {
            var isAssigned = await _userPointOfSaleRepository
                .GetAll()
                .AnyAsync(ups => ups.UserId == userId &&
                                ups.PointOfSaleId == pointOfSaleId &&
                                ups.IsActive);

            if (!isAssigned)
            {
                return null; // Not authorized
            }
        }

        var cutoffDate = DateTime.UtcNow.AddDays(-ReturnWindowDays);

        // Get sales within return window for this product and POS
        var (sales, _) = await _saleRepository.GetByPointOfSaleAsync(
            pointOfSaleId,
            startDate: cutoffDate,
            productId: productId,
            take: 50); // Max 50 eligible sales

        var eligibleSales = new List<EligibleSaleDto>();

        foreach (var sale in sales)
        {
            var alreadyReturned = await _returnSaleRepository.GetReturnedQuantityForSaleAsync(sale.Id);
            var availableForReturn = sale.Quantity - alreadyReturned;

            if (availableForReturn > 0)
            {
                if (await _giftCardRepository.IsIssuanceSaleAsync(sale.Id))
                    continue;

                if (await _giftCardRepository.SaleHasGiftCardCoverageAsync(sale.Id))
                    continue;

                var daysRemaining = (int)(sale.SaleDate.AddDays(ReturnWindowDays) - DateTime.UtcNow).TotalDays;

                eligibleSales.Add(new EligibleSaleDto
                {
                    SaleId = sale.Id,
                    SaleDate = sale.SaleDate,
                    OriginalQuantity = sale.Quantity,
                    ReturnedQuantity = alreadyReturned,
                    AvailableForReturn = availableForReturn,
                    UnitPrice = sale.Price,
                    PaymentMethodName = sale.PaymentMethod?.Name ?? string.Empty,
                    DaysRemaining = Math.Max(0, daysRemaining)
                });
            }
        }

        return new EligibleSalesResponse
        {
            EligibleSales = eligibleSales.OrderBy(s => s.SaleDate).ToList(),
            TotalAvailableForReturn = eligibleSales.Sum(s => s.AvailableForReturn)
        };
    }

    /// <inheritdoc/>
    public async Task<string?> GetReturnPhotoPathAsync(Guid returnId)
    {
        var photo = await _returnPhotoRepository.GetByReturnIdAsync(returnId);
        return photo?.FilePath;
    }

    /// <inheritdoc/>
    public async Task<(Stream Stream, string ContentType, string FileName)?> GetReturnPhotoStreamAsync(Guid returnId)
    {
        var photo = await _returnPhotoRepository.GetByReturnIdAsync(returnId);
        if (photo == null || string.IsNullOrEmpty(photo.FilePath))
        {
            return null;
        }

        // Extract folder from the file path
        var folder = $"returns/{returnId}";
        var result = await _fileStorageService.DownloadAsync(photo.FilePath, folder);

        if (result == null)
        {
            return null;
        }

        return (result.Value.Stream, result.Value.ContentType, photo.FileName);
    }

    /// <summary>
    /// Maps a Return entity to a ReturnDto.
    /// </summary>
    private static ReturnDto MapToDto(Return returnEntity)
    {
        return new ReturnDto
        {
            Id = returnEntity.Id,
            ProductId = returnEntity.ProductId,
            ProductSku = returnEntity.Product?.SKU ?? string.Empty,
            ProductName = returnEntity.Product?.Name ?? string.Empty,
            PointOfSaleId = returnEntity.PointOfSaleId,
            PointOfSaleName = returnEntity.PointOfSale?.Name ?? string.Empty,
            UserId = returnEntity.UserId,
            UserName = returnEntity.User?.Username ?? string.Empty,
            Quantity = returnEntity.Quantity,
            Category = returnEntity.Category,
            CategoryName = GetCategoryName(returnEntity.Category),
            Reason = returnEntity.Reason,
            TotalValue = returnEntity.GetTotalValue(),
            HasPhoto = returnEntity.Photo != null,
            ReturnDate = returnEntity.ReturnDate,
            CreatedAt = returnEntity.CreatedAt,
            AssociatedSales = returnEntity.ReturnSales?.Select(rs => new ReturnSaleDto
            {
                SaleId = rs.SaleId,
                SaleDate = rs.Sale?.SaleDate ?? DateTime.MinValue,
                Quantity = rs.Quantity,
                UnitPrice = rs.UnitPrice,
                Subtotal = rs.GetSubtotal(),
                PaymentMethodName = rs.Sale?.PaymentMethod?.Name ?? string.Empty
            }).ToList() ?? new List<ReturnSaleDto>()
        };
    }

    /// <summary>
    /// Gets the display name for a return category.
    /// </summary>
    private static string GetCategoryName(Domain.Enums.ReturnCategory category)
    {
        return category switch
        {
            Domain.Enums.ReturnCategory.Defectuoso => "Defectuoso",
            Domain.Enums.ReturnCategory.TamañoIncorrecto => "Tamaño Incorrecto",
            Domain.Enums.ReturnCategory.NoSatisfecho => "No Satisfecho",
            Domain.Enums.ReturnCategory.Otro => "Otro",
            _ => category.ToString()
        };
    }
}
