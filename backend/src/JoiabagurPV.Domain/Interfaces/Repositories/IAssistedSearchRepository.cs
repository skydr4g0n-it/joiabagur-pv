namespace JoiabagurPV.Domain.Interfaces.Repositories;

/// <summary>
/// Reads that back assisted search: authoritative hydration of retrieved candidates, and the
/// degraded lexical searcher. Implementation lives in Infrastructure.
/// </summary>
/// <remarks>
/// Both operations are set-based on purpose. Hydrating through the catalog service would resolve
/// inventory and photos one product at a time, which at a full candidate window is two orders of
/// magnitude of round trips inside a request competing with the retrieval time budget.
/// </remarks>
public interface IAssistedSearchRepository
{
    /// <summary>
    /// Hydrates the given candidates against the catalog, keeping only what the point of sale
    /// actually carries.
    /// </summary>
    /// <remarks>
    /// A row comes back only when the product is active and has an active inventory record at
    /// <paramref name="pointOfSaleId"/>. A quantity of zero is kept: availability weights a
    /// result, it never removes it.
    ///
    /// Order is not meaningful here. The caller re-orders by the relevance the retriever
    /// produced, which this query knows nothing about.
    /// </remarks>
    Task<IReadOnlyList<AssistedSearchRow>> HydrateAsync(
        IReadOnlyList<Guid> productIds,
        Guid pointOfSaleId,
        CancellationToken cancellationToken);

    /// <summary>
    /// Degraded searcher: Spanish full-text over the catalog, scoped to one point of sale,
    /// ordered by lexical relevance.
    /// </summary>
    /// <param name="terms">
    /// Query terms already split and sanitised. They are combined so that matching <em>any</em>
    /// of them is enough — a natural-language query never appears verbatim in a product name,
    /// and requiring all terms would return an empty list on every degraded search.
    /// </param>
    Task<IReadOnlyList<AssistedSearchRow>> SearchLexicalAsync(
        IReadOnlyList<string> terms,
        Guid pointOfSaleId,
        int take,
        CancellationToken cancellationToken);

    /// <summary>Whether a point of sale exists and is active.</summary>
    Task<bool> IsPointOfSaleActiveAsync(Guid pointOfSaleId, CancellationToken cancellationToken);
}

/// <summary>
/// One hydrated product at one point of sale, as the queries project it. Carries the file name
/// of the primary photo rather than its URL: resolving URLs is the caller's job and happens in
/// one pass over the whole page.
/// </summary>
public sealed class AssistedSearchRow
{
    public Guid ProductId { get; init; }

    public string Sku { get; init; } = string.Empty;

    public string Name { get; init; } = string.Empty;

    public decimal Price { get; init; }

    /// <summary>Units at the point of sale of the search. May be zero.</summary>
    public int Quantity { get; init; }

    public string? PrimaryPhotoFileName { get; init; }

    public string? CollectionName { get; init; }
}
