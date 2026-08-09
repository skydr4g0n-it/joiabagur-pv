namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// Optional retrieval diagnostics returned per candidate. Minimally filled while
/// jbg-ai serves stubs.
/// </summary>
public class AiDebugInfo
{
    /// <summary>Score contributed by the vector branch.</summary>
    public double? VectorScore { get; set; }

    /// <summary>Score contributed by the lexical branch.</summary>
    public double? LexicalScore { get; set; }

    /// <summary>Score contributed by a reranking stage, when one runs.</summary>
    public double? RerankScore { get; set; }

    /// <summary>Free-form diagnostic notes.</summary>
    public List<string> Notes { get; set; } = [];
}
