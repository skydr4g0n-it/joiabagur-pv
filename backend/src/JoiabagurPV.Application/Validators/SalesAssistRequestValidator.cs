using FluentValidation;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using Microsoft.Extensions.Options;

namespace JoiabagurPV.Application.Validators;

/// <summary>
/// Validator for <see cref="SalesAssistRequest"/>.
/// </summary>
/// <remarks>
/// The question ceiling is the one the frozen contract declares for its own query field, not an
/// independently chosen number: a longer question would be rejected by the AI service anyway, and
/// rejecting it here spares a round trip. It is measured after trimming, which is what is sent.
/// </remarks>
public class SalesAssistRequestValidator : AbstractValidator<SalesAssistRequest>
{
    public SalesAssistRequestValidator()
    {
        RuleFor(x => x.PointOfSaleId)
            .NotEmpty()
            .WithMessage("La asistencia de venta requiere un punto de venta.");

        When(x => x.Question is not null, () =>
        {
            RuleFor(x => x.Question)
                .Must(question => !string.IsNullOrWhiteSpace(question))
                .WithMessage("La pregunta no puede estar vacía.")
                .Must(question => question!.Trim().Length <= AiAssistSaleRequest.MaxQueryLength)
                .WithMessage($"La pregunta no puede superar los {AiAssistSaleRequest.MaxQueryLength} caracteres.");
        });
    }
}

/// <summary>
/// Validator for <see cref="SubstitutesRequest"/>. The page ceiling comes from configuration
/// through <c>IOptionsMonitor</c>, so raising it does not require a redeploy.
/// </summary>
public class SubstitutesRequestValidator : AbstractValidator<SubstitutesRequest>
{
    public SubstitutesRequestValidator(IOptionsMonitor<AiSalesAssistOptions> options)
    {
        RuleFor(x => x.PointOfSaleId)
            .NotEmpty()
            .WithMessage("Los sustitutos requieren un punto de venta.");

        RuleFor(x => x.PageSize)
            .Must(size => size is null || size >= 1)
            .WithMessage("El tamaño de página debe ser al menos 1.")
            .Must(size => size is null || size <= options.CurrentValue.SubstitutesMaxPageSize)
            .WithMessage(_ => $"El tamaño de página no puede superar {options.CurrentValue.SubstitutesMaxPageSize}.");
    }
}
