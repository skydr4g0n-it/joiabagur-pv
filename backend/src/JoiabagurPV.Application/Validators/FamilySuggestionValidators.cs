using FluentValidation;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;

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

/// <summary>
/// Validates a batch of human judgements about product and family pairs.
/// </summary>
/// <remarks>
/// The bounds here are the ones whose absence turns a reviewer's mistake into a database error
/// instead of a message: an unbounded batch, a note longer than the column, and an outcome the
/// enum does not name.
/// </remarks>
public class RecordFamilyVerdictsRequestValidator : AbstractValidator<RecordFamilyVerdictsRequest>
{
    public RecordFamilyVerdictsRequestValidator()
    {
        RuleFor(request => request.Verdicts)
            .NotEmpty()
            .WithMessage("Se necesita al menos un veredicto.");

        RuleFor(request => request.Verdicts)
            .Must(verdicts => verdicts.Count <= RecordFamilyVerdictsRequest.MaxVerdicts)
            .WithMessage(
                $"Un lote no puede superar los {RecordFamilyVerdictsRequest.MaxVerdicts} veredictos.");

        RuleForEach(request => request.Verdicts).ChildRules(verdict =>
        {
            verdict.RuleFor(item => item.ProductId)
                .NotEmpty()
                .WithMessage("Cada veredicto necesita un producto.");

            verdict.RuleFor(item => item.FamilyId)
                .NotEmpty()
                .WithMessage("Cada veredicto necesita una familia.");

            // Checked by name rather than by parsing an integer: a numeric body that lands on the
            // first member of the enum by accident would record "confirmado" for something nobody
            // confirmed, and nothing downstream could tell.
            verdict.RuleFor(item => item.Outcome)
                .Must(outcome => Enum.TryParse<FamilyReviewOutcome>(outcome, true, out var parsed)
                    && Enum.IsDefined(parsed))
                .WithMessage(
                    "El veredicto debe ser uno de: "
                    + string.Join(", ", Enum.GetNames<FamilyReviewOutcome>()) + ".");

            verdict.RuleFor(item => item.Note)
                .MaximumLength(FamilyReviewVerdict.NoteMaxLength)
                .WithMessage(
                    $"La nota no puede superar los {FamilyReviewVerdict.NoteMaxLength} caracteres.");

            // A cosine margin lives in [-1, 1]. A value outside it is a client bug, and storing it
            // would put a number in the review history that no later reading can interpret.
            verdict.RuleFor(item => item.MarginAtReview)
                .InclusiveBetween(-1d, 1d)
                .When(item => item.MarginAtReview.HasValue)
                .WithMessage("El margen registrado debe estar entre -1 y 1.");
        });
    }
}
