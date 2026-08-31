using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.Extensions.Logging;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Auditing existing families: jbg-ai measures, this side remembers what a person decided.
/// </summary>
/// <remarks>
/// <para>
/// The division of labour mirrors the suggestion flow and rests on the same hard constraint: the
/// vectors live in the AI service's schema and the catalog's truth lives here, so the measurement
/// is asked for and the judgement is stored. What is new is that the judgement has to travel
/// <em>back</em> on every call — the service keeps no verdict, so a pair it is not told about is a
/// pair it reports again.
/// </para>
/// <para>
/// <strong>Auditing writes nothing.</strong> Recording is a separate operation on a separate route,
/// and that separation is what makes "the audit changed nothing" an assertion a test can make
/// rather than a claim in a comment.
/// </para>
/// </remarks>
public class FamilyAuditService(
    IAiGatewayClient gateway,
    IFamilyReviewVerdictRepository verdicts,
    IUnitOfWork unitOfWork,
    ILogger<FamilyAuditService> logger) : IFamilyAuditService
{
    private readonly IAiGatewayClient _gateway = gateway;
    private readonly IFamilyReviewVerdictRepository _verdicts = verdicts;
    private readonly IUnitOfWork _unitOfWork = unitOfWork;
    private readonly ILogger<FamilyAuditService> _logger = logger;

    /// <inheritdoc/>
    public async Task<AiFamilyAuditResponse> AuditAsync(
        FamilyAuditQueryRequest request,
        Guid userId,
        string role,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        var judged = await _verdicts.GetJudgedPairsAsync();

        var scope = AiCallScope.ForCatalog(userId, role);
        var response = await _gateway.AuditFamiliesAsync(
            new AiFamilyAuditRequest
            {
                PieceType = request.PieceType,
                VetoMargin = request.VetoMargin,
                OrphanMargin = request.OrphanMargin,
                MaxOrphans = request.MaxOrphans,
                JudgedPairs = judged
                    .Select(pair => new AiJudgedPair
                    {
                        ProductId = pair.ProductId.ToString(),
                        FamilyId = pair.FamilyId.ToString()
                    })
                    .ToList()
            },
            scope,
            cancellationToken);

        // The examined counts travel beside the findings so that "nothing flagged" can be told
        // from "nothing looked at" in the log as well as on the screen. On a catalog-quality
        // surface those two read identically and only one of them is good news.
        _logger.LogInformation(
            "family_audit_read {Flagged} {Candidates} {Families} {Members} {JudgedPairs}",
            response.FlaggedMembers.Count,
            response.OrphanCandidates.Count,
            response.FamiliesReviewedCount,
            response.MembersExaminedCount,
            judged.Count);

        return response;
    }

    /// <inheritdoc/>
    public async Task<RecordFamilyVerdictsResponse> RecordVerdictsAsync(
        RecordFamilyVerdictsRequest request,
        Guid reviewedByUserId)
    {
        ArgumentNullException.ThrowIfNull(request);

        // Last write wins within one batch. A reviewer who ticks a row twice before submitting is
        // correcting themselves, and inserting both would break the unique index on the pair —
        // turning a question a person already answered into a database error.
        var deduplicated = request.Verdicts
            .GroupBy(verdict => (verdict.ProductId, verdict.FamilyId))
            .Select(group => group.Last())
            .ToList();

        var pairs = deduplicated
            .Select(verdict => (verdict.ProductId, verdict.FamilyId))
            .ToList();

        var existing = await _verdicts.GetByPairsAsync(pairs);
        var index = existing.ToDictionary(
            verdict => (verdict.ProductId, verdict.ProductFamilyId));

        var now = DateTime.UtcNow;
        var created = 0;
        var updated = 0;

        foreach (var verdict in deduplicated)
        {
            var outcome = ParseOutcome(verdict.Outcome);

            if (index.TryGetValue((verdict.ProductId, verdict.FamilyId), out var stored))
            {
                stored.Outcome = outcome;
                stored.ReviewedByUserId = reviewedByUserId;
                stored.ReviewedAt = now;
                stored.MarginAtReview = verdict.MarginAtReview;
                stored.Note = verdict.Note?.Trim();
                updated++;
                continue;
            }

            await _verdicts.AddAsync(new FamilyReviewVerdict
            {
                ProductId = verdict.ProductId,
                ProductFamilyId = verdict.FamilyId,
                Outcome = outcome,
                ReviewedByUserId = reviewedByUserId,
                ReviewedAt = now,
                MarginAtReview = verdict.MarginAtReview,
                Note = verdict.Note?.Trim()
            });
            created++;
        }

        await _unitOfWork.SaveChangesAsync();

        // Corrections counted apart from first judgements: a session spent revisiting is a
        // different session from one spent advancing, and a single total hides which it was.
        _logger.LogInformation(
            "family_verdicts_recorded {Created} {Updated} {ReviewedBy}",
            created,
            updated,
            reviewedByUserId);

        return new RecordFamilyVerdictsResponse { Created = created, Updated = updated };
    }

    private static FamilyReviewOutcome ParseOutcome(string raw)
    {
        if (!Enum.TryParse<FamilyReviewOutcome>(raw, ignoreCase: true, out var parsed)
            || !Enum.IsDefined(parsed))
        {
            throw new ArgumentException(
                $"Veredicto no reconocido: '{raw}'. Valores admitidos: "
                + string.Join(", ", Enum.GetNames<FamilyReviewOutcome>()) + ".");
        }

        return parsed;
    }
}
