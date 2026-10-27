using JoiabagurPV.Domain.Interfaces.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JoiabagurPV.API.Controllers;

/// <summary>
/// Controller for serving uploaded files
/// </summary>
[ApiController]
[Route("api/files")]
[AllowAnonymous] // Files can be accessed without authentication for public display
public class FilesController : ControllerBase
{
    private readonly IFileStorageService _fileStorageService;
    private readonly ILogger<FilesController> _logger;

    public FilesController(
        IFileStorageService fileStorageService,
        ILogger<FilesController> logger)
    {
        _fileStorageService = fileStorageService;
        _logger = logger;
    }

    /// <summary>
    /// Get a file by folder and filename
    /// </summary>
    /// <param name="folder">Folder name (e.g., "products", "sales")</param>
    /// <param name="filename">The filename to retrieve</param>
    /// <returns>The file content</returns>
    [HttpGet("{folder}/{filename}")]
    public async Task<IActionResult> GetFile(string folder, string filename)
    {
        try
        {
            var result = await _fileStorageService.DownloadAsync(filename, folder);

            if (result == null)
            {
                _logger.LogWarning("File not found: {Folder}/{Filename}", folder, filename);
                return NotFound(new { message = "Archivo no encontrado" });
            }

            var (stream, contentType) = result.Value;
            
            return File(stream, contentType, enableRangeProcessing: true);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error retrieving file: {Folder}/{Filename}", folder, filename);
            return StatusCode(500, new { message = "Error al obtener el archivo" });
        }
    }

    /// <summary>
    /// Get a file from the root uploads directory (legacy support)
    /// </summary>
    /// <param name="filename">The filename to retrieve</param>
    /// <returns>The file content</returns>
    [HttpGet("{filename}")]
    public async Task<IActionResult> GetFileFromRoot(string filename)
    {
        try
        {
            var result = await _fileStorageService.DownloadAsync(filename, null);

            if (result == null)
            {
                _logger.LogWarning("File not found: {Filename}", filename);
                return NotFound(new { message = "Archivo no encontrado" });
            }

            var (stream, contentType) = result.Value;
            
            return File(stream, contentType, enableRangeProcessing: true);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error retrieving file: {Filename}", filename);
            return StatusCode(500, new { message = "Error al obtener el archivo" });
        }
    }
}
