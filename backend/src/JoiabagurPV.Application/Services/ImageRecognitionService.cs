using System.Text.Json;
using JoiabagurPV.Application.DTOs.ImageRecognition;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Interfaces.Repositories;
using JoiabagurPV.Domain.Interfaces.Services;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Service for image recognition and ML model management operations.
/// </summary>
public class ImageRecognitionService : IImageRecognitionService
{
    private const int EmbeddingVectorLength = 1280;

    private readonly IModelMetadataRepository _modelMetadataRepository;
    private readonly IModelTrainingJobRepository _trainingJobRepository;
    private readonly IProductRepository _productRepository;
    private readonly IProductPhotoRepository _productPhotoRepository;
    private readonly IProductPhotoEmbeddingRepository _embeddingRepository;
    private readonly IInventoryRepository _inventoryRepository;
    private readonly IUserPointOfSaleService _userPointOfSaleService;
    private readonly IFileStorageService _fileStorageService;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<ImageRecognitionService> _logger;

    public ImageRecognitionService(
        IModelMetadataRepository modelMetadataRepository,
        IModelTrainingJobRepository trainingJobRepository,
        IProductRepository productRepository,
        IProductPhotoRepository productPhotoRepository,
        IProductPhotoEmbeddingRepository embeddingRepository,
        IInventoryRepository inventoryRepository,
        IUserPointOfSaleService userPointOfSaleService,
        IFileStorageService fileStorageService,
        IUnitOfWork unitOfWork,
        ILogger<ImageRecognitionService> logger)
    {
        _modelMetadataRepository = modelMetadataRepository ?? throw new ArgumentNullException(nameof(modelMetadataRepository));
        _trainingJobRepository = trainingJobRepository ?? throw new ArgumentNullException(nameof(trainingJobRepository));
        _productRepository = productRepository ?? throw new ArgumentNullException(nameof(productRepository));
        _productPhotoRepository = productPhotoRepository ?? throw new ArgumentNullException(nameof(productPhotoRepository));
        _embeddingRepository = embeddingRepository ?? throw new ArgumentNullException(nameof(embeddingRepository));
        _inventoryRepository = inventoryRepository ?? throw new ArgumentNullException(nameof(inventoryRepository));
        _userPointOfSaleService = userPointOfSaleService ?? throw new ArgumentNullException(nameof(userPointOfSaleService));
        _fileStorageService = fileStorageService ?? throw new ArgumentNullException(nameof(fileStorageService));
        _unitOfWork = unitOfWork ?? throw new ArgumentNullException(nameof(unitOfWork));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <inheritdoc/>
    public async Task<ModelMetadataDto?> GetActiveModelMetadataAsync()
    {
        var activeModel = await _modelMetadataRepository.GetActiveModelAsync();
        return activeModel != null ? MapToDto(activeModel) : null;
    }

    /// <inheritdoc/>
    public async Task<List<ModelMetadataDto>> GetAllModelVersionsAsync()
    {
        var models = await _modelMetadataRepository.GetAllVersionsAsync();
        return models.Select(MapToDto).ToList();
    }

    /// <inheritdoc/>
    public async Task<string?> GetModelFilePathAsync(string? version = null)
    {
        ModelMetadata? model;

        if (string.IsNullOrEmpty(version))
        {
            model = await _modelMetadataRepository.GetActiveModelAsync();
        }
        else
        {
            model = await _modelMetadataRepository.GetByVersionAsync(version);
        }

        return model?.ModelPath;
    }

    /// <inheritdoc/>
    public async Task<(Stream Stream, string ContentType)?> DownloadModelFileAsync(string version, string fileName)
    {
        var model = await _modelMetadataRepository.GetByVersionAsync(version);
        if (model == null)
        {
            return null;
        }

        return await _fileStorageService.DownloadAsync(fileName, $"models/{version}");
    }

    /// <inheritdoc/>
    public async Task<(bool IsValid, string? ErrorMessage)> ValidateRetrainingRequirementsAsync()
    {
        // Check if at least one product has photos
        var productsWithPhotos = await _productPhotoRepository
            .GetAll()
            .Select(pp => pp.ProductId)
            .Distinct()
            .CountAsync();

        if (productsWithPhotos == 0)
        {
            return (false, "No se puede entrenar el modelo: ningún producto tiene fotos. Sube fotos primero.");
        }

        var totalPhotos = await _productPhotoRepository.GetAll().CountAsync();
        if (totalPhotos < 10)
        {
            return (false, $"No se puede entrenar el modelo: solo hay {totalPhotos} fotos. Se recomiendan al menos 10.");
        }

        return (true, null);
    }

    /// <inheritdoc/>
    public async Task<Guid> InitiateModelRetrainingAsync(Guid initiatedBy)
    {
        // Validate requirements
        var (isValid, errorMessage) = await ValidateRetrainingRequirementsAsync();
        if (!isValid)
        {
            throw new InvalidOperationException(errorMessage);
        }

        // Check if training already in progress
        var isInProgress = await _trainingJobRepository.IsJobInProgressAsync();
        if (isInProgress)
        {
            throw new InvalidOperationException("Ya hay un entrenamiento en curso. Espera a que termine.");
        }

        // Create training job
        var job = new ModelTrainingJob
        {
            InitiatedBy = initiatedBy,
            Status = "Queued",
            ProgressPercentage = 0,
            CurrentStage = "Queued - waiting to start"
        };

        job = await _trainingJobRepository.AddAsync(job);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation(
            "Model training job {JobId} initiated by user {UserId}",
            job.Id, initiatedBy);

        // TODO: Trigger background service to process the job
        // For MVP, this will be a manual Python script execution
        // Background service implementation deferred to allow testing of the API structure

        return job.Id;
    }

    /// <inheritdoc/>
    public async Task<TrainingJobStatusDto?> GetTrainingJobStatusAsync(Guid jobId)
    {
        var job = await _trainingJobRepository.GetByIdAsync(jobId);
        return job != null ? MapJobToDto(job) : null;
    }

    /// <inheritdoc/>
    public async Task<TrainingJobStatusDto?> GetLatestTrainingJobAsync()
    {
        var job = await _trainingJobRepository.GetLatestJobAsync();
        return job != null ? MapJobToDto(job) : null;
    }

    /// <inheritdoc/>
    public async Task<bool> IsTrainingInProgressAsync()
    {
        return await _trainingJobRepository.IsJobInProgressAsync();
    }

    /// <inheritdoc/>
    public async Task<UploadTrainedModelResult> UploadTrainedModelAsync(
        UploadTrainedModelRequest request,
        Dictionary<string, byte[]> weightFiles,
        Guid uploadedBy)
    {
        try
        {
            // Validate version format
            if (string.IsNullOrEmpty(request.Version))
            {
                return new UploadTrainedModelResult
                {
                    Success = false,
                    ErrorMessage = "La versión del modelo es obligatoria."
                };
            }

            // Validate model topology
            if (string.IsNullOrEmpty(request.ModelTopologyJson))
            {
                return new UploadTrainedModelResult
                {
                    Success = false,
                    ErrorMessage = "El JSON de topología del modelo es obligatorio."
                };
            }

            // Validate weight files
            if (weightFiles == null || weightFiles.Count == 0)
            {
                return new UploadTrainedModelResult
                {
                    Success = false,
                    ErrorMessage = "Hace falta al menos un archivo de pesos."
                };
            }

            // Check if version already exists
            var existingModel = await _modelMetadataRepository.GetByVersionAsync(request.Version);
            if (existingModel != null)
            {
                return new UploadTrainedModelResult
                {
                    Success = false,
                    ErrorMessage = $"La versión {request.Version} ya existe. Usa otra versión."
                };
            }

            _logger.LogInformation(
                "Uploading trained model {Version} by user {UserId}. Files: {FileCount}",
                request.Version, uploadedBy, weightFiles.Count);

            var modelFolder = $"models/{request.Version}";

            // Save model.json via file storage service (S3 in production)
            using (var modelJsonStream = new MemoryStream(System.Text.Encoding.UTF8.GetBytes(request.ModelTopologyJson)))
            {
                await _fileStorageService.UploadExactAsync(modelJsonStream, "model.json", "application/json", modelFolder);
            }

            // Save weight files via file storage service
            foreach (var (fileName, fileData) in weightFiles)
            {
                if (fileName.Contains("..") || fileName.Contains("/") || fileName.Contains("\\"))
                {
                    _logger.LogWarning("Invalid weight file name rejected: {FileName}", fileName);
                    continue;
                }

                using var weightStream = new MemoryStream(fileData);
                var contentType = fileName.EndsWith(".json") ? "application/json" : "application/octet-stream";
                await _fileStorageService.UploadExactAsync(weightStream, fileName, contentType, modelFolder);
            }

            // Deactivate previous active model
            var currentActive = await _modelMetadataRepository.GetActiveModelAsync();
            if (currentActive != null)
            {
                currentActive.IsActive = false;
                await _modelMetadataRepository.UpdateAsync(currentActive);
            }

            // Create new model metadata
            var accuracyJson = System.Text.Json.JsonSerializer.Serialize(new
            {
                trainingAccuracy = request.TrainingAccuracy,
                validationAccuracy = request.ValidationAccuracy,
                trainingDurationSeconds = request.TrainingDurationSeconds
            });

            var newModel = new ModelMetadata
            {
                Version = request.Version,
                TrainedAt = DateTime.UtcNow,
                ModelPath = modelFolder,
                AccuracyMetrics = accuracyJson,
                TotalPhotosUsed = request.TotalPhotosUsed,
                TotalProductsUsed = request.TotalProductsUsed,
                IsActive = true
            };

            await _modelMetadataRepository.AddAsync(newModel);
            await _unitOfWork.SaveChangesAsync();

            _logger.LogInformation(
                "Model {Version} uploaded successfully. Accuracy: {Accuracy}%",
                request.Version, request.ValidationAccuracy);

            return new UploadTrainedModelResult
            {
                Success = true,
                Version = request.Version,
                Metadata = MapToDto(newModel)
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error uploading trained model {Version}", request.Version);
            return new UploadTrainedModelResult
            {
                Success = false,
                ErrorMessage = $"No se pudo subir el modelo: {ex.Message}"
            };
        }
    }

    /// <inheritdoc/>
    public async Task<TrainingDatasetResponse> GetTrainingDatasetAsync()
    {
        // Get all active products with photos
        var productsWithPhotos = await _productRepository
            .GetAll()
            .Where(p => p.IsActive && p.SystemProductKind == null)
            .Include(p => p.Photos)
            .Where(p => p.Photos.Any())
            .ToListAsync();

        var photos = new List<TrainingPhotoDto>();
        var classLabels = new HashSet<string>();

        foreach (var product in productsWithPhotos)
        {
            // Use SKU as class label (immutable, unique) instead of Name (mutable, may have duplicates)
            classLabels.Add(product.SKU);

            foreach (var photo in product.Photos)
            {
                // Use the file storage service to get the correct URL for the photo file
                var photoUrl = await _fileStorageService.GetUrlAsync(photo.FileName, "products");
                
                photos.Add(new TrainingPhotoDto
                {
                    ProductId = product.Id,
                    ProductSku = product.SKU,
                    ProductName = product.Name,
                    PhotoId = photo.Id,
                    PhotoUrl = photoUrl
                });
            }
        }

        return new TrainingDatasetResponse
        {
            Photos = photos,
            TotalPhotos = photos.Count,
            TotalProducts = productsWithPhotos.Count,
            ClassLabels = classLabels.OrderBy(l => l).ToList()
        };
    }

    /// <inheritdoc/>
    public async Task<HashSet<Guid>?> GetAccessibleProductIdsAsync(Guid? userId, bool isAdmin)
    {
        // Admins can access all products
        if (isAdmin)
        {
            return null;
        }

        // Anonymous users or users without ID cannot access any products
        if (!userId.HasValue)
        {
            return new HashSet<Guid>();
        }

        // Get operator's assigned points of sale
        var assignedPosIds = await _userPointOfSaleService.GetAssignedPointOfSaleIdsAsync(userId.Value);
        
        if (assignedPosIds.Count == 0)
        {
            _logger.LogDebug("User {UserId} has no assigned points of sale", userId.Value);
            return new HashSet<Guid>();
        }

        // Get products that have inventory at the assigned points of sale
        var accessibleProductIds = await _inventoryRepository.GetProductIdsWithInventoryAtPointsOfSaleAsync(assignedPosIds);
        
        _logger.LogDebug(
            "User {UserId} can access {ProductCount} products from {PosCount} points of sale",
            userId.Value, accessibleProductIds.Count, assignedPosIds.Count);
        
        return accessibleProductIds;
    }

    private static ModelMetadataDto MapToDto(ModelMetadata model)
    {
        return new ModelMetadataDto
        {
            Version = model.Version,
            TrainedAt = model.TrainedAt,
            ModelPath = model.ModelPath,
            AccuracyMetrics = model.AccuracyMetrics,
            TotalPhotosUsed = model.TotalPhotosUsed,
            TotalProductsUsed = model.TotalProductsUsed,
            IsActive = model.IsActive
        };
    }

    private static TrainingJobStatusDto MapJobToDto(ModelTrainingJob job)
    {
        return new TrainingJobStatusDto
        {
            JobId = job.Id,
            Status = job.Status,
            ProgressPercentage = job.ProgressPercentage,
            CurrentStage = job.CurrentStage,
            StartedAt = job.StartedAt,
            CompletedAt = job.CompletedAt,
            ErrorMessage = job.ErrorMessage,
            ResultModelVersion = job.ResultModelVersion,
            DurationSeconds = job.DurationSeconds
        };
    }

    /// <inheritdoc/>
    public async Task SaveEmbeddingAsync(SaveEmbeddingRequest request)
    {
        if (request.Vector == null || request.Vector.Length != EmbeddingVectorLength)
        {
            throw new ArgumentException($"El vector de embedding tiene que tener exactamente {EmbeddingVectorLength} elementos.");
        }

        // Upsert: delete existing embedding for this photo, then insert new one
        await _embeddingRepository.DeleteByPhotoIdAsync(request.PhotoId);

        var embedding = new ProductPhotoEmbedding
        {
            ProductPhotoId = request.PhotoId,
            ProductId = request.ProductId,
            ProductSku = request.Sku,
            EmbeddingVector = JsonSerializer.Serialize(request.Vector)
        };

        await _embeddingRepository.AddAsync(embedding);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogDebug("Saved embedding for photo {PhotoId} (product {ProductId})", request.PhotoId, request.ProductId);
    }

    /// <inheritdoc/>
    public async Task DeleteEmbeddingAsync(Guid photoId)
    {
        await _embeddingRepository.DeleteByPhotoIdAsync(photoId);
        await _unitOfWork.SaveChangesAsync();
    }

    /// <inheritdoc/>
    public async Task DeleteAllEmbeddingsAsync()
    {
        await _embeddingRepository.DeleteAllAsync();
        _logger.LogInformation("All photo embeddings deleted");
    }

    /// <inheritdoc/>
    public async Task<EmbeddingsIndexResponse> GetAllEmbeddingsAsync()
    {
        var embeddings = await _embeddingRepository.GetAllAsync();
        var lastUpdated = embeddings.Count > 0 ? embeddings.Max(e => e.UpdatedAt) : (DateTime?)null;

        var dtos = embeddings.Select(e =>
        {
            var vector = JsonSerializer.Deserialize<float[]>(e.EmbeddingVector) ?? Array.Empty<float>();
            return new EmbeddingDto
            {
                PhotoId = e.ProductPhotoId,
                ProductId = e.ProductId,
                Sku = e.ProductSku,
                Vector = vector
            };
        }).ToList();

        return new EmbeddingsIndexResponse
        {
            Embeddings = dtos,
            LastUpdated = lastUpdated,
            Count = dtos.Count
        };
    }

    /// <inheritdoc/>
    public async Task<EmbeddingsStatusResponse> GetEmbeddingsStatusAsync()
    {
        var count = await _embeddingRepository.GetCountAsync();
        var lastUpdated = await _embeddingRepository.GetLastUpdatedAsync();

        return new EmbeddingsStatusResponse
        {
            Count = count,
            LastUpdated = lastUpdated
        };
    }
}
