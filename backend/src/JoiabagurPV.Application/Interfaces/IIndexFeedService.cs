using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>Indexing feeds: catalog and POS availability.</summary>
public interface IIndexFeedService
{
    Task<IndexFeedPageDto> GetCatalogPageAsync(
        DateTime? since,
        Guid? sinceId,
        CancellationToken cancellationToken);

    Task<IndexFeedPageDto> GetPosAvailabilityPageAsync(
        DateTime? since,
        Guid? sinceId,
        CancellationToken cancellationToken);
}
