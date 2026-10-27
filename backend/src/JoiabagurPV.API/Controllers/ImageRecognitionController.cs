using JoiabagurPV.Application.DTOs.ImageRecognition;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.API.Filters;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Text.Json.Nodes;

namespace JoiabagurPV.API.Controllers;

/// <summary>
/// Controller for image recognition and ML model management operations.
/// Product-photo image recognition is withdrawn; endpoints return 410 Gone.
/// </summary>
[ApiController]
[Route("api/image-recognition")]
[Authorize]
[ServiceFilter(typeof(ImageRecognitionWithdrawnFilter))]
[Obsolete("Product-photo image recognition is withdrawn. Endpoints return 410 Gone.")]
public class ImageRecognitionController : ControllerBase
{
    private readonly IImageRecognitionService _imageRecognitionService;
    private readonly IModelHealthService _modelHealthService;
    private readonly ICurrentUserService _currentUserService;
    private readonly ILogger<ImageRecognitionController> _logger;

    public ImageRecognitionController(
        IImageRecognitionService imageRecognitionService,
        IModelHealthService modelHealthService,
        ICurrentUserService currentUserService,
        ILogger<ImageRecognitionController> logger)
    {
        _imageRecognitionService = imageRecognitionService;
        _modelHealthService = modelHealthService;
        _currentUserService = currentUserService;
        _logger = logger;
    }

    /// <summary>
    /// Gets the active model metadata.
    /// Used by frontend to check model version and decide whether to download.
    /// </summary>
    /// <returns>Model metadata if active model exists.</returns>
    [HttpGet("model/metadata")]
    [ProducesResponseType(typeof(ModelMetadataDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<ModelMetadataDto>> GetModelMetadata()
    {
        var metadata = await _imageRecognitionService.GetActiveModelMetadataAsync();

        if (metadata == null)
        {
            return NotFound(new { message = "No hay un modelo de IA. Entrena un modelo inicial." });
        }

        return Ok(metadata);
    }

    /// <summary>
    /// Gets model health metrics and alert level (admin only).
    /// Used by admin dashboard to display model status and determine if retraining is needed.
    /// </summary>
    /// <returns>Model health metrics with alert level.</returns>
    [HttpGet("model/health")]
    [ProducesResponseType(typeof(ModelHealthDto), StatusCodes.Status200OK)]
    public async Task<ActionResult<ModelHealthDto>> GetModelHealth()
    {
        var health = await _modelHealthService.GetModelHealthAsync();
        return Ok(health);
    }

    /// <summary>
    /// Gets all model versions (training history).
    /// </summary>
    /// <returns>List of all model versions ordered by training date.</returns>
    [HttpGet("model/versions")]
    [ProducesResponseType(typeof(List<ModelMetadataDto>), StatusCodes.Status200OK)]
    public async Task<ActionResult<List<ModelMetadataDto>>> GetModelVersions()
    {
        var versions = await _imageRecognitionService.GetAllModelVersionsAsync();
        return Ok(versions);
    }

    /// <summary>
    /// Initiates model retraining (admin only).
    /// Creates an async job and returns immediately with job ID.
    /// </summary>
    /// <returns>Training job ID for status polling.</returns>
    [HttpPost("retrain")]
    [ProducesResponseType(typeof(object), StatusCodes.Status202Accepted)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> InitiateRetraining()
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized();
        }

        try
        {
            var jobId = await _imageRecognitionService.InitiateModelRetrainingAsync(_currentUserService.UserId.Value);

            _logger.LogInformation(
                "Model retraining initiated by user {UserId}, job {JobId}",
                _currentUserService.UserId.Value, jobId);

            return Accepted(new
            {
                jobId,
                message = "Model retraining job created successfully.",
                statusUrl = $"/api/image-recognition/retrain/status/{jobId}",
                estimatedDuration = "30-45 minutes"
            });
        }
        catch (InvalidOperationException ex) when (ex.Message.Contains("already in progress"))
        {
            return Conflict(new { message = ex.Message });
        }
        catch (InvalidOperationException ex)
        {
            return BadRequest(new { message = ex.Message });
        }
    }

    /// <summary>
    /// Gets the status of a training job.
    /// </summary>
    /// <param name="jobId">Training job ID.</param>
    /// <returns>Job status with progress information.</returns>
    [HttpGet("retrain/status/{jobId}")]
    [ProducesResponseType(typeof(TrainingJobStatusDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<TrainingJobStatusDto>> GetTrainingStatus(Guid jobId)
    {
        var status = await _imageRecognitionService.GetTrainingJobStatusAsync(jobId);

        if (status == null)
        {
            return NotFound(new { message = "Trabajo de entrenamiento no encontrado." });
        }

        return Ok(status);
    }

    /// <summary>
    /// Gets the latest training job status.
    /// </summary>
    /// <returns>Latest job status if exists.</returns>
    [HttpGet("retrain/latest")]
    [ProducesResponseType(typeof(TrainingJobStatusDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<TrainingJobStatusDto>> GetLatestTrainingStatus()
    {
        var status = await _imageRecognitionService.GetLatestTrainingJobAsync();

        if (status == null)
        {
            return NotFound(new { message = "No hay trabajos de entrenamiento." });
        }

        return Ok(status);
    }

    /// <summary>
    /// Downloads the active model files (TensorFlow.js format).
    /// Returns the model directory path for frontend to download model.json and .bin files.
    /// </summary>
    /// <returns>Model file path if available.</returns>
    [HttpGet("model")]
    [ProducesResponseType(typeof(object), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetModel()
    {
        var modelPath = await _imageRecognitionService.GetModelFilePathAsync();

        if (string.IsNullOrEmpty(modelPath))
        {
            return NotFound(new { message = "No hay un modelo disponible. Entrena un modelo primero." });
        }

        // Return model path for frontend to construct download URLs
        // Frontend will fetch model.json and .bin files separately
        // Get metadata for additional info
        var metadata = await _imageRecognitionService.GetActiveModelMetadataAsync();
        
        return Ok(new
        {
            modelPath,
            version = metadata?.Version,
            trainedAt = metadata?.TrainedAt,
            modelJsonUrl = $"/api/image-recognition/model/files/{metadata?.Version}/model.json",
            message = "Model available for download"
        });
    }

    /// <summary>
    /// Downloads a specific model file (model.json or .bin files).
    /// </summary>
    /// <param name="version">Model version.</param>
    /// <param name="fileName">File name (e.g., model.json, group1-shard1of1.bin).</param>
    /// <returns>Model file content.</returns>
    [HttpGet("model/files/{version}/{fileName}")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetModelFile(string version, string fileName)
    {
        // Validate file name to prevent directory traversal
        if (fileName.Contains("..") || fileName.Contains("/") || fileName.Contains("\\"))
        {
            return BadRequest(new { message = "Nombre de archivo no válido." });
        }

        var result = await _imageRecognitionService.DownloadModelFileAsync(version, fileName);
        if (result == null)
        {
            _logger.LogWarning("Model file not found: models/{Version}/{FileName}", version, fileName);
            return NotFound(new { message = "Archivo del modelo no encontrado." });
        }

        var (stream, contentType) = result.Value;

        Response.Headers["Cache-Control"] = "no-store";

        // Non-JSON files: stream directly to client
        if (!string.Equals(fileName, "model.json", StringComparison.OrdinalIgnoreCase))
        {
            return File(stream, contentType, fileName);
        }

        // For model.json: read into string so we can inspect/transform for backward compatibility.
        // The stream is fully consumed here and disposed; all return paths below use Content().
        string text;
        await using (stream)
        {
            using var reader = new StreamReader(stream);
            text = await reader.ReadToEndAsync();
        }

        try
        {
            var node = JsonNode.Parse(text);

            var hasModelTopology = node?["modelTopology"] != null;
            var hasWeightsManifest = node?["weightsManifest"] != null;

            if (!hasModelTopology || !hasWeightsManifest)
            {
                var weightsResult = await _imageRecognitionService.DownloadModelFileAsync(version, "weights_manifest.json");
                if (weightsResult == null)
                {
                    _logger.LogWarning("Legacy model.json detected but weights_manifest.json missing for version {Version}", version);
                }
                else
                {
                    using var weightsReader = new StreamReader(weightsResult.Value.Stream);
                    var weightsText = await weightsReader.ReadToEndAsync();
                    var weightsNode = JsonNode.Parse(weightsText);

                    var weightsArray = weightsNode as JsonArray;
                    if (weightsArray != null)
                    {
                        var wrapped = new JsonObject
                        {
                            ["format"] = "layers-model",
                            ["generatedBy"] = "jpv",
                            ["convertedBy"] = null,
                            ["modelTopology"] = node,
                            ["weightsManifest"] = new JsonArray
                            {
                                new JsonObject
                                {
                                    ["paths"] = new JsonArray("weights.bin"),
                                    ["weights"] = weightsArray
                                }
                            }
                        };

                        return Content(wrapped.ToJsonString(), "application/json");
                    }

                    _logger.LogWarning("weights_manifest.json was not a JSON array for version {Version}", version);
                }
            }

            return Content(text, "application/json");
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to apply legacy model.json wrapper for version {Version}", version);
            return NotFound(new { message = "Error al procesar el archivo del modelo." });
        }
    }

    /// <summary>
    /// Uploads a browser-trained model (admin only).
    /// Receives model.json and weight files from browser-based TensorFlow.js training.
    /// </summary>
    /// <returns>Upload result with new model metadata.</returns>
    [HttpPost("upload-trained-model")]
    [ProducesResponseType(typeof(UploadTrainedModelResult), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [RequestSizeLimit(100_000_000)] // 100MB limit for model files
    public async Task<ActionResult<UploadTrainedModelResult>> UploadTrainedModel([FromForm] UploadTrainedModelFormRequest request)
    {
        if (!_currentUserService.UserId.HasValue)
        {
            return Unauthorized();
        }

        // Validate request
        if (string.IsNullOrEmpty(request.Version))
        {
            return BadRequest(new { message = "La versión del modelo es obligatoria." });
        }

        if (string.IsNullOrEmpty(request.ModelTopologyJson))
        {
            return BadRequest(new { message = "El JSON de topología del modelo es obligatorio." });
        }

        if (request.WeightFiles == null || request.WeightFiles.Count == 0)
        {
            return BadRequest(new { message = "Hace falta al menos un archivo de pesos." });
        }

        // Read weight files
        var weightFiles = new Dictionary<string, byte[]>();
        foreach (var file in request.WeightFiles)
        {
            using var memoryStream = new MemoryStream();
            await file.CopyToAsync(memoryStream);
            weightFiles[file.FileName] = memoryStream.ToArray();
        }

        var uploadRequest = new UploadTrainedModelRequest
        {
            Version = request.Version,
            ModelTopologyJson = request.ModelTopologyJson,
            TrainingAccuracy = request.TrainingAccuracy,
            ValidationAccuracy = request.ValidationAccuracy,
            TotalPhotosUsed = request.TotalPhotosUsed,
            TotalProductsUsed = request.TotalProductsUsed,
            TrainingDurationSeconds = request.TrainingDurationSeconds
        };

        var result = await _imageRecognitionService.UploadTrainedModelAsync(
            uploadRequest,
            weightFiles,
            _currentUserService.UserId.Value);

        if (!result.Success)
        {
            return BadRequest(new { message = result.ErrorMessage });
        }

        _logger.LogInformation(
            "Browser-trained model {Version} uploaded by user {UserId}",
            result.Version, _currentUserService.UserId.Value);

        return Ok(result);
    }

    /// <summary>
    /// Gets the class labels and product mappings for inference.
    /// Returns only the minimal data needed to map predictions to products.
    /// Accessible to all authenticated users (operators can use image recognition).
    /// For operators, filters to only show products available at their assigned points of sale.
    /// </summary>
    /// <returns>Class labels with product ID, SKU, and name mappings.</returns>
    [HttpGet("model/class-labels")]
    [ProducesResponseType(typeof(ClassLabelsResponse), StatusCodes.Status200OK)]
    public async Task<ActionResult<ClassLabelsResponse>> GetClassLabels()
    {
        var dataset = await _imageRecognitionService.GetTrainingDatasetAsync();
        
        // Get accessible product IDs for the current user (operators see filtered products)
        var accessibleProductIds = await _imageRecognitionService.GetAccessibleProductIdsAsync(
            _currentUserService.UserId,
            _currentUserService.IsAdmin);
        
        // Build unique product list from photos (for inference mapping)
        // Filter by accessible products for operators
        var filteredPhotos = accessibleProductIds == null 
            ? dataset.Photos 
            : dataset.Photos.Where(p => accessibleProductIds.Contains(p.ProductId)).ToList();
        
        // Use ProductSku as dictionary key (immutable, unique) for stable model-to-product mapping
        var productMap = filteredPhotos
            .GroupBy(p => p.ProductId)
            .Select(g => g.First())
            .ToDictionary(p => p.ProductSku, p => new ProductLabelMapping
            {
                ProductId = p.ProductId,
                ProductSku = p.ProductSku,
                ProductName = p.ProductName,
                PhotoUrl = p.PhotoUrl
            });
        
        // Filter class labels (SKUs) to only include products the user can access
        var filteredClassLabels = accessibleProductIds == null
            ? dataset.ClassLabels
            : dataset.ClassLabels.Where(sku => productMap.ContainsKey(sku)).ToList();
        
        return Ok(new ClassLabelsResponse
        {
            ClassLabels = filteredClassLabels,
            ProductMappings = productMap
        });
    }

    /// <summary>
    /// Gets the training dataset for browser-based model training.
    /// Returns all active products with their photos for client-side training.
    /// </summary>
    /// <returns>Training dataset with photo metadata and URLs.</returns>
    [HttpGet("training-dataset")]
    [ProducesResponseType(typeof(TrainingDatasetResponse), StatusCodes.Status200OK)]
    public async Task<ActionResult<TrainingDatasetResponse>> GetTrainingDataset()
    {
        var dataset = await _imageRecognitionService.GetTrainingDatasetAsync();
        
        if (dataset.TotalPhotos == 0)
        {
            return Ok(new
            {
                dataset.Photos,
                dataset.TotalPhotos,
                dataset.TotalProducts,
                dataset.ClassLabels,
                message = "No hay fotos de producto para entrenar. Sube fotos primero."
            });
        }

        return Ok(dataset);
    }

    /// <summary>
    /// Saves (or updates) the MobileNetV2 embedding for a product photo.
    /// Vector must have exactly 1280 elements.
    /// </summary>
    [HttpPost("embeddings")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<IActionResult> SaveEmbedding([FromBody] SaveEmbeddingRequest request)
    {
        if (request.Vector == null || request.Vector.Length != 1280)
        {
            return BadRequest(new { message = "El vector de embedding tiene que tener exactamente 1280 elementos." });
        }

        try
        {
            await _imageRecognitionService.SaveEmbeddingAsync(request);
            return NoContent();
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new { message = ex.Message });
        }
    }

    /// <summary>
    /// Deletes the embedding for a specific product photo.
    /// </summary>
    [HttpDelete("embeddings/{photoId:guid}")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    public async Task<IActionResult> DeleteEmbedding(Guid photoId)
    {
        await _imageRecognitionService.DeleteEmbeddingAsync(photoId);
        return NoContent();
    }

    /// <summary>
    /// Deletes all stored embeddings.
    /// </summary>
    [HttpDelete("embeddings")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    public async Task<IActionResult> DeleteAllEmbeddings()
    {
        await _imageRecognitionService.DeleteAllEmbeddingsAsync();
        return NoContent();
    }

    /// <summary>
    /// Returns all stored embeddings for client-side similarity search.
    /// </summary>
    [HttpGet("embeddings")]
    [ProducesResponseType(typeof(EmbeddingsIndexResponse), StatusCodes.Status200OK)]
    public async Task<ActionResult<EmbeddingsIndexResponse>> GetAllEmbeddings()
    {
        var result = await _imageRecognitionService.GetAllEmbeddingsAsync();
        return Ok(result);
    }

    /// <summary>
    /// Returns the count and last-updated timestamp of the embeddings index.
    /// Lightweight endpoint for staleness checks before downloading the full index.
    /// </summary>
    [HttpGet("embeddings/status")]
    [ProducesResponseType(typeof(EmbeddingsStatusResponse), StatusCodes.Status200OK)]
    public async Task<ActionResult<EmbeddingsStatusResponse>> GetEmbeddingsStatus()
    {
        var result = await _imageRecognitionService.GetEmbeddingsStatusAsync();
        return Ok(result);
    }
}

/// <summary>
/// Form request for uploading browser-trained model (multipart/form-data).
/// </summary>
public class UploadTrainedModelFormRequest
{
    /// <summary>
    /// Model version identifier (e.g., "v1_20260112").
    /// </summary>
    public string Version { get; set; } = string.Empty;

    /// <summary>
    /// Model topology JSON (model.json content).
    /// </summary>
    public string ModelTopologyJson { get; set; } = string.Empty;

    /// <summary>
    /// Training accuracy percentage (0-100).
    /// </summary>
    public double TrainingAccuracy { get; set; }

    /// <summary>
    /// Validation accuracy percentage (0-100).
    /// </summary>
    public double ValidationAccuracy { get; set; }

    /// <summary>
    /// Total photos used for training.
    /// </summary>
    public int TotalPhotosUsed { get; set; }

    /// <summary>
    /// Total products included in training.
    /// </summary>
    public int TotalProductsUsed { get; set; }

    /// <summary>
    /// Training duration in seconds.
    /// </summary>
    public int TrainingDurationSeconds { get; set; }

    /// <summary>
    /// Weight files (.bin files).
    /// </summary>
    public List<IFormFile> WeightFiles { get; set; } = new();
}
