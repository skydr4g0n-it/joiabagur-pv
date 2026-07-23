using System.Security.Claims;
using FluentValidation;
using JoiabagurPV.Application.DTOs.Products;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Exceptions;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JoiabagurPV.API.Controllers;

/// <summary>
/// Controller for product management operations.
/// </summary>
[ApiController]
[Route("api/[controller]")]
[Authorize]
public class ProductsController : ControllerBase
{
    private readonly IProductService _productService;
    private readonly IExcelImportService _excelImportService;
    private readonly IProductPhotoService _productPhotoService;
    private readonly ICurrentUserService _currentUserService;
    private readonly IQrCodeService _qrCodeService;
    private readonly IValidator<CreateProductRequest> _createValidator;
    private readonly IValidator<UpdateProductRequest> _updateValidator;
    private readonly ILogger<ProductsController> _logger;

    public ProductsController(
        IProductService productService,
        IExcelImportService excelImportService,
        IProductPhotoService productPhotoService,
        ICurrentUserService currentUserService,
        IQrCodeService qrCodeService,
        IValidator<CreateProductRequest> createValidator,
        IValidator<UpdateProductRequest> updateValidator,
        ILogger<ProductsController> logger)
    {
        _productService = productService;
        _excelImportService = excelImportService;
        _productPhotoService = productPhotoService;
        _currentUserService = currentUserService;
        _qrCodeService = qrCodeService;
        _createValidator = createValidator;
        _updateValidator = updateValidator;
        _logger = logger;
    }

    /// <summary>
    /// Gets a paginated catalog of products with role-based filtering.
    /// Administrators see all products; operators see only products with inventory at their assigned points of sale.
    /// </summary>
    /// <param name="page">Page number (1-based). Defaults to 1.</param>
    /// <param name="pageSize">Items per page. Defaults to 50. Max 100.</param>
    /// <param name="sortBy">Sort field: "name", "createdAt", "price". Defaults to "name".</param>
    /// <param name="sortDirection">Sort direction: "asc" or "desc". Defaults to "asc".</param>
    /// <param name="includeInactive">Include inactive products. Defaults to false.</param>
    /// <returns>Paginated list of products.</returns>
    [HttpGet]
    [ProducesResponseType(typeof(PaginatedResultDto<ProductListDto>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    public async Task<IActionResult> GetCatalog(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 50,
        [FromQuery] string sortBy = "name",
        [FromQuery] string sortDirection = "asc",
        [FromQuery] bool includeInactive = false)
    {
        var parameters = new CatalogQueryParameters
        {
            Page = page,
            PageSize = pageSize,
            SortBy = sortBy,
            SortDirection = sortDirection,
            IncludeInactive = includeInactive
        };

        var result = await _productService.GetProductsAsync(
            parameters,
            _currentUserService.UserId,
            _currentUserService.IsAdmin);

        return Ok(result);
    }

    /// <summary>
    /// Searches products by SKU (exact match) or name (partial match).
    /// Role-based filtering applies: operators only see products with inventory at their assigned points of sale.
    /// </summary>
    /// <param name="query">Search query. Minimum 2 characters.</param>
    /// <returns>List of matching products (max 50).</returns>
    [HttpGet("search")]
    [ProducesResponseType(typeof(List<ProductListDto>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    public async Task<IActionResult> Search([FromQuery] string query)
    {
        if (string.IsNullOrWhiteSpace(query) || query.Length < 2)
        {
            return BadRequest(new { error = "La búsqueda requiere al menos 2 caracteres." });
        }

        var results = await _productService.SearchProductsAsync(
            query,
            _currentUserService.UserId,
            _currentUserService.IsAdmin);

        return Ok(results);
    }

    /// <summary>
    /// Gets a product by ID.
    /// </summary>
    /// <param name="productId">The product ID.</param>
    /// <returns>The product details.</returns>
    [HttpGet("{productId:guid}")]
    [ProducesResponseType(typeof(ProductDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetById(Guid productId)
    {
        var product = await _productService.GetByIdAsync(productId);

        if (product == null)
        {
            return NotFound(new { error = "Producto no encontrado" });
        }

        return Ok(product);
    }

    /// <summary>
    /// Gets a product by SKU.
    /// </summary>
    /// <param name="sku">The product SKU.</param>
    /// <returns>The product details.</returns>
    [HttpGet("by-sku/{sku}")]
    [ProducesResponseType(typeof(ProductDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetBySku(string sku)
    {
        var product = await _productService.GetBySkuAsync(sku);

        if (product == null)
        {
            return NotFound(new { error = $"Producto con SKU '{sku}' no encontrado" });
        }

        return Ok(product);
    }

    /// <summary>
    /// Creates a new product.
    /// </summary>
    /// <param name="request">The product creation request.</param>
    /// <returns>The created product.</returns>
    [HttpPost]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(ProductDto), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> Create([FromBody] CreateProductRequest request)
    {
        var validationResult = await _createValidator.ValidateAsync(request);
        if (!validationResult.IsValid)
        {
            return BadRequest(new { errors = validationResult.Errors.Select(e => e.ErrorMessage) });
        }

        try
        {
            var product = await _productService.CreateAsync(request);
            return CreatedAtAction(nameof(GetById), new { productId = product.Id }, product);
        }
        catch (DomainException ex) when (ex.Message.Contains("already exists"))
        {
            return Conflict(new { error = ex.Message });
        }
        catch (DomainException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Updates an existing product.
    /// </summary>
    /// <param name="productId">The product ID to update.</param>
    /// <param name="request">The update request.</param>
    /// <returns>The updated product.</returns>
    [HttpPut("{productId:guid}")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(ProductDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> Update(Guid productId, [FromBody] UpdateProductRequest request)
    {
        var validationResult = await _updateValidator.ValidateAsync(request);
        if (!validationResult.IsValid)
        {
            return BadRequest(new { errors = validationResult.Errors.Select(e => e.ErrorMessage) });
        }

        try
        {
            var product = await _productService.UpdateAsync(productId, request);
            return Ok(product);
        }
        catch (DomainException ex) when (ex.Message.Contains("not found"))
        {
            return NotFound(new { error = ex.Message });
        }
        catch (DomainException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Deactivates (soft deletes) a product.
    /// </summary>
    /// <param name="productId">The product ID.</param>
    /// <returns>204 No Content on success.</returns>
    [HttpDelete("{productId:guid}")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> Deactivate(Guid productId)
    {
        try
        {
            await _productService.DeactivateAsync(productId);
            return NoContent();
        }
        catch (DomainException ex)
        {
            return NotFound(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Reactivates a previously deactivated product.
    /// </summary>
    /// <param name="productId">The product ID.</param>
    /// <returns>204 No Content on success.</returns>
    [HttpPost("{productId:guid}/activate")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> Activate(Guid productId)
    {
        try
        {
            await _productService.ActivateAsync(productId);
            return NoContent();
        }
        catch (DomainException ex)
        {
            return NotFound(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Generates a QR code SVG for a product, encoding its SKU.
    /// Only administrators can generate QR codes.
    /// </summary>
    /// <param name="productId">The product ID.</param>
    /// <returns>SVG image of the QR code.</returns>
    [HttpGet("{productId:guid}/qrcode")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetQrCode(Guid productId)
    {
        var product = await _productService.GetByIdAsync(productId);
        if (product == null)
        {
            return NotFound(new { error = "Producto no encontrado" });
        }

        var svg = _qrCodeService.GenerateSvg(product.SKU, $"{product.SKU} - {product.Name}");
        return Content(svg, "image/svg+xml");
    }

    /// <summary>
    /// Generates a printable PDF with QR code labels for multiple products.
    /// Only administrators can generate batch QR codes.
    /// </summary>
    /// <param name="productIds">Optional list of product IDs to include. If empty, generates for all active products.</param>
    /// <returns>PDF file with QR code labels.</returns>
    [HttpGet("qrcodes/batch")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    public async Task<IActionResult> GetQrCodeBatch([FromQuery] List<Guid>? productIds = null)
    {
        List<(string Sku, string Name)> products;

        if (productIds != null && productIds.Count != 0)
        {
            products = new List<(string, string)>();
            foreach (var id in productIds)
            {
                var product = await _productService.GetByIdAsync(id);
                if (product != null)
                    products.Add((product.SKU, product.Name));
            }
        }
        else
        {
            var allProducts = await _productService.GetAllAsync(includeInactive: false);
            products = allProducts.Select(p => (p.SKU, p.Name)).ToList();
        }

        var pdf = _qrCodeService.GeneratePdf(products);
        return File(pdf, "application/pdf", "qr-labels.pdf");
    }

    /// <summary>
    /// Downloads an Excel template for product import.
    /// Only administrators can access this endpoint.
    /// </summary>
    [HttpGet("import-template")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(FileContentResult), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    public IActionResult DownloadImportTemplate()
    {
        _logger.LogInformation("Generating product import template");

        var templateStream = _excelImportService.GenerateTemplate();
        var content = templateStream.ToArray();

        return File(
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "product-import-template.xlsx");
    }

    /// <summary>
    /// Imports products from an Excel file.
    /// Only administrators can import products.
    /// </summary>
    /// <param name="file">The Excel file (.xlsx or .xls).</param>
    /// <returns>Import result with created/updated counts.</returns>
    [HttpPost("import")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(ImportResult), StatusCodes.Status200OK)]
    [ProducesResponseType(typeof(ImportResult), StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status413PayloadTooLarge)]
    [RequestSizeLimit(10 * 1024 * 1024)] // 10 MB
    public async Task<IActionResult> Import(IFormFile file)
    {
        // Validate file presence
        if (file == null || file.Length == 0)
        {
            return BadRequest(new ImportResult
            {
                Success = false,
                Message = "No file provided.",
                Errors = new List<ImportError>
                {
                    new ImportError { RowNumber = 0, Field = "File", Message = "File is required." }
                }
            });
        }

        // Validate file size
        if (file.Length > _excelImportService.MaxFileSizeBytes)
        {
            return StatusCode(StatusCodes.Status413PayloadTooLarge, new ImportResult
            {
                Success = false,
                Message = "File size exceeds the maximum allowed size.",
                Errors = new List<ImportError>
                {
                    new ImportError 
                    { 
                        RowNumber = 0, 
                        Field = "File", 
                        Message = $"File size exceeds maximum of {_excelImportService.MaxFileSizeBytes / (1024 * 1024)} MB." 
                    }
                }
            });
        }

        // Validate file extension
        var extension = Path.GetExtension(file.FileName).ToLowerInvariant();
        if (!_excelImportService.AllowedExtensions.Contains(extension))
        {
            return BadRequest(new ImportResult
            {
                Success = false,
                Message = "Invalid file format.",
                Errors = new List<ImportError>
                {
                    new ImportError 
                    { 
                        RowNumber = 0, 
                        Field = "File", 
                        Message = $"Invalid file type. Allowed types: {string.Join(", ", _excelImportService.AllowedExtensions)}" 
                    }
                }
            });
        }

        _logger.LogInformation("Starting product import from file: {FileName}", file.FileName);

        try
        {
            await using var stream = file.OpenReadStream();
            var result = await _excelImportService.ImportAsync(stream);

            if (result.Success)
            {
                _logger.LogInformation(
                    "Product import completed: {Created} created, {Updated} updated",
                    result.CreatedCount, result.UpdatedCount);
                return Ok(result);
            }
            else
            {
                _logger.LogWarning("Product import failed with {ErrorCount} errors", result.Errors.Count);
                return BadRequest(result);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during product import");
            return BadRequest(new ImportResult
            {
                Success = false,
                Message = "An error occurred during import.",
                Errors = new List<ImportError>
                {
                    new ImportError { RowNumber = 0, Field = "File", Message = ex.Message }
                }
            });
        }
    }

    /// <summary>
    /// Validates an Excel file for product import without performing the import.
    /// Only administrators can validate import files.
    /// </summary>
    /// <param name="file">The Excel file (.xlsx or .xls).</param>
    /// <returns>Validation result with any errors found.</returns>
    [HttpPost("import/validate")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(ImportResult), StatusCodes.Status200OK)]
    [ProducesResponseType(typeof(ImportResult), StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [RequestSizeLimit(10 * 1024 * 1024)] // 10 MB
    public async Task<IActionResult> ValidateImport(IFormFile file)
    {
        // Validate file presence
        if (file == null || file.Length == 0)
        {
            return BadRequest(new ImportResult
            {
                Success = false,
                Message = "No file provided.",
                Errors = new List<ImportError>
                {
                    new ImportError { RowNumber = 0, Field = "File", Message = "File is required." }
                }
            });
        }

        // Validate file extension
        var extension = Path.GetExtension(file.FileName).ToLowerInvariant();
        if (!_excelImportService.AllowedExtensions.Contains(extension))
        {
            return BadRequest(new ImportResult
            {
                Success = false,
                Message = "Invalid file format.",
                Errors = new List<ImportError>
                {
                    new ImportError 
                    { 
                        RowNumber = 0, 
                        Field = "File", 
                        Message = $"Invalid file type. Allowed types: {string.Join(", ", _excelImportService.AllowedExtensions)}" 
                    }
                }
            });
        }

        try
        {
            await using var stream = file.OpenReadStream();
            var result = await _excelImportService.ValidateAsync(stream);
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error validating product import file");
            return BadRequest(new ImportResult
            {
                Success = false,
                Message = "An error occurred during validation.",
                Errors = new List<ImportError>
                {
                    new ImportError { RowNumber = 0, Field = "File", Message = ex.Message }
                }
            });
        }
    }

    /// <summary>
    /// Uploads a photo for a product.
    /// Only administrators can upload photos.
    /// </summary>
    /// <param name="productId">The product ID.</param>
    /// <param name="file">The photo file (JPG or PNG).</param>
    /// <returns>The uploaded photo information.</returns>
    [HttpPost("{productId:guid}/photos")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(ProductPhotoDto), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status413PayloadTooLarge)]
    [RequestSizeLimit(5 * 1024 * 1024)] // 5 MB
    public async Task<IActionResult> UploadPhoto(Guid productId, IFormFile file)
    {
        // Validate file presence
        if (file == null || file.Length == 0)
        {
            return BadRequest(new { error = "No file provided." });
        }

        // Validate file size (5 MB max)
        const long maxFileSize = 5 * 1024 * 1024;
        if (file.Length > maxFileSize)
        {
            return StatusCode(StatusCodes.Status413PayloadTooLarge, new 
            { 
                error = $"File size exceeds maximum of {maxFileSize / (1024 * 1024)} MB." 
            });
        }

        // Validate file extension
        var extension = Path.GetExtension(file.FileName).ToLowerInvariant();
        var allowedExtensions = new[] { ".jpg", ".jpeg", ".png" };
        if (!allowedExtensions.Contains(extension))
        {
            return BadRequest(new 
            { 
                error = "Only JPG and PNG formats are allowed." 
            });
        }

        _logger.LogInformation(
            "Uploading photo for product {ProductId}: {FileName}", 
            productId, 
            file.FileName);

        try
        {
            await using var stream = file.OpenReadStream();
            var photo = await _productPhotoService.UploadPhotoAsync(
                productId, 
                stream, 
                file.FileName, 
                file.ContentType);

            _logger.LogInformation(
                "Photo uploaded successfully for product {ProductId}: {PhotoId}", 
                productId, 
                photo.Id);

            return CreatedAtAction(
                nameof(GetProductPhotos), 
                new { productId }, 
                photo);
        }
        catch (DomainException ex) when (ex.Message.Contains("not found"))
        {
            return NotFound(new { error = ex.Message });
        }
        catch (DomainException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error uploading photo for product {ProductId}", productId);
            return BadRequest(new { error = "An error occurred during photo upload." });
        }
    }

    /// <summary>
    /// Gets all photos for a product.
    /// </summary>
    /// <param name="productId">The product ID.</param>
    /// <returns>List of photos ordered by display order.</returns>
    [HttpGet("{productId:guid}/photos")]
    [ProducesResponseType(typeof(List<ProductPhotoDto>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetProductPhotos(Guid productId)
    {
        try
        {
            var photos = await _productPhotoService.GetProductPhotosAsync(productId);
            return Ok(photos);
        }
        catch (DomainException ex)
        {
            return NotFound(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Sets a photo as the primary photo for a product.
    /// Only administrators can set primary photos.
    /// </summary>
    /// <param name="productId">The product ID.</param>
    /// <param name="photoId">The photo ID to set as primary.</param>
    /// <returns>204 No Content on success.</returns>
    [HttpPost("{productId:guid}/photos/{photoId:guid}/set-primary")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> SetPrimaryPhoto(Guid productId, Guid photoId)
    {
        try
        {
            await _productPhotoService.SetPrimaryPhotoAsync(photoId);
            return NoContent();
        }
        catch (DomainException ex)
        {
            return NotFound(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Updates the display order of photos for a product.
    /// Only administrators can reorder photos.
    /// </summary>
    /// <param name="productId">The product ID.</param>
    /// <param name="request">Dictionary mapping photo IDs to new display order values.</param>
    /// <returns>204 No Content on success.</returns>
    [HttpPut("{productId:guid}/photos/order")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> UpdatePhotoOrder(Guid productId, [FromBody] Dictionary<Guid, int> request)
    {
        if (request == null || request.Count == 0)
        {
            return BadRequest(new { error = "Photo order mapping is required." });
        }

        try
        {
            await _productPhotoService.UpdateDisplayOrderAsync(productId, request);
            return NoContent();
        }
        catch (DomainException ex) when (ex.Message.Contains("not found"))
        {
            return NotFound(new { error = ex.Message });
        }
        catch (DomainException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    /// <summary>
    /// Deletes a photo.
    /// Only administrators can delete photos.
    /// </summary>
    /// <param name="productId">The product ID.</param>
    /// <param name="photoId">The photo ID to delete.</param>
    /// <returns>204 No Content on success.</returns>
    [HttpDelete("{productId:guid}/photos/{photoId:guid}")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> DeletePhoto(Guid productId, Guid photoId)
    {
        try
        {
            await _productPhotoService.DeletePhotoAsync(photoId);
            return NoContent();
        }
        catch (DomainException ex)
        {
            return NotFound(new { error = ex.Message });
        }
    }
}



