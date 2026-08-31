using FluentValidation;
using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Application.Validators;

/// <summary>
/// Validates a batch of approved families before any of it is written.
/// </summary>
/// <remarks>
/// Every rule here catches something the database would otherwise catch as a constraint error —
/// an answer nobody can act on. A product declared twice, a label repeated inside one family, an
/// empty family: all three are refused with a message naming the offender, which is the whole
/// difference between an error someone can fix and one they have to investigate.
/// </remarks>
public class ApplyFamilySuggestionsRequestValidator : AbstractValidator<ApplyFamilySuggestionsRequest>
{
    public ApplyFamilySuggestionsRequestValidator()
    {
        RuleFor(request => request.Families)
            .NotEmpty()
            .WithMessage("Debe aprobarse al menos una familia.")
            .Must(families => families.Count <= ApplyFamilySuggestionsRequest.MaxFamilies)
            .WithMessage(
                $"No se pueden aprobar más de {ApplyFamilySuggestionsRequest.MaxFamilies} familias " +
                "en una sola llamada.");

        RuleForEach(request => request.Families).SetValidator(new ApprovedFamilyRequestValidator());

        // Across families, not only within one. Declaring the same product in two approved
        // families would create the first and fail the second on the uniqueness index, leaving
        // the administrator with a half-applied batch and no obvious cause.
        RuleFor(request => request.Families)
            .Must(families =>
            {
                var declared = families.SelectMany(family => family.Members).Select(m => m.ProductId);
                return declared.Distinct().Count() == declared.Count();
            })
            .WithMessage("Un producto no puede declararse en dos familias del mismo lote.");
    }
}

/// <summary>
/// Validates one approved family.
/// </summary>
public class ApprovedFamilyRequestValidator : AbstractValidator<ApprovedFamilyRequest>
{
    public ApprovedFamilyRequestValidator()
    {
        RuleFor(family => family.Name)
            .NotEmpty()
            .WithMessage("La familia debe tener nombre.")
            .MaximumLength(200)
            .WithMessage("El nombre de la familia no puede superar los 200 caracteres.");

        RuleFor(family => family.Description)
            .MaximumLength(1000)
            .WithMessage("La descripción no puede superar los 1000 caracteres.");

        RuleFor(family => family.Members)
            .Must(members => members.Count >= 2)
            .WithMessage("Una familia necesita al menos dos miembros; con uno no hay variante que distinguir.");

        RuleFor(family => family.Members)
            .Must(members => members.Select(m => m.ProductId).Distinct().Count() == members.Count)
            .WithMessage("Un producto no puede declararse dos veces en la misma familia.");

        // Null repeats freely — several members may have no variant determined yet, which the
        // family schema allows on purpose. Two members carrying the *same* label are what defeats
        // the point of the family, and what its unique index rejects.
        RuleFor(family => family.Members)
            .Must(members =>
            {
                var labels = members
                    .Select(m => m.VariantLabel)
                    .Where(label => !string.IsNullOrWhiteSpace(label))
                    .ToList();
                return labels.Distinct(StringComparer.OrdinalIgnoreCase).Count() == labels.Count;
            })
            .WithMessage("Dos miembros de una familia no pueden compartir la etiqueta de variante.");
    }
}
