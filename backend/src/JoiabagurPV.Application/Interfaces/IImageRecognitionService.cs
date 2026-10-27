using JoiabagurPV.Application.DTOs.ImageRecognition;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>
/// Service interface for image recognition and ML model management operations.
/// Product-photo image recognition is withdrawn; HTTP endpoints return 410 Gone.
/// </summary>
[Obsolete("Product-photo image recognition is withdrawn. Endpoints return 410 Gone.")]
public interface IImageRecognitionService
{
    /// <summary>
    /// Gets the current active model metadata.
    /// </summary>
    /// <returns>Model metadata if active model exists, null otherwise.</returns>
    Task<ModelMetadataDto?> GetActiveModelMetadataAsync();

    /// <summary>
    /// Gets all model versions (training history).
    /// </summary>
    /// <returns>List of all model versions ordered by training date descending.</returns>
    Task<List<ModelMetadataDto>> GetAllModelVersionsAsync();

    /// <summary>
    /// Gets the model file path for serving to frontend.
    /// </summary>
    /// <param name="version">Optional version. If null, returns active model.</param>
    /// <returns>Model file path if found, null otherwise.</returns>
    Task<string?> GetModelFilePathAsync(string? version = null);

    /// <summary>
    /// Downloads a model file from storage.
    /// </summary>
    /// <param name="version">Model version.</param>
    /// <param name="fileName">File name (e.g., model.json, weights.bin).</param>
    /// <returns>File stream and content type, or null if not found.</returns>
    Task<(Stream Stream, string ContentType)?> DownloadModelFileAsync(string version, string fileName);

    /// <summary>
    /// Validates that model retraining requirements are met.
    /// </summary>
    /// <returns>Validation result with error message if invalid.</returns>
    Task<(bool IsValid, string? ErrorMessage)> ValidateRetrainingRequirementsAsync();

    /// <summary>
    /// Initiates model retraining as a background job.
    /// </summary>
    /// <param name="initiatedBy">User ID who initiated the training.</param>
    /// <returns>Training job ID.</returns>
    Task<Guid> InitiateModelRetrainingAsync(Guid initiatedBy);

    /// <summary>
    /// Gets the status of a training job.
    /// </summary>
    /// <param name="jobId">Training job ID.</param>
    /// <returns>Job status if found, null otherwise.</returns>
    Task<TrainingJobStatusDto?> GetTrainingJobStatusAsync(Guid jobId);

    /// <summary>
    /// Gets the latest training job.
    /// </summary>
    /// <returns>Latest job status if exists, null otherwise.</returns>
    Task<TrainingJobStatusDto?> GetLatestTrainingJobAsync();

    /// <summary>
    /// Checks if a training job is currently running.
    /// </summary>
    /// <returns>True if training in progress, false otherwise.</returns>
    Task<bool> IsTrainingInProgressAsync();

    /// <summary>
    /// Uploads a browser-trained model.
    /// </summary>
    /// <param name="request">Upload request with model data.</param>
    /// <param name="weightFiles">Weight file data (name -> bytes).</param>
    /// <param name="uploadedBy">User ID who uploaded the model.</param>
    /// <returns>Upload result.</returns>
    Task<UploadTrainedModelResult> UploadTrainedModelAsync(
        UploadTrainedModelRequest request,
        Dictionary<string, byte[]> weightFiles,
        Guid uploadedBy);

    /// <summary>
    /// Gets the training dataset for browser-based training.
    /// Returns all active products with their photos.
    /// </summary>
    /// <returns>Training dataset with photo metadata.</returns>
    Task<TrainingDatasetResponse> GetTrainingDatasetAsync();

    /// <summary>
    /// Gets the product IDs that a user can access based on their role and assigned points of sale.
    /// </summary>
    /// <param name="userId">The user ID (null for anonymous).</param>
    /// <param name="isAdmin">Whether the user is an administrator.</param>
    /// <returns>Set of accessible product IDs, or null if admin (has access to all).</returns>
    Task<HashSet<Guid>?> GetAccessibleProductIdsAsync(Guid? userId, bool isAdmin);

    /// <summary>
    /// Saves (or updates) the embedding for a photo. Validates vector length = 1280.
    /// </summary>
    Task SaveEmbeddingAsync(SaveEmbeddingRequest request);

    /// <summary>
    /// Deletes the embedding for a specific photo.
    /// </summary>
    Task DeleteEmbeddingAsync(Guid photoId);

    /// <summary>
    /// Deletes all stored embeddings.
    /// </summary>
    Task DeleteAllEmbeddingsAsync();

    /// <summary>
    /// Returns all stored embeddings with their deserialized vectors.
    /// </summary>
    Task<EmbeddingsIndexResponse> GetAllEmbeddingsAsync();

    /// <summary>
    /// Returns the count and last-updated timestamp of the embeddings index.
    /// </summary>
    Task<EmbeddingsStatusResponse> GetEmbeddingsStatusAsync();
}
