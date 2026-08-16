namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// One product handed to jbg-ai for enrichment.
/// </summary>
/// <remarks>
/// Only the raw catalog text travels. Price, stock and point-of-sale assignment are deliberately
/// absent: the service has no use for them and, by the boundary rule, no business holding them.
/// </remarks>
public class AiEnrichProductInput
{
    /// <summary>Identifier of the product in the business database.</summary>
    public required string ProductId { get; set; }

    /// <summary>Product SKU.</summary>
    public required string Sku { get; set; }

    /// <summary>Product name, when it has one.</summary>
    public string? Name { get; set; }

    /// <summary>Product description, when it has one.</summary>
    public string? Description { get; set; }

    /// <summary>Extra structured attributes, when the catalog has any.</summary>
    public Dictionary<string, string> RawAttributes { get; set; } = [];
}

/// <summary>
/// A batch of products to enrich.
/// </summary>
public class AiEnrichRequest
{
    /// <summary>
    /// Largest batch the frozen contract accepts in one call.
    /// </summary>
    /// <remarks>
    /// Mirrored from <c>MAX_BATCH_SIZE</c> in the contract rather than picked here. Sending more
    /// would be rejected by the service with a validation error after the round trip; rejecting
    /// it on this side turns that into an immediate, explainable answer.
    /// </remarks>
    public const int MaxBatchSize = 50;

    /// <summary>Products to enrich, at most <see cref="MaxBatchSize"/>.</summary>
    public List<AiEnrichProductInput> Products { get; set; } = [];

    /// <summary>Locale of the catalog text.</summary>
    public string Locale { get; set; } = "es-ES";
}
