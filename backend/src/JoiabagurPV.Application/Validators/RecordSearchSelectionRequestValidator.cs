using FluentValidation;
using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Application.Validators;

/// <summary>
/// Validator for RecordSearchSelectionRequest.
/// </summary>
public class RecordSearchSelectionRequestValidator : AbstractValidator<RecordSearchSelectionRequest>
{
    public RecordSearchSelectionRequestValidator()
    {
        RuleFor(x => x.ProductId)
            .NotEmpty()
            .WithMessage("Product ID is required.");
    }
}
