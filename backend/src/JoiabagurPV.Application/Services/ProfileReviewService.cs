using System.Text.Json;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace JoiabagurPV.Application.Services;

/// <inheritdoc cref="IProfileReviewService"/>
public class ProfileReviewService : IProfileReviewService
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        // The casing the profile columns were written with. Reading or writing them under a
        // different policy would leave a document nothing ever matches.
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };

    /// <summary>The question asked where the values still lack a phrase behind them.</summary>
    private const string QuestionIsItCorrect = "¿Es correcto?";

    /// <summary>
    /// The question asked where every value already has a phrase behind it.
    /// </summary>
    /// <remarks>
    /// Different on purpose, and the difference is the point. At that level the span check has
    /// already asked whether the phrase is present and answered yes, so the only defect a person
    /// can still find is an <em>omission</em> — and there are measurably many: 94 products name a
    /// material the extractor did not extract, 81 of them in this stratum. Asking "is it
    /// correct?" there is how a reviewer confirms all 81 away without reading to the end.
    /// </remarks>
    private const string QuestionIsAnythingMissing = "¿Falta algo?";

    /// <summary>The question the rejected list asks, which is the opposite one.</summary>
    private const string QuestionIsThisRejectionWrong = "¿Hay algún rechazo incorrecto?";

    private readonly IRepository<ProductAiProfile> _profiles;
    private readonly IRepository<Product> _products;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ProfileReviewOptions _options;
    private readonly ILogger<ProfileReviewService> _logger;

    public ProfileReviewService(
        IRepository<ProductAiProfile> profiles,
        IRepository<Product> products,
        IUnitOfWork unitOfWork,
        IOptions<ProfileReviewOptions> options,
        ILogger<ProfileReviewService> logger)
    {
        _profiles = profiles;
        _products = products;
        _unitOfWork = unitOfWork;
        _options = options?.Value ?? throw new ArgumentNullException(nameof(options));
        _logger = logger;
    }

    /// <inheritdoc/>
    public async Task<ProfileReviewQueueDto> GetQueueAsync(
        ProfileReviewQueueRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        var seed = string.IsNullOrWhiteSpace(request.Seed) ? _options.SamplingSeed : request.Seed.Trim();
        var quota = request.QuotaPerStratum is > 0 ? request.QuotaPerStratum.Value : _options.QuotaPerStratum;
        var page = request.Page < 1 ? 1 : request.Page;
        var pageSize = Math.Clamp(
            request.PageSize < 1 ? ProfileReviewQueueRequest.MaxPageSize : request.PageSize,
            1,
            ProfileReviewQueueRequest.MaxPageSize);

        // The universe is bulk origin over approved status, which is the whole of it: reviewing
        // moves a profile out of this set by changing its origin, never by changing its status.
        var rows = await ReadWithProductsAsync(
            profile => profile.ReviewOrigin == ProfileReviewOrigin.AutoBulk
                && profile.ReviewStatus == ProfileReviewStatus.Approved,
            cancellationToken);

        var assigned = rows
            .Select(row => (row.Profile, row.Product,
                Stratum: ProfileEvidenceStratum.AssignFromJson(row.Profile.FieldConfidenceJson)))
            .ToList();

        var wanted = ProfileEvidenceStratum.TryParse(request.Stratum);

        var draws = ProfileEvidenceStratum.All
            .Where(stratum => wanted is null || wanted == stratum)
            .Select(stratum => ProfileReviewSampling.Draw(
                stratum,
                [.. assigned.Where(item => item.Stratum.Stratum == stratum)],
                item => item.Profile.ProductId,
                seed,
                quota))
            .ToList();

        // Interleaved rather than concatenated: a reviewer who works A to Z meets one stratum
        // for an hour and then another, so any change in their pace over the session lands
        // entirely on one stratum and is indistinguishable from a property of that stratum.
        // Alternating spreads the learning effect across all three instead of confounding it.
        var batch = Interleave([.. draws.Select(draw => draw.Items)]);

        var items = batch
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .Select(item => ToItem(item.Profile, item.Product, item.Stratum))
            .ToList();

        _logger.LogInformation(
            "profile_review_queue_read {Seed} {Quota} {Universe} {Drawn} {Stratum}",
            seed,
            quota,
            assigned.Count,
            batch.Count,
            request.Stratum ?? "all");

        // Nothing is persisted, here or anywhere on this path. The batch is reproducible from
        // the seed, which is what a sample needs; storing it would require an entity, an entity
        // would require a migration, and this capability was designed to need none.
        return new ProfileReviewQueueDto
        {
            Seed = seed,
            Strata = [.. draws.Select(draw => new ProfileReviewStratumDto
            {
                Stratum = ProfileEvidenceStratum.Code(draw.Stratum),
                Label = Label(draw.Stratum),
                Question = Question(draw.Stratum),
                CorpusSize = draw.Available,
                Quota = draw.Quota,
                Drawn = draw.Items.Count,
                Exhausted = draw.Exhausted
            })],
            Items = items,
            TotalCount = batch.Count,
            Page = page,
            PageSize = pageSize
        };
    }

    /// <inheritdoc/>
    public async Task<RecordProfileReviewResponse> RecordReviewAsync(
        RecordProfileReviewRequest request,
        Guid reviewerId,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        // Refused rather than defaulted to zero. A fabricated duration is worse than none: a
        // null drops out of the average, and a zero asserts an instantaneous review.
        if (request.ReviewDurationMs is not > 0)
        {
            throw new ArgumentException(
                "Una revisión individual debe traer su duración medida (ReviewDurationMs > 0).",
                nameof(request));
        }

        var verdict = ParseVerdict(request.Verdict);

        var profile = await _profiles.GetAll()
            .FirstOrDefaultAsync(candidate => candidate.ProductId == request.ProductId, cancellationToken)
            ?? throw new ArgumentException(
                $"No existe un perfil de IA para el producto {request.ProductId}.", nameof(request));

        var stratum = ProfileEvidenceStratum.AssignFromJson(profile.FieldConfidenceJson);

        ApplyValues(profile, request);

        profile.ReviewStatus = verdict;
        profile.ReviewOrigin = ProfileReviewOrigin.Human;
        // Stamped by the server, never taken from the body: a request that could name its own
        // reviewer would let the metric be attributed to somebody who reviewed nothing.
        profile.ReviewedByUserId = reviewerId;
        profile.ReviewedAt = DateTime.UtcNow;
        profile.ReviewDurationMs = request.ReviewDurationMs;

        await _profiles.UpdateAsync(profile);

        // One operation. The judgement and its duration are written together, so losing the tab
        // cannot leave a recorded judgement whose time was never saved.
        await _unitOfWork.SaveChangesAsync();

        var corrections = ProfileCorrection.Classify(profile);
        var corrected = corrections
            .Where(correction => correction.Direction != CorrectionDirection.Confirmation)
            .ToList();

        foreach (var correction in corrected)
        {
            // Who, which field, which way. Never the profile itself: a log that carries the
            // whole document is one nobody greps and one that duplicates the catalog into a
            // second place it can be read from.
            _logger.LogInformation(
                "profile_review_corrected {ProductId} {ReviewerId} {Stratum} {Field} {Direction}",
                profile.ProductId,
                reviewerId,
                ProfileEvidenceStratum.Code(stratum.Stratum),
                correction.Field,
                ProfileCorrection.Name(correction.Direction));
        }

        _logger.LogInformation(
            "profile_review_recorded {ProductId} {ReviewerId} {Stratum} {Verdict} {CorrectedFields} {DurationMs}",
            profile.ProductId,
            reviewerId,
            ProfileEvidenceStratum.Code(stratum.Stratum),
            verdict.ToString(),
            corrected.Count,
            profile.ReviewDurationMs);

        return new RecordProfileReviewResponse
        {
            ProductId = profile.ProductId,
            ReviewStatus = verdict.ToString(),
            Stratum = ProfileEvidenceStratum.Code(stratum.Stratum),
            Directions =
            [
                .. corrections.Select(correction => new ProfileFieldDirectionDto(
                    correction.Field, ProfileCorrection.Name(correction.Direction)))
            ],
            CorrectedFields = corrected.Count,
            ReviewDurationMs = profile.ReviewDurationMs
        };
    }

    /// <inheritdoc/>
    public async Task<BulkApproveProfilesResponse> BulkApproveAsync(
        BulkApproveProfilesRequest request,
        Guid reviewerId,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        var fields = ProfileCorrection.Normalise(request.Fields);

        // Bounded to one field. Unbounded, this is how the batch stops containing any evidence:
        // a stratum approved wholesale yields a correction rate of zero that says nothing about
        // the extractor, and the delivery loses the number it exists to produce.
        if (fields.Count != 1)
        {
            throw new ArgumentException(
                "La aprobación masiva debe nombrar exactamente un campo.", nameof(request));
        }

        var field = fields[0];

        if (!ProfileCorrection.ReviewedFields.Contains(field, StringComparer.Ordinal))
        {
            throw new ArgumentException(
                $"'{field}' no es un campo revisable. Admitidos: "
                + string.Join(", ", ProfileCorrection.ReviewedFields) + ".",
                nameof(request));
        }

        var declared = ProfileEvidenceStratum.TryParse(request.Stratum)
            ?? throw new ArgumentException(
                "La aprobación masiva debe declarar el estrato al que se acota (A, B o C).",
                nameof(request));

        var productIds = request.ProductIds.Distinct().ToList();

        if (productIds.Count == 0)
        {
            throw new ArgumentException(
                "La aprobación masiva debe seleccionar al menos un perfil.", nameof(request));
        }

        var profiles = await _profiles.GetAll()
            .Where(profile => productIds.Contains(profile.ProductId))
            .ToListAsync(cancellationToken);

        if (profiles.Count != productIds.Count)
        {
            throw new ArgumentException(
                "La selección incluye productos sin perfil de IA. No se ha modificado nada.",
                nameof(request));
        }

        // Verified against the declared stratum rather than inferred from the selection.
        // Inferring it would accept any selection at all and report afterwards which stratum it
        // happened to be, which is not a bound.
        var trespassers = profiles
            .Where(profile =>
                ProfileEvidenceStratum.AssignFromJson(profile.FieldConfidenceJson).Stratum != declared)
            .ToList();

        if (trespassers.Count > 0)
        {
            throw new ArgumentException(
                $"La selección cruza más de un estrato: {trespassers.Count} perfil(es) no "
                + $"pertenecen al estrato {ProfileEvidenceStratum.Code(declared)}. "
                + "No se ha modificado nada.",
                nameof(request));
        }

        var stampedAt = DateTime.UtcNow;

        foreach (var profile in profiles)
        {
            profile.ReviewOrigin = ProfileReviewOrigin.Human;
            profile.ReviewedByUserId = reviewerId;
            profile.ReviewedAt = stampedAt;

            // No duration is written, ever. A shared timestamp spread across forty rows would
            // produce an average that flatters the process; an absence reports that this
            // judgement was not timed, which is what happened. An earlier individual review's
            // measurement is left alone rather than overwritten with null — losing a time that
            // was actually measured is the failure this whole design is built against.

            await _profiles.UpdateAsync(profile);
        }

        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation(
            "profile_review_bulk_approved {ReviewerId} {Stratum} {Field} {Count}",
            reviewerId,
            ProfileEvidenceStratum.Code(declared),
            field,
            profiles.Count);

        return new BulkApproveProfilesResponse
        {
            Field = field,
            Stratum = ProfileEvidenceStratum.Code(declared),
            Approved = profiles.Count
        };
    }

    /// <inheritdoc/>
    public async Task<RejectedProfilesDto> GetRejectedAsync(
        int page,
        int pageSize,
        CancellationToken cancellationToken = default)
    {
        var safePage = page < 1 ? 1 : page;
        var safePageSize = Math.Clamp(
            pageSize < 1 ? ProfileReviewQueueRequest.MaxPageSize : pageSize,
            1,
            ProfileReviewQueueRequest.MaxPageSize);

        var rows = await ReadWithProductsAsync(
            profile => profile.ReviewStatus == ProfileReviewStatus.Rejected,
            cancellationToken);

        // Ordered by the same seed as the queue, for the same reason, and separately from it:
        // these consume no stratum's quota. Most of them are correctly rejected non-jewellery
        // and they cluster in the stratum of absence, so letting them draw against it would
        // spend the scarcest attention in the batch confirming that a candle is not a jewel.
        var ordered = ProfileReviewSampling.Order(
            rows, row => row.Profile.ProductId, _options.SamplingSeed);

        var items = ordered
            .Skip((safePage - 1) * safePageSize)
            .Take(safePageSize)
            .Select(row => ToItem(
                row.Profile,
                row.Product,
                ProfileEvidenceStratum.AssignFromJson(row.Profile.FieldConfidenceJson)))
            .ToList();

        return new RejectedProfilesDto
        {
            Items = items,
            TotalCount = ordered.Count,
            Page = safePage,
            PageSize = safePageSize,
            Question = QuestionIsThisRejectionWrong
        };
    }

    /// <inheritdoc/>
    public async Task<RecordProfileReviewResponse> RestoreRejectedAsync(
        RestoreRejectedProfileRequest request,
        Guid reviewerId,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        var profile = await _profiles.GetAll()
            .FirstOrDefaultAsync(candidate => candidate.ProductId == request.ProductId, cancellationToken)
            ?? throw new ArgumentException(
                $"No existe un perfil de IA para el producto {request.ProductId}.", nameof(request));

        if (profile.ReviewStatus != ProfileReviewStatus.Rejected)
        {
            throw new ArgumentException(
                "Solo se puede devolver a aprobado un perfil que esté rechazado.", nameof(request));
        }

        var stratum = ProfileEvidenceStratum.AssignFromJson(profile.FieldConfidenceJson);

        profile.ReviewStatus = ProfileReviewStatus.Approved;
        profile.ReviewOrigin = ProfileReviewOrigin.Human;
        profile.ReviewedByUserId = reviewerId;
        profile.ReviewedAt = DateTime.UtcNow;

        if (request.ReviewDurationMs is > 0)
        {
            profile.ReviewDurationMs = request.ReviewDurationMs;
        }

        await _profiles.UpdateAsync(profile);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation(
            "profile_review_rejection_undone {ProductId} {ReviewerId} {Stratum}",
            profile.ProductId,
            reviewerId,
            ProfileEvidenceStratum.Code(stratum.Stratum));

        return new RecordProfileReviewResponse
        {
            ProductId = profile.ProductId,
            ReviewStatus = profile.ReviewStatus.ToString(),
            Stratum = ProfileEvidenceStratum.Code(stratum.Stratum),
            Directions = [],
            CorrectedFields = 0,
            ReviewDurationMs = profile.ReviewDurationMs
        };
    }

    /// <inheritdoc/>
    public async Task<ProfileReviewMetricsDto> GetMetricsAsync(
        CancellationToken cancellationToken = default)
    {
        var profiles = await _profiles.GetAll().ToListAsync(cancellationToken);

        var assigned = profiles
            .Select(profile => (
                Profile: profile,
                Stratum: ProfileEvidenceStratum.AssignFromJson(profile.FieldConfidenceJson).Stratum))
            .ToList();

        // The population the batch is drawn from, and the one the weighting uses. Excludes the
        // profiles the bulk pass rejected — gift-shop articles with no piece type in the closed
        // vocabulary — and stays the same size as reviewing proceeds, because reviewing changes
        // origin and a human rejection keeps the profile in this set. A weight that moved while
        // the session ran would make two readings of the same metric disagree.
        var universe = assigned
            .Where(item => !(item.Profile.ReviewStatus == ProfileReviewStatus.Rejected
                && item.Profile.ReviewOrigin == ProfileReviewOrigin.AutoBulk))
            .ToList();

        var corpusSize = ProfileEvidenceStratum.All.ToDictionary(
            stratum => stratum,
            stratum => universe.Count(item => item.Stratum == stratum));

        // Bulk origin leaves both the numerator and the denominator. A profile nobody looked at
        // agrees with its own proposal by construction, so counting it would drive the published
        // rate towards zero in proportion to how little of the catalog was reviewed.
        var reviewed = assigned
            .Where(item => item.Profile.ReviewOrigin == ProfileReviewOrigin.Human)
            .Select(item => (
                item.Profile,
                item.Stratum,
                Corrections: ProfileCorrection.Classify(item.Profile)))
            .ToList();

        var timed = reviewed
            .Where(item => item.Profile.ReviewDurationMs.HasValue)
            .Select(item => item.Profile.ReviewDurationMs!.Value / 1000d)
            .ToList();

        var judgements = reviewed
            .SelectMany(item => item.Corrections.Select(correction => (item.Stratum, correction)))
            .ToList();

        var fields = ProfileCorrection.ReviewedFields
            .Select(field => FieldMetrics(field, judgements, corpusSize))
            .ToList();

        var strata = ProfileEvidenceStratum.All
            .Select(stratum => StratumMetrics(stratum, reviewed, judgements, corpusSize[stratum]))
            .ToList();

        var fieldsCorrected = judgements.Count(
            item => item.correction.Direction != CorrectionDirection.Confirmation);

        return new ProfileReviewMetricsDto
        {
            ProfilesTotal = profiles.Count,
            ProfilesReviewedByHuman = reviewed.Count,
            ProfilesAutoBulk = profiles.Count(
                profile => profile.ReviewOrigin == ProfileReviewOrigin.AutoBulk),
            ReviewedShare = Rate(reviewed.Count, profiles.Count),
            TimedReviews = timed.Count,
            BulkApprovedReviews = reviewed.Count(item => !item.Profile.ReviewDurationMs.HasValue),
            // Null and never zero. Zero asserts an instantaneous review, which is a claim; an
            // absence reports that nothing was measured, which is the truth.
            AverageReviewSeconds = timed.Count == 0 ? null : Math.Round(timed.Average(), 1),
            MinReviewSeconds = timed.Count == 0 ? null : Math.Round(timed.Min(), 1),
            MaxReviewSeconds = timed.Count == 0 ? null : Math.Round(timed.Max(), 1),
            FieldsReviewed = judgements.Count,
            FieldsCorrected = fieldsCorrected,
            SampleCorrectionRate = Rate(fieldsCorrected, judgements.Count),
            WeightedCorrectionRate = Weighted(
                strata.Select(stratum => (stratum.CorrectionRate, stratum.CorpusSize))),
            Fields = fields,
            Strata = strata,
            ProfilesByPromptVersion = profiles
                .GroupBy(profile => profile.PromptVersion ?? "desconocida", StringComparer.Ordinal)
                .OrderBy(group => group.Key, StringComparer.Ordinal)
                .ToDictionary(group => group.Key, group => group.Count(), StringComparer.Ordinal),
            Seed = _options.SamplingSeed
        };
    }

    // ── Internals ─────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Reads the profiles matching a filter, each beside the product text it is judged against.
    /// </summary>
    /// <remarks>
    /// The filter is applied to the profiles <strong>before</strong> the join, and the join
    /// projects an anonymous type. Filtering after projecting into a named record is not
    /// translatable and fails at run time with a 500 — a shape that passes every unit test in
    /// this project, because the mocked queryable evaluates in memory and never has to speak SQL.
    /// </remarks>
    private async Task<List<ProfileProductRow>> ReadWithProductsAsync(
        System.Linq.Expressions.Expression<Func<ProductAiProfile, bool>> filter,
        CancellationToken cancellationToken)
    {
        var rows = await _profiles.GetAll()
            .Where(filter)
            .Join(
                _products.GetAll(),
                profile => profile.ProductId,
                product => product.Id,
                (profile, product) => new { Profile = profile, Product = product })
            .ToListAsync(cancellationToken);

        return [.. rows.Select(row => new ProfileProductRow(row.Profile, row.Product))];
    }

    /// <summary>A profile beside the product text it is judged against.</summary>
    private sealed record ProfileProductRow(ProductAiProfile Profile, Product Product);

    /// <summary>
    /// Takes one from each stratum in turn, until every stratum is spent.
    /// </summary>
    private static List<T> Interleave<T>(IReadOnlyList<IReadOnlyList<T>> lists)
    {
        var result = new List<T>(lists.Sum(list => list.Count));
        var longest = lists.Count == 0 ? 0 : lists.Max(list => list.Count);

        for (var index = 0; index < longest; index++)
        {
            foreach (var list in lists.Where(list => index < list.Count))
            {
                result.Add(list[index]);
            }
        }

        return result;
    }

    private static ProfileReviewItemDto ToItem(
        ProductAiProfile profile,
        Product product,
        ProfileStratumAssignment stratum)
    {
        var proposal = ProfileCorrection.ParseProposal(profile.ProposedProfileJson);
        var confidence = ProfileEvidenceStratum.ParseConfidence(profile.FieldConfidenceJson);
        var sources = ParseSources(profile.FieldSourceJson);
        var corrections = ProfileCorrection.Classify(profile)
            .ToDictionary(correction => correction.Field, StringComparer.Ordinal);

        return new ProfileReviewItemDto
        {
            ProductId = profile.ProductId,
            Sku = product.SKU,
            Name = product.Name,
            Description = product.Description,
            HasDescription = !string.IsNullOrWhiteSpace(product.Description),
            Stratum = ProfileEvidenceStratum.Code(stratum.Stratum),
            StratumDecidingField = stratum.DecidingField,
            Question = Question(stratum.Stratum),
            Fields =
            [
                Field(ProfileFields.PieceType, profile.PieceType, proposal?.PieceType?.Value),
                ListField(ProfileFields.Materials, profile.MaterialsJson, proposal?.Materials?.Value),
                Field(ProfileFields.StoneType, profile.StoneType, proposal?.StoneType?.Value),
                Field(ProfileFields.SizeLabel, profile.SizeLabel, proposal?.SizeLabel?.Value),
                ListField(ProfileFields.ColorTags, profile.ColorTagsJson, proposal?.ColorTags?.Value),
                ListField(ProfileFields.StyleTags, profile.StyleTagsJson, proposal?.StyleTags?.Value),
                ListField(ProfileFields.OccasionTags, profile.OccasionTagsJson, proposal?.OccasionTags?.Value)
            ],
            ReviewStatus = profile.ReviewStatus.ToString(),
            ReviewOrigin = profile.ReviewOrigin.ToString(),
            PromptVersion = profile.PromptVersion
        };

        ProfileReviewFieldDto Field(string name, string? value, string? proposed) =>
            Decorate(new ProfileReviewFieldDto
            {
                Field = name,
                IsList = false,
                Value = value,
                ProposedValue = proposed
            });

        ProfileReviewFieldDto ListField(string name, string? valueJson, List<string>? proposed) =>
            Decorate(new ProfileReviewFieldDto
            {
                Field = name,
                IsList = true,
                Values = [.. ProfileCorrection.ParseList(valueJson)],
                ProposedValues = [.. ProfileCorrection.Normalise(proposed)]
            });

        ProfileReviewFieldDto Decorate(ProfileReviewFieldDto field)
        {
            var source = sources.GetValueOrDefault(field.Field, ProfileFieldSources.Inferred);
            var sensitive = ProfileReviewPolicy.SensitiveFields.Contains(field.Field);

            field.Confidence = confidence.GetValueOrDefault(field.Field, 0.20);
            field.Source = source;
            field.Sensitive = sensitive;
            // Sensitive and inferred. A size read off a SKU by a regex is not a guess, and
            // marking it would spend a reviewer's attention on the one field that needs none.
            field.PendingReview = sensitive && source == ProfileFieldSources.Inferred;
            field.AlreadyCorrected =
                corrections.TryGetValue(field.Field, out var correction)
                && correction.Direction != CorrectionDirection.Confirmation;

            return field;
        }
    }

    private static ProfileFieldCorrectionDto FieldMetrics(
        string field,
        IReadOnlyList<(EvidenceStratum Stratum, FieldCorrection correction)> judgements,
        IReadOnlyDictionary<EvidenceStratum, int> corpusSize)
    {
        var forField = judgements
            .Where(item => item.correction.Field == field)
            .ToList();

        var byStratum = ProfileEvidenceStratum.All
            .Select(stratum =>
            {
                var rows = forField.Where(item => item.Stratum == stratum).ToList();
                var corrected = rows.Count(
                    item => item.correction.Direction != CorrectionDirection.Confirmation);

                return new ProfileFieldStratumCorrectionDto
                {
                    Stratum = ProfileEvidenceStratum.Code(stratum),
                    Reviewed = rows.Count,
                    Corrected = corrected,
                    CorrectionRate = Rate(corrected, rows.Count),
                    Confirmations = Count(rows, CorrectionDirection.Confirmation),
                    Additions = Count(rows, CorrectionDirection.Addition),
                    Removals = Count(rows, CorrectionDirection.Removal),
                    Substitutions = Count(rows, CorrectionDirection.Substitution),
                    CorpusSize = corpusSize[stratum]
                };
            })
            .ToList();

        var totalCorrected = forField.Count(
            item => item.correction.Direction != CorrectionDirection.Confirmation);

        return new ProfileFieldCorrectionDto
        {
            Field = field,
            Reviewed = forField.Count,
            Corrected = totalCorrected,
            SampleCorrectionRate = Rate(totalCorrected, forField.Count),
            WeightedCorrectionRate = Weighted(
                byStratum.Select(stratum => (stratum.CorrectionRate, stratum.CorpusSize))),
            ByStratum = byStratum
        };
    }

    private static ProfileStratumCorrectionDto StratumMetrics(
        EvidenceStratum stratum,
        IReadOnlyList<(ProductAiProfile Profile, EvidenceStratum Stratum,
            IReadOnlyList<FieldCorrection> Corrections)> reviewed,
        IReadOnlyList<(EvidenceStratum Stratum, FieldCorrection correction)> judgements,
        int corpusSize)
    {
        var profiles = reviewed.Where(item => item.Stratum == stratum).ToList();
        var rows = judgements.Where(item => item.Stratum == stratum).ToList();
        var corrected = rows.Count(
            item => item.correction.Direction != CorrectionDirection.Confirmation);

        return new ProfileStratumCorrectionDto
        {
            Stratum = ProfileEvidenceStratum.Code(stratum),
            Label = Label(stratum),
            CorpusSize = corpusSize,
            ProfilesReviewed = profiles.Count,
            ProfilesWithAnyCorrection = profiles.Count(item => item.Corrections.Any(
                correction => correction.Direction != CorrectionDirection.Confirmation)),
            FieldsReviewed = rows.Count,
            FieldsCorrected = corrected,
            CorrectionRate = Rate(corrected, rows.Count),
            Additions = Count(rows, CorrectionDirection.Addition),
            Removals = Count(rows, CorrectionDirection.Removal),
            Substitutions = Count(rows, CorrectionDirection.Substitution)
        };
    }

    private static int Count(
        IReadOnlyList<(EvidenceStratum Stratum, FieldCorrection correction)> rows,
        CorrectionDirection direction) =>
        rows.Count(item => item.correction.Direction == direction);

    private static double? Rate(int part, int whole) =>
        whole == 0 ? null : Math.Round(part * 100d / whole, 1);

    /// <summary>
    /// Combines per-stratum rates by the real size of each stratum in the corpus.
    /// </summary>
    /// <remarks>
    /// The strata are deliberately sampled at very different rates — equal quotas over
    /// populations of 122, 285 and 761 — so an unweighted total over the batch describes the
    /// batch and not the catalog. Strata nobody reviewed are left out of both sides of the
    /// fraction rather than counted as zero, which would report a catalog cleaner than anything
    /// that was looked at.
    /// </remarks>
    private static double? Weighted(IEnumerable<(double? Rate, int Weight)> parts)
    {
        var measured = parts.Where(part => part.Rate.HasValue && part.Weight > 0).ToList();

        if (measured.Count == 0)
        {
            return null;
        }

        var weight = measured.Sum(part => (double)part.Weight);

        return weight == 0
            ? null
            : Math.Round(measured.Sum(part => part.Rate!.Value * part.Weight) / weight, 1);
    }

    private static string Label(EvidenceStratum stratum) => stratum switch
    {
        EvidenceStratum.Absence => "Ausencia de evidencia",
        EvidenceStratum.NoSpan => "Afirmado sin frase en el texto",
        EvidenceStratum.WithSpan => "Afirmado con frase en el texto",
        _ => throw new ArgumentOutOfRangeException(nameof(stratum), stratum, "Unknown stratum.")
    };

    private static string Question(EvidenceStratum stratum) =>
        stratum == EvidenceStratum.WithSpan ? QuestionIsAnythingMissing : QuestionIsItCorrect;

    private static ProfileReviewStatus ParseVerdict(string? raw)
    {
        var verdict = raw?.Trim().ToLowerInvariant();

        return verdict switch
        {
            "approved" or "aprobado" => ProfileReviewStatus.Approved,
            "rejected" or "rechazado" => ProfileReviewStatus.Rejected,
            _ => throw new ArgumentException(
                $"Veredicto no reconocido: '{raw}'. Admitidos: approved, rejected.", nameof(raw))
        };
    }

    private static Dictionary<string, string> ParseSources(string? fieldSourceJson)
    {
        if (string.IsNullOrWhiteSpace(fieldSourceJson))
        {
            return new Dictionary<string, string>(StringComparer.Ordinal);
        }

        try
        {
            return JsonSerializer.Deserialize<Dictionary<string, string>>(fieldSourceJson)
                ?? new Dictionary<string, string>(StringComparer.Ordinal);
        }
        catch (JsonException)
        {
            return new Dictionary<string, string>(StringComparer.Ordinal);
        }
    }

    /// <summary>
    /// Writes the reviewer's values into the profile, and nothing else.
    /// </summary>
    /// <remarks>
    /// <strong>The raw proposal, the confidences, the provenances and the source hash are not
    /// touched.</strong> The correction rate is the difference between the proposal and the
    /// values in force, so a review that rewrote the proposal would leave the profile agreeing
    /// with itself — destroying the metric silently, and with no way to recover it from the row.
    /// </remarks>
    private static void ApplyValues(ProductAiProfile profile, RecordProfileReviewRequest request)
    {
        profile.PieceType = Trimmed(request.PieceType);
        profile.StoneType = Trimmed(request.StoneType);
        profile.SizeLabel = Trimmed(request.SizeLabel);
        profile.MaterialsJson = SerializeList(request.Materials);
        profile.ColorTagsJson = SerializeList(request.ColorTags);
        profile.StyleTagsJson = SerializeList(request.StyleTags);
        profile.OccasionTagsJson = SerializeList(request.OccasionTags);
    }

    private static string? Trimmed(string? value) =>
        string.IsNullOrWhiteSpace(value) ? null : value.Trim();

    private static string SerializeList(IEnumerable<string?>? values) =>
        JsonSerializer.Serialize(ProfileCorrection.Normalise(values), JsonOptions);
}
