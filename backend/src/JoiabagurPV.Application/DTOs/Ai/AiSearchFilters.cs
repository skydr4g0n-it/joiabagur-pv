namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// Catalog-side filters for a retrieval request. Price and stock filtering stay on
/// the .NET side, which is the authority on both.
/// </summary>
public class AiSearchFilters
{
    /// <summary>Materials the caller wants matched, from the closed vocabulary.</summary>
    public List<string> Materials { get; set; } = [];

    /// <summary>Optional piece category.</summary>
    public string? Category { get; set; }

    /// <summary>Optional family the results must belong to.</summary>
    public string? FamilyId { get; set; }

    /// <summary>Products to leave out of the candidate set.</summary>
    public List<string> ExcludeProductIds { get; set; } = [];
}
