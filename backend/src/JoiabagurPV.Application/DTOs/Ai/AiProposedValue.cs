namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// Where a proposed value came from.
/// </summary>
/// <remarks>
/// The single most consequential field of the enrichment contract. The whole hybrid review
/// policy is expressed in terms of it: a sensitive attribute a model inferred needs a person to
/// vouch for it, and the same attribute produced by a deterministic normalization does not. The
/// contract was renegotiated to carry this precisely because without it that distinction cannot
/// be made at all.
/// </remarks>
public enum AiFieldSource
{
    /// <summary>A deterministic normalization produced it — a regex, a copied structured field.</summary>
    Rule = 1,

    /// <summary>A model produced it.</summary>
    Inferred = 2
}

/// <summary>
/// A single proposed text value with its confidence and provenance.
/// </summary>
public class AiProposedText
{
    /// <summary>The proposed value.</summary>
    public required string Value { get; set; }

    /// <summary>How confident the extractor is, in the range 0 to 1.</summary>
    public double Confidence { get; set; }

    /// <summary>Whether a rule or a model produced it.</summary>
    public AiFieldSource Source { get; set; }
}

/// <summary>
/// A proposed list value with its confidence and provenance.
/// </summary>
/// <remarks>
/// A list rather than a single value because a piece is routinely made of several materials,
/// and because an absence of evidence has to be expressible as an empty list rather than as a
/// default that would read like a finding.
/// </remarks>
public class AiProposedList
{
    /// <summary>The proposed values. Empty when there is no evidence.</summary>
    public List<string> Value { get; set; } = [];

    /// <inheritdoc cref="AiProposedText.Confidence"/>
    public double Confidence { get; set; }

    /// <inheritdoc cref="AiProposedText.Source"/>
    public AiFieldSource Source { get; set; }
}
