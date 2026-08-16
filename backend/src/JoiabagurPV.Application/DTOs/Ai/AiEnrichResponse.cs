namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// One product's proposed attributes, as returned by jbg-ai.
/// </summary>
/// <remarks>
/// <para>
/// The four sensitive fields — <see cref="PieceType"/>, <see cref="Materials"/>,
/// <see cref="StoneType"/> and <see cref="SizeLabel"/> — are the ones whose error reaches a
/// customer, and each arrives individually so its provenance can be judged individually.
/// </para>
/// <para>
/// <see cref="FamilyId"/> and <see cref="VariantLabel"/> are part of the contract and are
/// <strong>deliberately ignored</strong> by this side: the product family is a business entity
/// with its own capability, and holding a second opinion about it here would create two truths
/// about the same thing.
/// </para>
/// </remarks>
public class AiProposedProfile
{
    /// <summary>Identifier of the product this proposal describes.</summary>
    public required string ProductId { get; set; }

    /// <summary>SKU of that product.</summary>
    public required string Sku { get; set; }

    /// <summary>Proposed display title. Not applied to the catalog by this capability.</summary>
    public AiProposedText? Title { get; set; }

    /// <summary>Proposed description. Not applied to the catalog by this capability.</summary>
    public AiProposedText? Description { get; set; }

    /// <summary>Kind of piece. Sensitive.</summary>
    public AiProposedText? PieceType { get; set; }

    /// <summary>Materials, as a list. Sensitive.</summary>
    public AiProposedList Materials { get; set; } = new();

    /// <summary>Stone, when the piece has one. Sensitive.</summary>
    public AiProposedText? StoneType { get; set; }

    /// <summary>Size label. Sensitive.</summary>
    public AiProposedText? SizeLabel { get; set; }

    /// <summary>Colour tags. Commercial.</summary>
    public AiProposedList ColorTags { get; set; } = new();

    /// <summary>Style tags. Commercial.</summary>
    public AiProposedList StyleTags { get; set; } = new();

    /// <summary>Occasion tags. Commercial.</summary>
    public AiProposedList OccasionTags { get; set; } = new();

    /// <summary>Family hint. Ignored here; the family belongs to its own capability.</summary>
    public AiProposedText? FamilyId { get; set; }

    /// <summary>Variant hint. Ignored here, for the same reason.</summary>
    public AiProposedText? VariantLabel { get; set; }

    /// <summary>Anything the extractor wants to flag about this product.</summary>
    public List<string> Warnings { get; set; } = [];
}

/// <summary>
/// Catalog enrichment response from jbg-ai.
/// </summary>
public class AiEnrichResponse
{
    /// <summary>One proposal per requested product.</summary>
    public List<AiProposedProfile> Profiles { get; set; } = [];

    /// <summary>Token usage reported by the service.</summary>
    public AiUsage Usage { get; set; } = new();

    /// <summary>
    /// Version of the extraction prompt behind this batch.
    /// </summary>
    /// <remarks>
    /// Persisted with every profile. Cheap to carry and impossible to reconstruct afterwards,
    /// which is the whole argument for it: the delivery is expected to show the measured effect
    /// of one prompt version against the next, and that comparison needs the label to have been
    /// recorded at the time.
    /// </remarks>
    public string PromptVersion { get; set; } = string.Empty;

    /// <summary>Correlation identifier echoed by the service.</summary>
    public string TraceId { get; set; } = string.Empty;
}

/// <summary>
/// Token usage of a generative call, as the contract reports it.
/// </summary>
public class AiUsage
{
    /// <summary>Tokens consumed by the prompt.</summary>
    public int PromptTokens { get; set; }

    /// <summary>Tokens produced by the model.</summary>
    public int CompletionTokens { get; set; }

    /// <summary>Sum of both.</summary>
    public int TotalTokens { get; set; }

    /// <summary>Provider model identifier, null while the service is stubbed.</summary>
    public string? Model { get; set; }
}
