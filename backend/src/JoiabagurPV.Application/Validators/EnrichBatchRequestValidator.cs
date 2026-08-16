using FluentValidation;
using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Application.Validators;

/// <summary>
/// Validates a batch enrichment request.
/// </summary>
public class EnrichBatchRequestValidator : AbstractValidator<EnrichBatchRequest>
{
    public EnrichBatchRequestValidator()
    {
        RuleFor(request => request.ProductIds)
            .NotEmpty()
            .WithMessage("A batch must name at least one product.");

        // The bound is the contract's, not a number chosen here. Rejecting on this side turns a
        // round trip that would end in a validation error into an immediate, explainable answer.
        RuleFor(request => request.ProductIds)
            .Must(ids => ids.Count <= AiEnrichRequest.MaxBatchSize)
            .WithMessage(
                $"A batch may hold at most {AiEnrichRequest.MaxBatchSize} products, which is the "
                + "limit the AI service contract accepts in one call.");

        RuleForEach(request => request.ProductIds)
            .NotEmpty()
            .WithMessage("A product identifier cannot be empty.");

        RuleFor(request => request.ReviewMode)
            .IsInEnum()
            .WithMessage("The review mode must be either Routed or AutoBulk.");
    }
}
