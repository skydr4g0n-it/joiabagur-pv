using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>Indexing feeds: catalog and POS availability.</summary>
public interface IIndexFeedService
{
    Task<IndexFeedPageDto> GetCatalogPageAsync(
        DateTime? since,
        Guid? sinceId,
        CancellationToken cancellationToken);

    /// <remarks>
    /// Returns the derived page type on purpose: System.Text.Json serialises by the declared
    /// type, so widening this to the base would silently drop <c>computedAsOf</c> from the wire.
    /// </remarks>
    Task<PosAvailabilityPageDto> GetPosAvailabilityPageAsync(
        DateTime? since,
        Guid? sinceId,
        CancellationToken cancellationToken);
}
