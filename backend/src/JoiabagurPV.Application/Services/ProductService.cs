using JoiabagurPV.Application.DTOs.Products;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Exceptions;
using JoiabagurPV.Domain.Interfaces.Repositories;
using JoiabagurPV.Domain.Interfaces.Services;
using Microsoft.Extensions.Logging;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Service for product management operations.
/// </summary>
public class ProductService : IProductService
{
    private readonly IProductRepository _productRepository;
    private readonly ICollectionRepository _collectionRepository;
    private readonly IInventoryRepository _inventoryRepository;
    private readonly IUserPointOfSaleService _userPointOfSaleService;
    private readonly IFileStorageService _fileStorageService;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<ProductService> _logger;

    public ProductService(
        IProductRepository productRepository,
        ICollectionRepository collectionRepository,
        IInventoryRepository inventoryRepository,
        IUserPointOfSaleService userPointOfSaleService,
        IFileStorageService fileStorageService,
        IUnitOfWork unitOfWork,
        ILogger<ProductService> logger)
    {
        _productRepository = productRepository;
        _collectionRepository = collectionRepository;
        _inventoryRepository = inventoryRepository;
        _userPointOfSaleService = userPointOfSaleService;
        _fileStorageService = fileStorageService;
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    /// <inheritdoc/>
    public async Task<List<ProductDto>> GetAllAsync(bool includeInactive = true)
    {
        var products = await _productRepository.GetAllAsync(includeInactive);
        var productDtos = new List<ProductDto>();
        foreach (var product in products)
        {
            productDtos.Add(await MapToDtoAsync(product));
        }
        return productDtos;
    }

    /// <inheritdoc/>
    public async Task<ProductDto?> GetByIdAsync(Guid productId)
    {
        var product = await _productRepository.GetWithPhotosAsync(productId);
        return product != null ? await MapToDtoAsync(product) : null;
    }

    /// <inheritdoc/>
    public async Task<ProductDto?> GetBySkuAsync(string sku)
    {
        var normalizedSku = (sku ?? string.Empty).Trim().ToUpperInvariant();
        var product = await _productRepository.GetBySkuAsync(normalizedSku);
        return product != null ? await MapToDtoAsync(product) : null;
    }

    /// <inheritdoc/>
    public async Task<ProductDto> CreateAsync(CreateProductRequest request)
    {
        var normalizedSku = (request.SKU ?? string.Empty).Trim().ToUpperInvariant();
        var normalizedName = (request.Name ?? string.Empty).Trim();

        if (string.IsNullOrWhiteSpace(normalizedSku))
        {
            throw new DomainException("El SKU es requerido");
        }

        if (string.IsNullOrWhiteSpace(normalizedName))
        {
            throw new DomainException("El nombre es requerido");
        }

        // Validate SKU uniqueness
        if (await _productRepository.SkuExistsAsync(normalizedSku))
        {
            throw new DomainException($"Ya existe un producto con el SKU '{normalizedSku}'.");
        }

        // Validate price
        if (request.Price <= 0)
        {
            throw new DomainException("El precio del producto debe ser mayor que cero.");
        }

        // Validate collection if provided
        if (request.CollectionId.HasValue)
        {
            var collection = await _collectionRepository.GetByIdAsync(request.CollectionId.Value);
            if (collection == null)
            {
                throw new DomainException($"Colección con ID '{request.CollectionId}' no encontrada.");
            }

            // Ensure CollectionName is available in the response DTO
            // (MapToDto uses product.Collection?.Name)
            // We'll attach the loaded entity to the new product below.
        }

        var product = new Product
        {
            SKU = normalizedSku,
            Name = normalizedName,
            Description = request.Description,
            Price = request.Price,
            CollectionId = request.CollectionId,
            IsActive = true
        };

        if (request.CollectionId.HasValue)
        {
            product.Collection = await _collectionRepository.GetByIdAsync(request.CollectionId.Value);
        }

        await _productRepository.AddAsync(product);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Product created: {SKU} - {Name}", product.SKU, product.Name);

        return await MapToDtoAsync(product);
    }

    /// <inheritdoc/>
    public async Task<ProductDto> UpdateAsync(Guid productId, UpdateProductRequest request)
    {
        var product = await _productRepository.GetByIdAsync(productId);
        if (product == null)
        {
            throw new DomainException($"Producto con ID '{productId}' no encontrado.");
        }

        var normalizedName = (request.Name ?? string.Empty).Trim();
        if (string.IsNullOrWhiteSpace(normalizedName))
        {
            throw new DomainException("El nombre es requerido");
        }

        // Validate price
        if (request.Price <= 0)
        {
            throw new DomainException("El precio del producto debe ser mayor que cero.");
        }

        // Validate collection if provided
        if (request.CollectionId.HasValue)
        {
            if (!await _collectionRepository.ExistsAsync(request.CollectionId.Value))
            {
                throw new DomainException($"Colección con ID '{request.CollectionId}' no encontrada.");
            }
        }

        product.Name = normalizedName;
        product.Description = request.Description;
        product.Price = request.Price;
        product.CollectionId = request.CollectionId;
        product.IsActive = request.IsActive;

        await _productRepository.UpdateAsync(product);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Product updated: {SKU} - {Name}", product.SKU, product.Name);

        // Load the Collection navigation property if CollectionId is set
        if (product.CollectionId.HasValue)
        {
            product.Collection = await _collectionRepository.GetByIdAsync(product.CollectionId.Value);
        }
        else
        {
            product.Collection = null;
        }

        return await MapToDtoAsync(product);
    }

    /// <inheritdoc/>
    public async Task DeactivateAsync(Guid productId)
    {
        var product = await _productRepository.GetByIdAsync(productId);
        if (product == null)
        {
            throw new DomainException($"Producto con ID '{productId}' no encontrado.");
        }

        product.IsActive = false;
        await _productRepository.UpdateAsync(product);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Product deactivated: {SKU}", product.SKU);
    }

    /// <inheritdoc/>
    public async Task ActivateAsync(Guid productId)
    {
        var product = await _productRepository.GetByIdAsync(productId);
        if (product == null)
        {
            throw new DomainException($"Producto con ID '{productId}' no encontrado.");
        }

        product.IsActive = true;
        await _productRepository.UpdateAsync(product);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Product activated: {SKU}", product.SKU);
    }

    /// <inheritdoc/>
    public async Task<PaginatedResultDto<ProductListDto>> GetProductsAsync(
        CatalogQueryParameters parameters,
        Guid? userId = null,
        bool isAdmin = true)
    {
        // Normalize and validate parameters
        var page = Math.Max(1, parameters.Page);
        var pageSize = Math.Clamp(parameters.PageSize, 1, 100);
        var sortBy = (parameters.SortBy ?? "name").ToLowerInvariant();
        var sortDirection = (parameters.SortDirection ?? "asc").ToLowerInvariant();

        _logger.LogDebug(
            "Getting products catalog: Page={Page}, PageSize={PageSize}, SortBy={SortBy}, IsAdmin={IsAdmin}, UserId={UserId}",
            page, pageSize, sortBy, isAdmin, userId);

        // Get product IDs that the user can access
        HashSet<Guid>? allowedProductIds = null;
        if (!isAdmin && userId.HasValue)
        {
            var assignedPosIds = await _userPointOfSaleService.GetAssignedPointOfSaleIdsAsync(userId.Value);
            if (assignedPosIds.Count == 0)
            {
                // Operator with no POS assignments sees no products
                return PaginatedResultDto<ProductListDto>.Create(new List<ProductListDto>(), 0, page, pageSize);
            }
            allowedProductIds = await _inventoryRepository.GetProductIdsWithInventoryAtPointsOfSaleAsync(assignedPosIds);
            if (allowedProductIds.Count == 0)
            {
                return PaginatedResultDto<ProductListDto>.Create(new List<ProductListDto>(), 0, page, pageSize);
            }
        }

        // Get all products (we'll filter and paginate in memory for now)
        // TODO: Optimize with database-level pagination when needed
        var allProducts = await _productRepository.GetAllAsync(parameters.IncludeInactive);

        // Apply role-based filtering for operators
        if (allowedProductIds != null)
        {
            allProducts = allProducts.Where(p => allowedProductIds.Contains(p.Id)).ToList();
        }

        // Apply sorting
        allProducts = ApplySorting(allProducts, sortBy, sortDirection);

        // Get total count before pagination
        var totalCount = allProducts.Count;

        // Apply pagination
        var pagedProducts = allProducts
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToList();

        // Get inventory quantities for the products on this page
        var productIds = pagedProducts.Select(p => p.Id).ToList();
        var inventoryQuantities = await GetInventoryQuantitiesAsync(productIds, allowedProductIds != null ? userId : null, isAdmin);

        // Map to DTOs
        var items = new List<ProductListDto>();
        foreach (var product in pagedProducts)
        {
            items.Add(await MapToListDtoAsync(product, inventoryQuantities));
        }

        return PaginatedResultDto<ProductListDto>.Create(items, totalCount, page, pageSize);
    }

    /// <inheritdoc/>
    public async Task<List<ProductListDto>> SearchProductsAsync(
        string query,
        Guid? userId = null,
        bool isAdmin = true,
        int maxResults = 50)
    {
        if (string.IsNullOrWhiteSpace(query) || query.Length < 2)
        {
            return new List<ProductListDto>();
        }

        var normalizedQuery = query.Trim();
        maxResults = Math.Clamp(maxResults, 1, 100);

        _logger.LogDebug(
            "Searching products: Query='{Query}', IsAdmin={IsAdmin}, UserId={UserId}",
            normalizedQuery, isAdmin, userId);

        // Get product IDs that the user can access
        HashSet<Guid>? allowedProductIds = null;
        if (!isAdmin && userId.HasValue)
        {
            var assignedPosIds = await _userPointOfSaleService.GetAssignedPointOfSaleIdsAsync(userId.Value);
            if (assignedPosIds.Count == 0)
            {
                return new List<ProductListDto>();
            }
            allowedProductIds = await _inventoryRepository.GetProductIdsWithInventoryAtPointsOfSaleAsync(assignedPosIds);
            if (allowedProductIds.Count == 0)
            {
                return new List<ProductListDto>();
            }
        }

        // Get all active products
        var allProducts = await _productRepository.GetAllAsync(includeInactive: false);

        // Apply role-based filtering for operators
        if (allowedProductIds != null)
        {
            allProducts = allProducts.Where(p => allowedProductIds.Contains(p.Id)).ToList();
        }

        // Search: SKU exact match first, then name partial match
        var normalizedQueryUpper = normalizedQuery.ToUpperInvariant();
        
        // SKU exact match
        var skuMatch = allProducts.FirstOrDefault(p => 
            p.SKU.ToUpperInvariant() == normalizedQueryUpper);

        // Name partial matches (case-insensitive)
        var nameMatches = allProducts
            .Where(p => p.Name.Contains(normalizedQuery, StringComparison.OrdinalIgnoreCase))
            .OrderBy(p => p.Name)
            .ToList();

        // Combine results: SKU match first, then name matches (excluding SKU match to avoid duplicates)
        var results = new List<Product>();
        if (skuMatch != null)
        {
            results.Add(skuMatch);
            nameMatches = nameMatches.Where(p => p.Id != skuMatch.Id).ToList();
        }
        results.AddRange(nameMatches);

        // Limit results
        results = results.Take(maxResults).ToList();

        // Get inventory quantities
        var productIds = results.Select(p => p.Id).ToList();
        var inventoryQuantities = await GetInventoryQuantitiesAsync(productIds, allowedProductIds != null ? userId : null, isAdmin);

        var listItems = new List<ProductListDto>();
        foreach (var product in results)
        {
            listItems.Add(await MapToListDtoAsync(product, inventoryQuantities));
        }
        return listItems;
    }

    private static List<Product> ApplySorting(List<Product> products, string sortBy, string sortDirection)
    {
        var isDescending = sortDirection == "desc";
        
        return sortBy switch
        {
            "createdat" => isDescending 
                ? products.OrderByDescending(p => p.CreatedAt).ToList()
                : products.OrderBy(p => p.CreatedAt).ToList(),
            "price" => isDescending
                ? products.OrderByDescending(p => p.Price).ToList()
                : products.OrderBy(p => p.Price).ToList(),
            _ => isDescending // default to name
                ? products.OrderByDescending(p => p.Name).ToList()
                : products.OrderBy(p => p.Name).ToList(),
        };
    }

    private async Task<Dictionary<Guid, int>> GetInventoryQuantitiesAsync(
        List<Guid> productIds, 
        Guid? userId,
        bool isAdmin)
    {
        var quantities = new Dictionary<Guid, int>();

        if (productIds.Count == 0)
        {
            return quantities;
        }

        // For admin, sum all inventory; for operator, sum only from assigned POS
        List<Guid>? pointOfSaleIds = null;
        if (!isAdmin && userId.HasValue)
        {
            pointOfSaleIds = await _userPointOfSaleService.GetAssignedPointOfSaleIdsAsync(userId.Value);
        }

        foreach (var productId in productIds)
        {
            var inventories = await _inventoryRepository.FindByProductAsync(productId, activeOnly: true);
            
            if (pointOfSaleIds != null)
            {
                inventories = inventories.Where(i => pointOfSaleIds.Contains(i.PointOfSaleId)).ToList();
            }

            quantities[productId] = inventories.Sum(i => i.Quantity);
        }

        return quantities;
    }

    private async Task<ProductListDto> MapToListDtoAsync(Product product, Dictionary<Guid, int> inventoryQuantities)
    {
        var primaryPhoto = product.Photos?.FirstOrDefault(p => p.IsPrimary) 
            ?? product.Photos?.OrderBy(p => p.DisplayOrder).FirstOrDefault();

        string? primaryPhotoUrl = null;
        if (primaryPhoto != null)
        {
            primaryPhotoUrl = await _fileStorageService.GetUrlAsync(primaryPhoto.FileName, "products");
        }

        return new ProductListDto
        {
            Id = product.Id,
            SKU = product.SKU,
            Name = product.Name,
            Price = product.Price,
            PrimaryPhotoUrl = primaryPhotoUrl,
            CollectionName = product.Collection?.Name,
            IsActive = product.IsActive,
            AvailableQuantity = inventoryQuantities.GetValueOrDefault(product.Id, 0),
            CreatedAt = product.CreatedAt
        };
    }

    private async Task<ProductDto> MapToDtoAsync(Product product)
    {
        // Map photos with URLs
        var photoDtos = new List<ProductPhotoDto>();
        if (product.Photos != null)
        {
            foreach (var photo in product.Photos)
            {
                photoDtos.Add(await MapPhotoToDtoAsync(photo));
            }
        }

        return new ProductDto
        {
            Id = product.Id,
            SKU = product.SKU,
            Name = product.Name,
            Description = product.Description,
            Price = product.Price,
            CollectionId = product.CollectionId,
            CollectionName = product.Collection?.Name,
            IsActive = product.IsActive,
            CreatedAt = product.CreatedAt,
            UpdatedAt = product.UpdatedAt,
            Photos = photoDtos
        };
    }

    private async Task<ProductPhotoDto> MapPhotoToDtoAsync(ProductPhoto photo)
    {
        var url = await _fileStorageService.GetUrlAsync(photo.FileName, "products");

        return new ProductPhotoDto
        {
            Id = photo.Id,
            ProductId = photo.ProductId,
            FileName = photo.FileName,
            Url = url,
            DisplayOrder = photo.DisplayOrder,
            IsPrimary = photo.IsPrimary,
            CreatedAt = photo.CreatedAt,
            UpdatedAt = photo.UpdatedAt
        };
    }
}



