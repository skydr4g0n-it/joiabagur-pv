using JoiabagurPV.Application.DTOs.Sales;
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

/// <summary>
/// Service for sales management operations.
/// </summary>
public class SalesService : ISalesService
{
    private readonly ISaleRepository _saleRepository;
    private readonly ISalePhotoRepository _salePhotoRepository;
    private readonly IProductRepository _productRepository;
    private readonly IPointOfSaleRepository _pointOfSaleRepository;
    private readonly IUserPointOfSaleRepository _userPointOfSaleRepository;
    private readonly IStockValidationService _stockValidationService;
    private readonly IPaymentMethodValidationService _paymentMethodValidationService;
    private readonly IInventoryService _inventoryService;
    private readonly IFileStorageService _fileStorageService;
    private readonly IUnitOfWork _unitOfWork;
    private readonly IDashboardService _dashboardService;
    private readonly IPosCommissionReportService _commissionReportService;
    private readonly IGiftCardRepository _giftCardRepository;
    private readonly IPaymentMethodRepository _paymentMethodRepository;

    public SalesService(
        ISaleRepository saleRepository,
        ISalePhotoRepository salePhotoRepository,
        IProductRepository productRepository,
        IPointOfSaleRepository pointOfSaleRepository,
        IUserPointOfSaleRepository userPointOfSaleRepository,
        IStockValidationService stockValidationService,
        IPaymentMethodValidationService paymentMethodValidationService,
        IInventoryService inventoryService,
        IFileStorageService fileStorageService,
        IUnitOfWork unitOfWork,
        IDashboardService dashboardService,
        IPosCommissionReportService commissionReportService,
        IGiftCardRepository giftCardRepository,
        IPaymentMethodRepository paymentMethodRepository)
    {
        _saleRepository = saleRepository ?? throw new ArgumentNullException(nameof(saleRepository));
        _salePhotoRepository = salePhotoRepository ?? throw new ArgumentNullException(nameof(salePhotoRepository));
        _productRepository = productRepository ?? throw new ArgumentNullException(nameof(productRepository));
        _pointOfSaleRepository = pointOfSaleRepository ?? throw new ArgumentNullException(nameof(pointOfSaleRepository));
        _userPointOfSaleRepository = userPointOfSaleRepository ?? throw new ArgumentNullException(nameof(userPointOfSaleRepository));
        _stockValidationService = stockValidationService ?? throw new ArgumentNullException(nameof(stockValidationService));
        _paymentMethodValidationService = paymentMethodValidationService ?? throw new ArgumentNullException(nameof(paymentMethodValidationService));
        _inventoryService = inventoryService ?? throw new ArgumentNullException(nameof(inventoryService));
        _fileStorageService = fileStorageService ?? throw new ArgumentNullException(nameof(fileStorageService));
        _unitOfWork = unitOfWork ?? throw new ArgumentNullException(nameof(unitOfWork));
        _dashboardService = dashboardService ?? throw new ArgumentNullException(nameof(dashboardService));
        _commissionReportService = commissionReportService ?? throw new ArgumentNullException(nameof(commissionReportService));
        _giftCardRepository = giftCardRepository ?? throw new ArgumentNullException(nameof(giftCardRepository));
        _paymentMethodRepository = paymentMethodRepository ?? throw new ArgumentNullException(nameof(paymentMethodRepository));
    }

    /// <inheritdoc/>
    /// <remarks>
    /// <para><b>Transaction Management:</b></para>
    /// <para>This method implements a double stock validation pattern for concurrency safety:</para>
    /// <list type="number">
    /// <item>First validation: Before transaction (fast fail for obvious issues)</item>
    /// <item>Second validation: Inside transaction (prevents race conditions)</item>
    /// </list>
    /// <para>If stock changes between validations, the error message shows the difference.</para>
    /// <para><b>Atomic Operations:</b></para>
    /// <para>Sale, SalePhoto, and InventoryMovement are created in a single transaction.</para>
    /// <para>If any step fails, all changes are rolled back to maintain data integrity.</para>
    /// <para><b>Price Snapshot:</b></para>
    /// <para>The product price at sale time is frozen in Sale.Price to preserve historical accuracy.</para>
    /// </remarks>
    public async Task<CreateSaleResult> CreateSaleAsync(CreateSaleRequest request, Guid userId, bool isAdmin)
    {
        try
        {
            // Validate quantity
            if (request.Quantity <= 0)
            {
                return new CreateSaleResult
                {
                    Success = false,
                    ErrorMessage = "Quantity must be greater than zero."
                };
            }

            // Validate operator is assigned to point of sale (admins can sell from any POS)
            if (!isAdmin)
            {
                var isAssigned = await _userPointOfSaleRepository
                    .GetAll()
                    .AnyAsync(ups => ups.UserId == userId && 
                                    ups.PointOfSaleId == request.PointOfSaleId &&
                                    ups.IsActive);

                if (!isAssigned)
                {
                    return new CreateSaleResult
                    {
                        Success = false,
                        ErrorMessage = "Operator is not assigned to this point of sale."
                    };
                }
            }

            // Validate product exists and is active
            var product = await _productRepository.GetByIdAsync(request.ProductId);
            if (product == null)
            {
                return new CreateSaleResult
                {
                    Success = false,
                    ErrorMessage = $"Product with ID {request.ProductId} not found."
                };
            }

            if (!product.IsActive)
            {
                return new CreateSaleResult
                {
                    Success = false,
                    ErrorMessage = $"Product '{product.Name}' is not active."
                };
            }

            // Load POS to check AllowManualPriceEdit policy
            var pointOfSale = await _pointOfSaleRepository.GetByIdAsync(request.PointOfSaleId);
            if (pointOfSale == null)
            {
                return new CreateSaleResult
                {
                    Success = false,
                    ErrorMessage = $"Point of sale with ID {request.PointOfSaleId} not found."
                };
            }

            // Reject manual price when POS disallows overrides
            if (request.Price.HasValue && !pointOfSale.AllowManualPriceEdit)
            {
                return new CreateSaleResult
                {
                    Success = false,
                    ErrorMessage = "Manual price editing is not allowed for this point of sale."
                };
            }

            // FIRST stock validation (before transaction)
            var stockValidation = await _stockValidationService.ValidateStockAvailabilityAsync(
                request.ProductId,
                request.PointOfSaleId,
                request.Quantity);

            if (!stockValidation.IsValid)
            {
                return new CreateSaleResult
                {
                    Success = false,
                    ErrorMessage = stockValidation.ErrorMessage ?? "Insufficient stock available."
                };
            }

            // Validate payment method
            try
            {
                await _paymentMethodValidationService.ValidatePaymentMethodAsync(
                    request.PaymentMethodId,
                    request.PointOfSaleId);
            }
            catch (InvalidOperationException ex)
            {
                return new CreateSaleResult
                {
                    Success = false,
                    ErrorMessage = ex.Message
                };
            }

            // Begin transaction
            await _unitOfWork.BeginTransactionAsync();
            
            try
            {
                // SECOND stock validation (double check for concurrency safety)
                var finalStockValidation = await _stockValidationService.ValidateStockAvailabilityAsync(
                    request.ProductId,
                    request.PointOfSaleId,
                    request.Quantity);

                if (!finalStockValidation.IsValid)
                {
                    await _unitOfWork.RollbackTransactionAsync();
                    return new CreateSaleResult
                    {
                        Success = false,
                        ErrorMessage = $"Stock changed. Available: {finalStockValidation.AvailableQuantity}, Requested: {request.Quantity}"
                    };
                }

                // Price resolution
                var officialPrice = product.Price;
                decimal effectivePrice;
                bool priceWasOverridden;
                decimal? originalProductPrice;

                if (pointOfSale.AllowManualPriceEdit && request.Price.HasValue && request.Price.Value != officialPrice)
                {
                    effectivePrice = request.Price.Value;
                    priceWasOverridden = true;
                    originalProductPrice = officialPrice;
                }
                else
                {
                    effectivePrice = officialPrice;
                    priceWasOverridden = false;
                    originalProductPrice = null;
                }

                // Create Sale record
                var sale = new Sale
                {
                    ProductId = request.ProductId,
                    PointOfSaleId = request.PointOfSaleId,
                    UserId = userId,
                    PaymentMethodId = request.PaymentMethodId,
                    Price = effectivePrice,
                    Quantity = request.Quantity,
                    PriceWasOverridden = priceWasOverridden,
                    OriginalProductPrice = originalProductPrice,
                    Notes = request.Notes,
                    SaleDate = DateTime.UtcNow
                };

                sale = await _saleRepository.AddAsync(sale);
                await _unitOfWork.SaveChangesAsync();

                // Handle photo if provided
                // Note: Photo compression will be handled by ImageCompressionService in the controller
                // Here we just save the already-compressed photo
                if (!string.IsNullOrEmpty(request.PhotoBase64))
                {
                    try
                    {
                        var photoBytes = Convert.FromBase64String(request.PhotoBase64);
                        var fileName = $"sale_{sale.Id}_{DateTime.UtcNow:yyyyMMddHHmmss}.jpg";
                        
                        // Save photo to storage
                        using var photoStream = new MemoryStream(photoBytes);
                        var storedFileName = await _fileStorageService.UploadAsync(
                            photoStream, 
                            fileName, 
                            "image/jpeg", 
                            $"sales/{sale.Id}");

                        // Create SalePhoto record
                        var salePhoto = new SalePhoto
                        {
                            SaleId = sale.Id,
                            FilePath = storedFileName,
                            FileName = request.PhotoFileName ?? fileName,
                            FileSize = photoBytes.Length,
                            MimeType = "image/jpeg"
                        };

                        await _salePhotoRepository.AddAsync(salePhoto);
                        await _unitOfWork.SaveChangesAsync();
                    }
                    catch (Exception ex)
                    {
                        // Photo save failed, but don't fail the entire sale
                        // Log the error but continue with the transaction
                        Console.WriteLine($"Failed to save sale photo: {ex.Message}");
                    }
                }

                // Create inventory movement (automatic stock update)
                var movementResult = await _inventoryService.CreateSaleMovementAsync(
                    request.ProductId,
                    request.PointOfSaleId,
                    sale.Id,
                    request.Quantity,
                    userId);

                if (!movementResult.Success)
                {
                    await _unitOfWork.RollbackTransactionAsync();
                    return new CreateSaleResult
                    {
                        Success = false,
                        ErrorMessage = movementResult.ErrorMessage ?? "Failed to create inventory movement."
                    };
                }

                // Commit transaction
                await _unitOfWork.CommitTransactionAsync();

                _dashboardService.InvalidateDashboardCache();

                // Load sale with details for response
                var saleWithDetails = await _saleRepository.GetByIdWithDetailsAsync(sale.Id);

                return new CreateSaleResult
                {
                    Success = true,
                    Sale = MapToDto(saleWithDetails!, 0m),
                    WarningMessage = stockValidation.IsLowStock ? stockValidation.WarningMessage : null,
                    IsLowStock = stockValidation.IsLowStock,
                    RemainingStock = movementResult.QuantityAfter
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
            return new CreateSaleResult
            {
                Success = false,
                ErrorMessage = $"An error occurred while creating the sale: {ex.Message}"
            };
        }
    }

    /// <inheritdoc/>
    public async Task<SaleDto?> GetSaleByIdAsync(Guid id, Guid userId, bool isAdmin)
    {
        var sale = await _saleRepository.GetByIdWithDetailsAsync(id);
        if (sale == null)
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
                                ups.PointOfSaleId == sale.PointOfSaleId &&
                                ups.IsActive);

            if (!isAssigned)
            {
                return null; // Not authorized
            }
        }

        var coverage = await _giftCardRepository.GetNetCoverageOnSaleAsync(sale.Id);
        return MapToDto(sale, coverage);
    }

    /// <inheritdoc/>
    public async Task<SalesHistoryResponse> GetSalesHistoryAsync(
        SalesHistoryFilterRequest request, 
        Guid userId, 
        bool isAdmin)
    {
        List<Sale> sales;
        int totalCount;

        var skip = (request.Page - 1) * request.PageSize;
        var take = Math.Min(request.PageSize, PaginationConstants.MaxPageSize);

        if (isAdmin)
        {
            // Admins can see all sales
            (sales, totalCount) = await _saleRepository.GetAllSalesAsync(
                request.StartDate,
                request.EndDate,
                request.PointOfSaleId,
                request.ProductId,
                request.UserId,
                request.PaymentMethodId,
                skip,
                take);
        }
        else
        {
            // Operators can only see sales from their assigned points of sale
            var assignedPosIds = await _userPointOfSaleRepository
                .GetAll()
                .Where(ups => ups.UserId == userId && ups.IsActive)
                .Select(ups => ups.PointOfSaleId)
                .ToListAsync();

            if (!assignedPosIds.Any())
            {
                // No assigned points of sale
                return new SalesHistoryResponse
                {
                    Sales = new List<SaleDto>(),
                    TotalCount = 0,
                    Page = request.Page,
                    PageSize = request.PageSize,
                    TotalPages = 0,
                    HasNextPage = false,
                    HasPreviousPage = false
                };
            }

            (sales, totalCount) = await _saleRepository.GetByPointOfSalesAsync(
                assignedPosIds,
                request.StartDate,
                request.EndDate,
                request.ProductId,
                request.UserId,
                request.PaymentMethodId,
                skip,
                take);
        }

        var totalPages = (int)Math.Ceiling(totalCount / (double)request.PageSize);

        var saleIds = sales.Select(s => s.Id).ToList();
        var coverageMap = await _giftCardRepository.GetNetCoverageBySaleIdsAsync(saleIds);

        return new SalesHistoryResponse
        {
            Sales = sales.Select(s => MapToDto(s, coverageMap.GetValueOrDefault(s.Id, 0m))).ToList(),
            TotalCount = totalCount,
            Page = request.Page,
            PageSize = request.PageSize,
            TotalPages = totalPages,
            HasNextPage = request.Page < totalPages,
            HasPreviousPage = request.Page > 1
        };
    }

    /// <inheritdoc/>
    public async Task<string?> GetSalePhotoPathAsync(Guid saleId)
    {
        var photo = await _salePhotoRepository.GetBySaleIdAsync(saleId);
        return photo?.FilePath;
    }

    /// <inheritdoc/>
    public async Task<(Stream Stream, string ContentType, string FileName)?> GetSalePhotoStreamAsync(Guid saleId)
    {
        var photo = await _salePhotoRepository.GetBySaleIdAsync(saleId);
        if (photo == null || string.IsNullOrEmpty(photo.FilePath))
        {
            return null;
        }

        // Extract folder from the file path
        var folder = $"sales/{saleId}";
        var result = await _fileStorageService.DownloadAsync(photo.FilePath, folder);
        
        if (result == null)
        {
            return null;
        }

        return (result.Value.Stream, result.Value.ContentType, photo.FileName);
    }

    /// <inheritdoc/>
    public async Task<CreateBulkSalesResult> CreateBulkSalesAsync(CreateBulkSalesRequest request, Guid userId, bool isAdmin)
    {
        try
        {
            if (request.Lines.Count == 0)
            {
                return new CreateBulkSalesResult { Success = false, ErrorMessage = "At least one sale line is required." };
            }

            if (!isAdmin)
            {
                var isAssigned = await _userPointOfSaleRepository
                    .GetAll()
                    .AnyAsync(ups => ups.UserId == userId &&
                                    ups.PointOfSaleId == request.PointOfSaleId &&
                                    ups.IsActive);
                if (!isAssigned)
                {
                    return new CreateBulkSalesResult { Success = false, ErrorMessage = "Operator is not assigned to this point of sale." };
                }
            }

            var pointOfSale = await _pointOfSaleRepository.GetByIdAsync(request.PointOfSaleId);
            if (pointOfSale == null)
            {
                return new CreateBulkSalesResult { Success = false, ErrorMessage = $"Point of sale with ID {request.PointOfSaleId} not found." };
            }

            try
            {
                await _paymentMethodValidationService.ValidatePaymentMethodAsync(request.PaymentMethodId, request.PointOfSaleId);
            }
            catch (InvalidOperationException ex)
            {
                return new CreateBulkSalesResult { Success = false, ErrorMessage = ex.Message };
            }

            var products = new Dictionary<Guid, Product>();
            for (int i = 0; i < request.Lines.Count; i++)
            {
                var line = request.Lines[i];

                var product = await _productRepository.GetByIdAsync(line.ProductId);
                if (product == null)
                    return new CreateBulkSalesResult { Success = false, ErrorMessage = $"Line {i + 1}: Product with ID {line.ProductId} not found." };
                if (!product.IsActive)
                    return new CreateBulkSalesResult { Success = false, ErrorMessage = $"Line {i + 1}: Product '{product.Name}' is not active." };
                if (product.SystemProductKind != null)
                    return new CreateBulkSalesResult { Success = false, ErrorMessage = $"Line {i + 1}: System products cannot be sold through bulk checkout." };
                if (line.Price.HasValue && !pointOfSale.AllowManualPriceEdit)
                    return new CreateBulkSalesResult { Success = false, ErrorMessage = $"Line {i + 1}: Manual price editing is not allowed for this point of sale." };

                if (line.Quantity <= 0)
                    return new CreateBulkSalesResult { Success = false, ErrorMessage = $"Line {i + 1}: Quantity must be greater than zero." };

                products[line.ProductId] = product;

                var stockValidation = await _stockValidationService.ValidateStockAvailabilityAsync(line.ProductId, request.PointOfSaleId, line.Quantity);
                if (!stockValidation.IsValid)
                    return new CreateBulkSalesResult { Success = false, ErrorMessage = $"Line {i + 1}: {stockValidation.ErrorMessage ?? "Insufficient stock."}" };
            }

            var giftCardCodes = request.GiftCardCodes?
                .Where(c => !string.IsNullOrWhiteSpace(c))
                .Select(c => c.Trim())
                .ToList() ?? new List<string>();

            var lineTotals = new List<decimal>();
            for (int i = 0; i < request.Lines.Count; i++)
            {
                var line = request.Lines[i];
                var product = products[line.ProductId];
                var officialPrice = product.Price;
                decimal effectivePrice;
                if (pointOfSale.AllowManualPriceEdit && line.Price.HasValue && line.Price.Value != officialPrice)
                    effectivePrice = line.Price.Value;
                else
                    effectivePrice = officialPrice;
                lineTotals.Add(effectivePrice * line.Quantity);
            }

            var cartTotal = lineTotals.Sum();
            List<GiftCardAllocationApply> allocationApplies = new();
            Dictionary<string, GiftCard> lockedCardsByCode = new();
            Guid? giftCardPaymentMethodId = null;

            if (giftCardCodes.Count > 0)
            {
                giftCardPaymentMethodId = await _paymentMethodRepository.GetAll()
                    .Where(pm => pm.Code == GiftCardConstants.GiftCardPaymentMethodCode)
                    .Select(pm => pm.Id)
                    .FirstOrDefaultAsync();
                if (giftCardPaymentMethodId == Guid.Empty)
                    return new CreateBulkSalesResult { Success = false, ErrorMessage = "Gift card payment method is not configured." };
            }

            var bulkOperationId = Guid.NewGuid();
            var createdSales = new List<SaleDto>();
            var warnings = new List<BulkSaleLineWarning>();

            await _unitOfWork.BeginTransactionAsync();
            try
            {
                if (giftCardCodes.Count > 0)
                {
                    var locked = await _giftCardRepository.LockByCodesAsync(giftCardCodes);
                    lockedCardsByCode = locked.ToDictionary(c => c.Code, c => c);

                    foreach (var code in giftCardCodes)
                    {
                        if (!lockedCardsByCode.TryGetValue(code, out var card))
                        {
                            await _unitOfWork.RollbackTransactionAsync();
                            return new CreateBulkSalesResult { Success = false, ErrorMessage = $"Gift card '{code}' was not found." };
                        }

                        if (card.PointOfSaleId != request.PointOfSaleId)
                        {
                            await _unitOfWork.RollbackTransactionAsync();
                            return new CreateBulkSalesResult { Success = false, ErrorMessage = $"Gift card '{code}' is not valid at this point of sale." };
                        }

                        if (GiftCardEconomics.IsExpiredForRedemption(card.ExpiryDate))
                        {
                            await _unitOfWork.RollbackTransactionAsync();
                            return new CreateBulkSalesResult { Success = false, ErrorMessage = $"Gift card '{code}' is expired." };
                        }

                        if (card.SpendableBalance <= 0)
                        {
                            await _unitOfWork.RollbackTransactionAsync();
                            return new CreateBulkSalesResult { Success = false, ErrorMessage = $"Gift card '{code}' was already used." };
                        }
                    }

                    var cardsInOrder = giftCardCodes
                        .Select(code => (code, lockedCardsByCode[code].SpendableBalance))
                        .ToList();
                    var lineStates = lineTotals
                        .Select((total, index) => new GiftCardAllocationLineState(index, total, total))
                        .ToList();
                    var (applies, consumedCodes) = GiftCardAllocation.Allocate(lineStates, cardsInOrder);
                    allocationApplies = applies;

                    foreach (var code in consumedCodes)
                        lockedCardsByCode[code].SpendableBalance = 0m;
                }

                var coverageTotal = allocationApplies.Sum(a => a.Amount);
                var cashDue = cartTotal - coverageTotal;
                Guid linePaymentMethodId;

                if (cashDue <= 0)
                {
                    if (giftCardPaymentMethodId == null)
                    {
                        await _unitOfWork.RollbackTransactionAsync();
                        return new CreateBulkSalesResult { Success = false, ErrorMessage = "Gift card payment method is not configured." };
                    }

                    if (request.PaymentMethodId != giftCardPaymentMethodId.Value)
                    {
                        await _unitOfWork.RollbackTransactionAsync();
                        return new CreateBulkSalesResult { Success = false, ErrorMessage = "Fully covered checkouts must use the gift card payment method." };
                    }

                    linePaymentMethodId = giftCardPaymentMethodId.Value;
                }
                else
                {
                    if (giftCardPaymentMethodId.HasValue && request.PaymentMethodId == giftCardPaymentMethodId.Value)
                    {
                        await _unitOfWork.RollbackTransactionAsync();
                        return new CreateBulkSalesResult { Success = false, ErrorMessage = "Gift card payment method cannot be used when cash is still due." };
                    }

                    linePaymentMethodId = request.PaymentMethodId;
                }

                var appliesByLine = allocationApplies
                    .GroupBy(a => a.LineIndex)
                    .ToDictionary(g => g.Key, g => g.ToList());

                for (int i = 0; i < request.Lines.Count; i++)
                {
                    var line = request.Lines[i];
                    var product = products[line.ProductId];

                    var finalStockValidation = await _stockValidationService.ValidateStockAvailabilityAsync(line.ProductId, request.PointOfSaleId, line.Quantity);
                    if (!finalStockValidation.IsValid)
                    {
                        await _unitOfWork.RollbackTransactionAsync();
                        return new CreateBulkSalesResult { Success = false, ErrorMessage = $"Line {i + 1}: Stock changed. Available: {finalStockValidation.AvailableQuantity}, Requested: {line.Quantity}" };
                    }

                    var officialPrice = product.Price;
                    decimal effectivePrice;
                    bool priceWasOverridden;
                    decimal? originalProductPrice;

                    if (pointOfSale.AllowManualPriceEdit && line.Price.HasValue && line.Price.Value != officialPrice)
                    {
                        effectivePrice = line.Price.Value;
                        priceWasOverridden = true;
                        originalProductPrice = officialPrice;
                    }
                    else
                    {
                        effectivePrice = officialPrice;
                        priceWasOverridden = false;
                        originalProductPrice = null;
                    }

                    var sale = new Sale
                    {
                        ProductId = line.ProductId,
                        PointOfSaleId = request.PointOfSaleId,
                        UserId = userId,
                        PaymentMethodId = linePaymentMethodId,
                        Price = effectivePrice,
                        Quantity = line.Quantity,
                        PriceWasOverridden = priceWasOverridden,
                        OriginalProductPrice = originalProductPrice,
                        Notes = request.Notes,
                        BulkOperationId = bulkOperationId,
                        SaleDate = DateTime.UtcNow
                    };

                    sale = await _saleRepository.AddAsync(sale);
                    await _unitOfWork.SaveChangesAsync();

                    if (appliesByLine.TryGetValue(i, out var lineApplies))
                    {
                        var entryDate = sale.SaleDate;
                        foreach (var apply in lineApplies)
                        {
                            var card = lockedCardsByCode[apply.CardCode];
                            await _giftCardRepository.AddCoverageEntryAsync(new GiftCardCoverageEntry
                            {
                                GiftCardId = card.Id,
                                SaleId = sale.Id,
                                EntryType = GiftCardCoverageEntryType.Apply,
                                Amount = apply.Amount,
                                EntryDate = entryDate
                            });
                        }

                        await _unitOfWork.SaveChangesAsync();
                    }

                    if (!string.IsNullOrEmpty(line.PhotoBase64))
                    {
                        try
                        {
                            var photoBytes = Convert.FromBase64String(line.PhotoBase64);
                            var fileName = $"sale_{sale.Id}_{DateTime.UtcNow:yyyyMMddHHmmss}.jpg";
                            using var photoStream = new MemoryStream(photoBytes);
                            var storedFileName = await _fileStorageService.UploadAsync(photoStream, fileName, "image/jpeg", $"sales/{sale.Id}");

                            var salePhoto = new SalePhoto
                            {
                                SaleId = sale.Id,
                                FilePath = storedFileName,
                                FileName = line.PhotoFileName ?? fileName,
                                FileSize = photoBytes.Length,
                                MimeType = "image/jpeg"
                            };
                            await _salePhotoRepository.AddAsync(salePhoto);
                            await _unitOfWork.SaveChangesAsync();
                        }
                        catch (Exception)
                        {
                            // Photo save failed but don't fail the entire bulk operation
                        }
                    }

                    var movementResult = await _inventoryService.CreateSaleMovementAsync(line.ProductId, request.PointOfSaleId, sale.Id, line.Quantity, userId);
                    if (!movementResult.Success)
                    {
                        await _unitOfWork.RollbackTransactionAsync();
                        return new CreateBulkSalesResult { Success = false, ErrorMessage = $"Line {i + 1}: {movementResult.ErrorMessage ?? "Failed to create inventory movement."}" };
                    }

                    var saleWithDetails = await _saleRepository.GetByIdWithDetailsAsync(sale.Id);
                    var coverageOnSale = appliesByLine.TryGetValue(i, out var applied)
                        ? applied.Sum(a => a.Amount)
                        : 0m;
                    createdSales.Add(MapToDto(saleWithDetails!, coverageOnSale));

                    if (finalStockValidation.IsLowStock)
                    {
                        warnings.Add(new BulkSaleLineWarning
                        {
                            LineIndex = i,
                            ProductName = product.Name,
                            Message = finalStockValidation.WarningMessage ?? "Low stock",
                            IsLowStock = true,
                            RemainingStock = movementResult.QuantityAfter
                        });
                    }
                }

                await _unitOfWork.CommitTransactionAsync();

                _dashboardService.InvalidateDashboardCache();

                return new CreateBulkSalesResult
                {
                    Success = true,
                    BulkOperationId = bulkOperationId,
                    Sales = createdSales,
                    Warnings = warnings
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
            return new CreateBulkSalesResult
            {
                Success = false,
                ErrorMessage = $"An error occurred during bulk sale creation: {ex.Message}"
            };
        }
    }

    /// <inheritdoc/>
    public async Task<SalesReportResponse> GetSalesReportAsync(
        SalesReportFilterRequest request,
        Guid userId,
        bool isAdmin)
    {
        var posIds = await GetAuthorizedPosIdsAsync(userId, isAdmin);
        if (!isAdmin && posIds != null && posIds.Count == 0)
        {
            return new SalesReportResponse
            {
                Items = new List<SalesReportItemDto>(),
                TotalCount = 0,
                Page = request.Page,
                PageSize = request.PageSize,
                TotalPages = 0,
                TotalSalesCount = 0,
                TotalQuantity = 0,
                TotalAmount = 0,
                TotalCommission = 0,
                TotalAmountNet = 0
            };
        }

        var skip = (request.Page - 1) * request.PageSize;

        var (sales, totalCount) = await _saleRepository.GetSalesForReportAsync(
            posIds,
            request.StartDate, request.EndDate,
            request.PointOfSaleId, request.ProductId,
            request.UserId, request.PaymentMethodId,
            request.Search, request.AmountMin, request.AmountMax,
            request.HasPhoto, request.PriceWasOverridden,
            skip, request.PageSize);

        var (aggCount, aggQuantity, _) = await _saleRepository.GetSalesReportAggregatesAsync(
            posIds,
            request.StartDate, request.EndDate,
            request.PointOfSaleId, request.ProductId,
            request.UserId, request.PaymentMethodId,
            request.Search, request.AmountMin, request.AmountMax,
            request.HasPhoto, request.PriceWasOverridden);

        var commissionResult = await _commissionReportService.ComputeReportCommissionsAsync(
            posIds,
            request.StartDate, request.EndDate,
            request.PointOfSaleId, request.ProductId,
            request.UserId, request.PaymentMethodId,
            request.Search, request.AmountMin, request.AmountMax,
            request.HasPhoto, request.PriceWasOverridden);

        var totalPages = (int)Math.Ceiling(totalCount / (double)request.PageSize);

        return new SalesReportResponse
        {
            Items = sales.Select(MapToReportItemDto).ToList(),
            TotalCount = totalCount,
            Page = request.Page,
            PageSize = request.PageSize,
            TotalPages = totalPages,
            TotalSalesCount = aggCount,
            TotalQuantity = aggQuantity,
            TotalAmount = commissionResult.ReturnAdjustedGross,
            TotalCommission = commissionResult.TotalCommission,
            TotalAmountNet = commissionResult.TotalAmountNet,
            AggregatesByPointOfSale = commissionResult.AggregatesByPointOfSale.Count > 0
                ? commissionResult.AggregatesByPointOfSale
                : null
        };
    }

    /// <inheritdoc/>
    public async Task<(MemoryStream Stream, int TotalCount)> ExportSalesReportAsync(
        SalesReportFilterRequest request,
        Guid userId,
        bool isAdmin)
    {
        var posIds = await GetAuthorizedPosIdsAsync(userId, isAdmin);

        var (aggCount, _, _) = await _saleRepository.GetSalesReportAggregatesAsync(
            posIds,
            request.StartDate, request.EndDate,
            request.PointOfSaleId, request.ProductId,
            request.UserId, request.PaymentMethodId,
            request.Search, request.AmountMin, request.AmountMax,
            request.HasPhoto, request.PriceWasOverridden);

        if (aggCount > 10_000)
        {
            throw new InvalidOperationException($"EXPORT_LIMIT_EXCEEDED:{aggCount}");
        }

        var (sales, _) = await _saleRepository.GetSalesForReportAsync(
            posIds,
            request.StartDate, request.EndDate,
            request.PointOfSaleId, request.ProductId,
            request.UserId, request.PaymentMethodId,
            request.Search, request.AmountMin, request.AmountMax,
            request.HasPhoto, request.PriceWasOverridden,
            skip: 0, take: 10_000);

        var items = sales.Select(MapToReportItemDto).ToList();

        var commissionResult = await _commissionReportService.ComputeReportCommissionsAsync(
            posIds,
            request.StartDate, request.EndDate,
            request.PointOfSaleId, request.ProductId,
            request.UserId, request.PaymentMethodId,
            request.Search, request.AmountMin, request.AmountMax,
            request.HasPhoto, request.PriceWasOverridden);

        var stream = GenerateSalesReportExcel(items, commissionResult);
        return (stream, aggCount);
    }

    private MemoryStream GenerateSalesReportExcel(List<SalesReportItemDto> items, SalesReportCommissionResult totals)
    {
        using var workbook = new ClosedXML.Excel.XLWorkbook();

        var ws = workbook.Worksheets.Add("Ventas");
        var headers = new[]
        {
            "Fecha", "Hora", "SKU", "Producto", "Colección", "Punto de venta",
            "Cantidad", "Precio", "Total", "Precio original",
            "Método de pago", "Operador", "Notas", "Con foto"
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
            ws.Cell(row, 1).Value = item.SaleDate.ToString("dd/MM/yyyy");
            ws.Cell(row, 2).Value = item.SaleDate.ToString("HH:mm");
            ws.Cell(row, 3).Value = item.ProductSku;
            ws.Cell(row, 4).Value = item.ProductName;
            ws.Cell(row, 5).Value = item.CollectionName ?? "";
            ws.Cell(row, 6).Value = item.PointOfSaleName;
            ws.Cell(row, 7).Value = item.Quantity;
            ws.Cell(row, 8).Value = item.Price;
            ws.Cell(row, 9).Value = item.Total;
            ws.Cell(row, 10).Value = item.PriceWasOverridden ? item.OriginalProductPrice ?? 0m : 0m;
            if (!item.PriceWasOverridden)
                ws.Cell(row, 10).Value = "";
            ws.Cell(row, 11).Value = item.PaymentMethodName;
            ws.Cell(row, 12).Value = item.OperatorName;
            ws.Cell(row, 13).Value = item.Notes ?? "";
            ws.Cell(row, 14).Value = item.HasPhoto ? "Sí" : "No";
        }

        ws.Columns(8, 10).Style.NumberFormat.Format = "#,##0.00";
        ws.Columns().AdjustToContents();

        var wsSummary = workbook.Worksheets.Add("Resumen por punto de venta");
        var summaryHeaders = new[] { "Punto de venta", "Nº ventas", "Cantidad total", "Importe total" };
        for (var c = 0; c < summaryHeaders.Length; c++)
            wsSummary.Cell(1, c + 1).Value = summaryHeaders[c];

        var summaryHeaderRange = wsSummary.Range(1, 1, 1, summaryHeaders.Length);
        summaryHeaderRange.Style.Font.Bold = true;
        summaryHeaderRange.Style.Fill.BackgroundColor = ClosedXML.Excel.XLColor.LightGray;

        var posSummary = items
            .GroupBy(i => i.PointOfSaleName)
            .Select(g => new
            {
                PosName = g.Key,
                SalesCount = g.Count(),
                TotalQuantity = g.Sum(x => x.Quantity),
                TotalAmount = g.Sum(x => x.Total)
            })
            .OrderBy(x => x.PosName)
            .ToList();

        for (var i = 0; i < posSummary.Count; i++)
        {
            var row = i + 2;
            var pos = posSummary[i];
            wsSummary.Cell(row, 1).Value = pos.PosName;
            wsSummary.Cell(row, 2).Value = pos.SalesCount;
            wsSummary.Cell(row, 3).Value = pos.TotalQuantity;
            wsSummary.Cell(row, 4).Value = pos.TotalAmount;
        }

        var totalRow = posSummary.Count + 2;
        wsSummary.Cell(totalRow, 1).Value = "TOTAL GENERAL";
        wsSummary.Cell(totalRow, 2).Value = posSummary.Sum(x => x.SalesCount);
        wsSummary.Cell(totalRow, 3).Value = posSummary.Sum(x => x.TotalQuantity);
        wsSummary.Cell(totalRow, 4).Value = posSummary.Sum(x => x.TotalAmount);

        var totalRowRange = wsSummary.Range(totalRow, 1, totalRow, summaryHeaders.Length);
        totalRowRange.Style.Font.Bold = true;

        wsSummary.Column(4).Style.NumberFormat.Format = "#,##0.00";
        wsSummary.Columns().AdjustToContents();

        var summaryTotalsRow = totalRow + 2;
        wsSummary.Cell(summaryTotalsRow, 1).Value = "Importe total (ventas - devoluciones)";
        wsSummary.Cell(summaryTotalsRow, 4).Value = totals.ReturnAdjustedGross;
        wsSummary.Cell(summaryTotalsRow + 1, 1).Value = "Comisión total";
        wsSummary.Cell(summaryTotalsRow + 1, 4).Value = totals.TotalCommission;
        wsSummary.Cell(summaryTotalsRow + 2, 1).Value = "Importe neto";
        wsSummary.Cell(summaryTotalsRow + 2, 4).Value = totals.TotalAmountNet;
        wsSummary.Range(summaryTotalsRow, 1, summaryTotalsRow + 2, 4).Style.Font.Bold = true;

        var ms = new MemoryStream();
        workbook.SaveAs(ms);
        ms.Position = 0;
        return ms;
    }

    private async Task<List<Guid>?> GetAuthorizedPosIdsAsync(Guid userId, bool isAdmin)
    {
        if (isAdmin)
            return null;

        return await _userPointOfSaleRepository
            .GetAll()
            .Where(ups => ups.UserId == userId && ups.IsActive)
            .Select(ups => ups.PointOfSaleId)
            .ToListAsync();
    }

    private static SalesReportItemDto MapToReportItemDto(Sale sale)
    {
        return new SalesReportItemDto
        {
            Id = sale.Id,
            SaleDate = sale.SaleDate,
            ProductName = sale.Product?.Name ?? string.Empty,
            ProductSku = sale.Product?.SKU ?? string.Empty,
            CollectionName = sale.Product?.Collection?.Name,
            PointOfSaleName = sale.PointOfSale?.Name ?? string.Empty,
            Quantity = sale.Quantity,
            Price = sale.Price,
            Total = sale.GetTotal(),
            OriginalProductPrice = sale.OriginalProductPrice,
            PriceWasOverridden = sale.PriceWasOverridden,
            PaymentMethodName = sale.PaymentMethod?.Name ?? string.Empty,
            OperatorName = sale.User?.Username ?? string.Empty,
            Notes = sale.Notes,
            HasPhoto = sale.Photo != null
        };
    }

    /// <summary>
    /// Maps a Sale entity to a SaleDto.
    /// </summary>
    private static SaleDto MapToDto(Sale sale, decimal giftCardCoverageAmount)
    {
        return new SaleDto
        {
            Id = sale.Id,
            ProductId = sale.ProductId,
            ProductSku = sale.Product?.SKU ?? string.Empty,
            ProductName = sale.Product?.Name ?? string.Empty,
            PointOfSaleId = sale.PointOfSaleId,
            PointOfSaleName = sale.PointOfSale?.Name ?? string.Empty,
            UserId = sale.UserId,
            UserName = sale.User?.Username ?? string.Empty,
            PaymentMethodId = sale.PaymentMethodId,
            PaymentMethodName = sale.PaymentMethod?.Name ?? string.Empty,
            Price = sale.Price,
            Quantity = sale.Quantity,
            Total = sale.GetTotal(),
            PriceWasOverridden = sale.PriceWasOverridden,
            OriginalProductPrice = sale.OriginalProductPrice,
            Notes = sale.Notes,
            HasPhoto = sale.Photo != null,
            HasReturn = sale.ReturnSales.Count > 0,
            SaleDate = sale.SaleDate,
            CreatedAt = sale.CreatedAt,
            GiftCardCoverageAmount = giftCardCoverageAmount
        };
    }
}
