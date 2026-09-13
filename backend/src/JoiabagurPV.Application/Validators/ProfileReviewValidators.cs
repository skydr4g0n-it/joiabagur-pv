using FluentValidation;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Services;

namespace JoiabagurPV.Application.Validators;

/// <summary>
/// Validates a request for the stratified review queue.
/// </summary>
public class ProfileReviewQueueRequestValidator : AbstractValidator<ProfileReviewQueueRequest>
{
    public ProfileReviewQueueRequestValidator()
    {
        RuleFor(request => request.Page)
            .GreaterThan(0)
            .WithMessage("La página debe ser mayor que cero.");

        // Pagination is mandatory and capped. The queue reads every profile of the corpus to
        // stratify it, so an uncapped page would serve the whole catalog into a browser as one
        // response.
        RuleFor(request => request.PageSize)
            .InclusiveBetween(1, ProfileReviewQueueRequest.MaxPageSize)
            .WithMessage(
                $"El tamaño de página debe estar entre 1 y {ProfileReviewQueueRequest.MaxPageSize}.");

        RuleFor(request => request.Stratum)
            .Must(stratum => stratum is null || ProfileEvidenceStratum.TryParse(stratum) is not null)
            .WithMessage("El estrato debe ser A, B o C.");

        RuleFor(request => request.QuotaPerStratum)
            .Must(quota => quota is null or > 0)
            .WithMessage("La cuota por estrato debe ser mayor que cero.");
    }
}

/// <summary>
/// Validates one reviewer's judgement.
/// </summary>
public class RecordProfileReviewRequestValidator : AbstractValidator<RecordProfileReviewRequest>
{
    public RecordProfileReviewRequestValidator()
    {
        RuleFor(request => request.ProductId)
            .NotEmpty()
            .WithMessage("La revisión debe nombrar el producto.");

        RuleFor(request => request.Verdict)
            .Must(verdict => verdict is "approved" or "rejected")
            .WithMessage("El veredicto debe ser 'approved' o 'rejected'.");

        // Required, and refused rather than defaulted to zero. The previous review capability
        // recorded sixty-four judgements and six durations because its stopwatch lived in
        // component state; a zero here would replace that absence with a claim that the review
        // was instantaneous, which is worse than reporting nothing.
        RuleFor(request => request.ReviewDurationMs)
            .NotNull()
            .WithMessage("Una revisión individual debe traer su duración medida.")
            .GreaterThan(0)
            .When(request => request.ReviewDurationMs.HasValue)
            .WithMessage("La duración medida debe ser mayor que cero milisegundos.");
    }
}

/// <summary>
/// Validates a bulk approval, which is bounded to one field.
/// </summary>
/// <remarks>
/// The stratum is not checked here: whether a selection spans more than one is a question about
/// the profiles, and this validator holds no database. The service refuses it, and refusing it
/// in both places would leave one of the two rules untested through the route that matters.
/// </remarks>
public class BulkApproveProfilesRequestValidator : AbstractValidator<BulkApproveProfilesRequest>
{
    public BulkApproveProfilesRequestValidator()
    {
        // Exactly one. Unbounded, bulk approval is how the batch stops containing any evidence:
        // a stratum approved wholesale yields a correction rate of zero that says nothing about
        // the extractor, and the delivery loses the figure it exists to produce.
        RuleFor(request => request.Fields)
            .Must(fields => fields.Count == 1)
            .WithMessage("La aprobación masiva debe nombrar exactamente un campo.");

        RuleFor(request => request.Fields)
            .Must(fields => fields.Count != 1
                || ProfileCorrection.ReviewedFields.Contains(fields[0], StringComparer.Ordinal))
            .WithMessage(
                "El campo debe ser uno de: " + string.Join(", ", ProfileCorrection.ReviewedFields) + ".");

        RuleFor(request => request.Stratum)
            .Must(stratum => ProfileEvidenceStratum.TryParse(stratum) is not null)
            .WithMessage("La aprobación masiva debe declarar el estrato (A, B o C) al que se acota.");

        RuleFor(request => request.ProductIds)
            .NotEmpty()
            .WithMessage("La aprobación masiva debe seleccionar al menos un perfil.");

        RuleFor(request => request.ProductIds)
            .Must(ids => ids.Count <= ProfileReviewQueueRequest.MaxPageSize)
            .WithMessage(
                $"Una aprobación masiva admite como mucho {ProfileReviewQueueRequest.MaxPageSize} "
                + "perfiles, el mismo tope que una página de la cola.");
    }
}

/// <summary>
/// Validates returning a rejected profile to approved.
/// </summary>
public class RestoreRejectedProfileRequestValidator : AbstractValidator<RestoreRejectedProfileRequest>
{
    public RestoreRejectedProfileRequestValidator()
    {
        RuleFor(request => request.ProductId)
            .NotEmpty()
            .WithMessage("Hay que nombrar el producto cuyo rechazo se deshace.");

        // Optional here, unlike an individual review. The inverted pass over the rejected is a
        // short triage of a different question, and requiring a stopwatch on it would mix its
        // times into an average that describes the stratified session.
        RuleFor(request => request.ReviewDurationMs)
            .GreaterThan(0)
            .When(request => request.ReviewDurationMs.HasValue)
            .WithMessage("La duración medida debe ser mayor que cero milisegundos.");
    }
}
