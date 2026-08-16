namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// What kind of jbg-ai route a call scope may be used on.
/// </summary>
/// <remarks>
/// Exists so the refusal can be made by the client rather than left to the reader of a nullable
/// point of sale. A null identifier says "there is none"; this says "and that is deliberate,
/// for this family of routes" — which is what makes sending it to retrieval a bug the client can
/// name instead of a null reference it happens to trip over.
/// </remarks>
public enum AiCallScopeKind
{
    /// <summary>Scoped to one point of sale: retrieval, sale assistance, inventory.</summary>
    PointOfSale = 1,

    /// <summary>Scoped to the whole catalog: enrichment, index synchronization.</summary>
    Catalog = 2
}
