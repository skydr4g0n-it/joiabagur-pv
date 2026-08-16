using System.Data.Common;
using System.Text.Json;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace JoiabagurPV.Application.Services;

/// <inheritdoc cref="IProductAiProfileService"/>
public class ProductAiProfileService : IProductAiProfileService
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        // camelCase, fixed here on purpose and for the same reason as the search telemetry: the
        // queries that read these documents are written by hand, and changing the casing later
        // breaks all of them silently.
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };

    private readonly IAiGatewayClient _gateway;
    private readonly IProfileReviewPolicy _policy;
    private readonly IRepository<Product> _products;
    private readonly IRepository<ProductAiProfile> _profiles;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<ProductAiProfileService> _logger;

    public ProductAiProfileService(
        IAiGatewayClient gateway,
        IProfileReviewPolicy policy,
        IRepository<Product> products,
        IRepository<ProductAiProfile> profiles,
        IUnitOfWork unitOfWork,
        ILogger<ProductAiProfileService> logger)
    {
        _gateway = gateway;
        _policy = policy;
        _products = products;
        _profiles = profiles;
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    /// <inheritdoc/>
    public async Task<EnrichBatchResponse> EnrichBatchAsync(
        EnrichBatchRequest request,
        Guid userId,
        string role,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        var requested = request.ProductIds.Distinct().ToList();

        var products = await _products.GetAll()
            .Include(product => product.Collection)
            .Where(product => requested.Contains(product.Id))
            .ToListAsync(cancellationToken);

        var existing = await _profiles.GetAll()
            .Where(profile => requested.Contains(profile.ProductId))
            .ToDictionaryAsync(profile => profile.ProductId, cancellationToken);

        var results = new List<EnrichBatchProfileResult>();
        var pendingProducts = new List<Product>();
        var hashes = new Dictionary<Guid, string>();

        foreach (var product in products)
        {
            var hash = ProductEnrichmentSourceHash.Compute(product, product.Collection?.Name);
            hashes[product.Id] = hash;

            // The skip that makes repeating a batch cheap and safe. Cheap because no model call
            // is paid for a product that has not changed; safe because a stored profile that a
            // person reviewed is not silently replaced by a fresh proposal.
            if (!request.Force
                && existing.TryGetValue(product.Id, out var stored)
                && stored.SourceHash == hash)
            {
                results.Add(new EnrichBatchProfileResult(product.Id, null, []));
                continue;
            }

            pendingProducts.Add(product);
        }

        var skippedUnchanged = results.Count;

        if (pendingProducts.Count == 0)
        {
            _logger.LogInformation(
                "enrich_batch_skipped_all {Requested} {SkippedUnchanged}",
                requested.Count,
                skippedUnchanged);

            return new EnrichBatchResponse(requested.Count, 0, skippedUnchanged, 0, 0, results);
        }

        var batch = await RequestProposalsAsync(pendingProducts, userId, role, cancellationToken);

        var enriched = 0;

        foreach (var product in pendingProducts)
        {
            if (!batch.Proposals.TryGetValue(product.Id.ToString(), out var proposal))
            {
                // Recorded rather than thrown: one product the extractor could not answer for
                // must not discard the work already done for the other forty-nine.
                _logger.LogWarning("enrich_batch_missing_proposal {ProductId}", product.Id);
                results.Add(new EnrichBatchProfileResult(product.Id, null, []));
                continue;
            }

            var outcome = _policy.Route(proposal);
            var stored = existing.GetValueOrDefault(product.Id);
            var profile = Upsert(
                stored,
                product.Id,
                hashes[product.Id],
                proposal,
                outcome,
                request.ReviewMode,
                batch);

            if (stored is null)
            {
                await _profiles.AddAsync(profile);
            }
            else
            {
                await _profiles.UpdateAsync(profile);
            }

            enriched++;
            results.Add(new EnrichBatchProfileResult(
                product.Id,
                profile.ReviewStatus.ToString(),
                outcome.FieldsPendingReview));
        }

        var skippedConcurrent = await SaveToleratingConcurrentInsertsAsync();
        enriched -= skippedConcurrent;

        var failed = pendingProducts.Count - enriched - skippedConcurrent;

        _logger.LogInformation(
            "enrich_batch_completed {Requested} {Enriched} {SkippedUnchanged} {SkippedConcurrent} {Failed} {ReviewMode}",
            requested.Count,
            enriched,
            skippedUnchanged,
            skippedConcurrent,
            failed,
            request.ReviewMode);

        return new EnrichBatchResponse(
            requested.Count, enriched, skippedUnchanged, skippedConcurrent, failed, results);
    }

    /// <summary>
    /// PostgreSQL's SQLSTATE for a unique-constraint violation.
    /// </summary>
    private const string UniqueViolationSqlState = "23505";

    /// <summary>
    /// Persists the batch, treating a lost race for a product as an outcome rather than a fault.
    /// </summary>
    /// <returns>How many products another batch had already enriched.</returns>
    /// <remarks>
    /// <para>
    /// The window this closes is wide, not narrow. Between reading which products already have a
    /// profile and writing the new ones sits the call to the extraction model, which takes
    /// seconds. Two administrators enriching overlapping batches is an ordinary Tuesday, not a
    /// pathological interleaving.
    /// </para>
    /// <para>
    /// Letting the violation escape would contradict this very method: a product the extractor
    /// returned nothing for is already counted and the other forty-nine proceed, so a race over
    /// one row must not be the thing that discards the batch. The losing rows are detached and
    /// the rest saved — the failed attempt rolls its transaction back, so nothing was written
    /// and everything is still pending.
    /// </para>
    /// </remarks>
    private async Task<int> SaveToleratingConcurrentInsertsAsync()
    {
        try
        {
            await _unitOfWork.SaveChangesAsync();
            return 0;
        }
        catch (DbUpdateException exception) when (IsUniqueViolation(exception) && exception.Entries.Count > 0)
        {
            var lost = exception.Entries
                .Select(entry => entry.Entity)
                .OfType<ProductAiProfile>()
                .Select(profile => profile.ProductId)
                .ToList();

            foreach (var entry in exception.Entries)
            {
                entry.State = EntityState.Detached;
            }

            _logger.LogInformation(
                "enrich_batch_lost_race {ProductIds}",
                string.Join(",", lost));

            await _unitOfWork.SaveChangesAsync();

            return lost.Count;
        }
    }

    /// <summary>
    /// Whether a persistence failure is the unique index refusing a duplicate profile.
    /// </summary>
    /// <remarks>
    /// Matched on the SQLSTATE rather than on the message, which the server localises and which
    /// would make this check depend on the language the database was started in. Read through
    /// <see cref="DbException.SqlState"/>, a base-library property, so the application layer
    /// stays free of a reference to the PostgreSQL driver — which belongs to infrastructure.
    /// </remarks>
    private static bool IsUniqueViolation(DbUpdateException exception) =>
        exception.InnerException is DbException { SqlState: UniqueViolationSqlState };

    /// <summary>
    /// One batch's proposals plus the provenance of the run that produced them.
    /// </summary>
    /// <remarks>
    /// Carried together rather than stashed in fields: this service is scoped, and a mutable
    /// field holding "the last prompt version" would be a race waiting for the first caller who
    /// enriches two batches concurrently.
    /// </remarks>
    private sealed record ProposalBatch(
        IReadOnlyDictionary<string, AiProposedProfile> Proposals,
        string? PromptVersion,
        string? Model);

    private async Task<ProposalBatch> RequestProposalsAsync(
        IReadOnlyList<Product> products,
        Guid userId,
        string role,
        CancellationToken cancellationToken)
    {
        var gatewayRequest = new AiEnrichRequest
        {
            Products = products
                .Select(product => new AiEnrichProductInput
                {
                    ProductId = product.Id.ToString(),
                    Sku = product.SKU,
                    Name = product.Name,
                    Description = product.Description
                })
                .ToList()
        };

        // A catalog scope, never a point-of-sale one: enriching the catalog belongs to no point
        // of sale, and the client refuses the wrong kind before anything leaves the process.
        var scope = AiCallScope.ForCatalog(userId, role);

        var response = await _gateway.EnrichAsync(gatewayRequest, scope, cancellationToken);

        return new ProposalBatch(
            response.Profiles.ToDictionary(profile => profile.ProductId, StringComparer.Ordinal),
            response.PromptVersion,
            response.Usage.Model);
    }

    private ProductAiProfile Upsert(
        ProductAiProfile? existing,
        Guid productId,
        string sourceHash,
        AiProposedProfile proposal,
        ProfileRoutingOutcome outcome,
        ProfileReviewMode mode,
        ProposalBatch batch)
    {
        var profile = existing ?? new ProductAiProfile
        {
            ProductId = productId,
            MaterialsJson = "[]",
            ColorTagsJson = "[]",
            StyleTagsJson = "[]",
            OccasionTagsJson = "[]",
            FieldConfidenceJson = "{}",
            FieldSourceJson = "{}",
            ProposedProfileJson = "{}",
            SourceHash = sourceHash
        };

        profile.PieceType = proposal.PieceType?.Value;
        profile.MaterialsJson = Serialize(proposal.Materials.Value);
        profile.StoneType = proposal.StoneType?.Value;
        profile.SizeLabel = proposal.SizeLabel?.Value;
        profile.ColorTagsJson = Serialize(proposal.ColorTags.Value);
        profile.StyleTagsJson = Serialize(proposal.StyleTags.Value);
        profile.OccasionTagsJson = Serialize(proposal.OccasionTags.Value);

        profile.AiConfidence = outcome.AggregateConfidence;

        // Written in both modes. This is what keeps the bulk path honest: even when everything
        // is approved without a person, the record still says which fields would have needed
        // one, so the share of the corpus nobody looked at is a number rather than a guess.
        profile.FieldConfidenceJson = Serialize(outcome.FieldConfidence);
        profile.FieldSourceJson = Serialize(outcome.FieldSource);
        profile.ProposedProfileJson = Serialize(proposal);

        profile.GeneratedByModel = batch.Model;
        profile.PromptVersion = batch.PromptVersion;
        profile.SourceHash = sourceHash;

        profile.ReviewStatus = mode == ProfileReviewMode.AutoBulk
            ? ProfileReviewStatus.Approved
            : outcome.Status;

        // Any fresh proposal is unreviewed by definition: the text it describes is not the text
        // the previous reviewer read. Clearing rather than keeping avoids a profile that claims
        // to have been checked by someone who never saw this content.
        profile.ReviewOrigin = ProfileReviewOrigin.AutoBulk;

        if (existing is not null
            && (existing.ReviewedByUserId is not null || existing.ReviewedAt is not null))
        {
            _logger.LogInformation(
                "enrich_profile_review_reset {ProductId} {PreviousReviewer} {PreviousReviewedAt}",
                productId,
                existing.ReviewedByUserId,
                existing.ReviewedAt);
        }

        profile.ReviewedByUserId = null;
        profile.ReviewedAt = null;
        profile.ReviewDurationMs = null;

        return profile;
    }

    private static string Serialize<T>(T value) => JsonSerializer.Serialize(value, JsonOptions);
}
