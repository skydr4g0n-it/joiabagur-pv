using FluentValidation;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using Microsoft.Extensions.Options;

namespace JoiabagurPV.Application.Validators;

/// <summary>
/// Validator for AssistedSearchRequest.
/// </summary>
/// <remarks>
/// The query ceiling is the one the frozen contract declares, not an independently chosen
/// number: a longer query would be rejected by the AI service anyway, and the telemetry column
/// is sized to that same limit.
///
/// The page ceiling comes from configuration through <c>IOptionsMonitor</c>, so raising it does
/// not require a redeploy.
/// </remarks>
public class AssistedSearchRequestValidator : AbstractValidator<AssistedSearchRequest>
{
    public AssistedSearchRequestValidator(IOptionsMonitor<AiSearchOptions> options)
    {
        RuleFor(x => x.Query)
            .NotEmpty()
            .WithMessage("La búsqueda requiere un texto.")
            .MaximumLength(AiSearchRequest.MaxQueryLength)
            .WithMessage($"La búsqueda no puede superar los {AiSearchRequest.MaxQueryLength} caracteres.");

        RuleFor(x => x.PointOfSaleId)
            .NotEmpty()
            .WithMessage("La búsqueda asistida requiere un punto de venta.");

        RuleFor(x => x.PageSize)
            .Must(size => size is null || size >= 1)
            .WithMessage("El tamaño de página debe ser al menos 1.")
            .Must(size => size is null || size <= options.CurrentValue.MaxPageSize)
            .WithMessage(x => $"El tamaño de página no puede superar {options.CurrentValue.MaxPageSize}.");
    }
}
