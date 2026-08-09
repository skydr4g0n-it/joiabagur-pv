namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// Retrieval strategy requested from jbg-ai. Serialized as the lowercase string
/// the frozen contract declares.
/// </summary>
public enum AiRetrievalMode
{
    /// <summary>Vector and lexical branches fused. Contract default.</summary>
    Hybrid,

    /// <summary>Vector branch only.</summary>
    Vector,

    /// <summary>Lexical branch only.</summary>
    Lexical
}
