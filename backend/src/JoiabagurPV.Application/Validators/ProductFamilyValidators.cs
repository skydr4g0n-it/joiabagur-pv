using FluentValidation;
using JoiabagurPV.Application.DTOs.Products;
using JoiabagurPV.Domain.Entities;

namespace JoiabagurPV.Application.Validators;

/// <summary>
/// Rules shared by every request that declares a list of family members.
/// </summary>
/// <remarks>
/// Both duplicate checks exist to fail here rather than at the database. The unique indexes would
/// catch them anyway, but as a rejected transaction with a constraint name in it — an error the
/// caller cannot act on. Caught in the request, they name the field that is wrong.
/// <para>
/// Messages are in Spanish, matching the product-area validators these sit beside: the review
/// screen that will surface them is a Spanish UI.
/// </para>
/// </remarks>
public static class ProductFamilyMemberRules
{
    /// <summary>
    /// Applies the member-list rules to whichever request carries the list.
    /// </summary>
    public static void ApplyTo<TRequest>(
        AbstractValidator<TRequest> validator,
        Func<TRequest, List<ProductFamilyMemberRequest>> members)
    {
        validator.RuleFor(request => members(request))
            .Must(list => list.All(member => member.ProductId != Guid.Empty))
            .WithMessage("Cada miembro debe indicar un producto");

        validator.RuleFor(request => members(request))
            .Must(list => list.Select(member => member.ProductId).Distinct().Count() == list.Count)
            .WithMessage("Un producto no puede aparecer dos veces en la misma familia");

        validator.RuleFor(request => members(request))
            .Must(NoDuplicateLabels)
            .WithMessage(
                "Dos variantes de la misma familia no pueden llevar la misma etiqueta. "
                + "Una etiqueta sin informar sí puede repetirse: significa que aún no se conoce");

        validator.RuleFor(request => members(request))
            .Must(list => list.All(member =>
                member.VariantLabel is null
                || member.VariantLabel.Length <= ProductFamilyMember.VariantLabelMaxLength))
            .WithMessage(
                $"La etiqueta de variante no puede exceder "
                + $"{ProductFamilyMember.VariantLabelMaxLength} caracteres");
    }

    /// <summary>
    /// Whether the declared labels are distinguishable.
    /// </summary>
    /// <remarks>
    /// Blank and absent labels are excluded before comparing, deliberately. "Not determined yet" is
    /// a legitimate state that any number of members may share — the database says the same thing by
    /// treating nulls as distinct — whereas two members both labelled "M" defeat the point of having
    /// a family at all. Compared case-insensitively so that "m" and "M" are caught here rather than
    /// slipping past into a sibling list nobody can read.
    /// </remarks>
    private static bool NoDuplicateLabels(List<ProductFamilyMemberRequest> members)
    {
        var labels = members
            .Select(member => member.VariantLabel?.Trim())
            .Where(label => !string.IsNullOrEmpty(label))
            .ToList();

        return labels.Distinct(StringComparer.OrdinalIgnoreCase).Count() == labels.Count;
    }
}

/// <summary>
/// Validator for creating a product family.
/// </summary>
public class CreateProductFamilyRequestValidator : AbstractValidator<CreateProductFamilyRequest>
{
    public CreateProductFamilyRequestValidator()
    {
        RuleFor(x => x.Name)
            .NotEmpty().WithMessage("El nombre de la familia es requerido")
            .MaximumLength(ProductFamily.NameMaxLength)
            .WithMessage($"El nombre no puede exceder {ProductFamily.NameMaxLength} caracteres");

        ProductFamilyMemberRules.ApplyTo(this, request => request.Members);
    }
}

/// <summary>
/// Validator for correcting a family's name and description.
/// </summary>
public class UpdateProductFamilyRequestValidator : AbstractValidator<UpdateProductFamilyRequest>
{
    public UpdateProductFamilyRequestValidator()
    {
        RuleFor(x => x.Name)
            .NotEmpty().WithMessage("El nombre de la familia es requerido")
            .MaximumLength(ProductFamily.NameMaxLength)
            .WithMessage($"El nombre no puede exceder {ProductFamily.NameMaxLength} caracteres");
    }
}

/// <summary>
/// Validator for declaring the complete membership of a family.
/// </summary>
/// <remarks>
/// An empty list is valid and is not an oversight: it is how a family is dissolved without being
/// deleted.
/// </remarks>
public class ReplaceFamilyMembersRequestValidator : AbstractValidator<ReplaceFamilyMembersRequest>
{
    public ReplaceFamilyMembersRequestValidator()
    {
        ProductFamilyMemberRules.ApplyTo(this, request => request.Members);
    }
}
