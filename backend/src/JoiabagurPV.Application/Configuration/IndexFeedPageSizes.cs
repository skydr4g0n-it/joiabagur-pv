namespace JoiabagurPV.Application.Configuration;

/// <summary>
/// Server-fixed page sizes for the indexing feeds. Not the operator list caps, and not
/// <c>PaginationConstants.MaxPageSize</c>.
/// </summary>
public static class IndexFeedPageSizes
{
    /// <summary>Catalog feed. Fits an embedding batch; the client does not choose this.</summary>
    public const int Catalog = 50;

    /// <summary>
    /// POS availability feed. A service exception, not copyable to UI lists.
    /// </summary>
    public const int PosAvailability = 200;
}
