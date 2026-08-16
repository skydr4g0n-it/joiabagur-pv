using JoiabagurPV.Application.DTOs.Products;

namespace JoiabagurPV.Application.Exceptions;

/// <summary>
/// Raised when a membership declaration names products that already belong to another family.
/// </summary>
/// <remarks>
/// Carries the clashing products rather than a sentence about them. The controller translates this
/// type into 409 — by type, not by sniffing a message, which is how the rest of this codebase's
/// older controllers decide and how they end up coupled to wording. The conflicts travel with it so
/// the response can name which products clash and which family holds each of them: a rejection that
/// only says "conflict" leaves the caller to find the offending row among twenty declared members.
/// </remarks>
public class ProductFamilyConflictException : Exception
{
    public ProductFamilyConflictException(IReadOnlyList<ProductFamilyConflictDto> conflicts)
        : base(BuildMessage(conflicts))
    {
        Conflicts = conflicts;
    }

    /// <summary>The products that already belong elsewhere, with the family that holds them.</summary>
    public IReadOnlyList<ProductFamilyConflictDto> Conflicts { get; }

    private static string BuildMessage(IReadOnlyList<ProductFamilyConflictDto> conflicts) =>
        "Estos productos ya pertenecen a otra familia: "
        + string.Join(", ", conflicts.Select(c => $"{c.ProductId} → «{c.FamilyName}» ({c.FamilyId})"));
}
