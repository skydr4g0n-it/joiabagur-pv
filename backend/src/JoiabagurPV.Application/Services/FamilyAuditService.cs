using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Common;
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
        // Read now, not later. Once a rejected member is removed it is indistinguishable from a
        // rejected candidate, and the two populations are reported apart.
        var currentMembers = await _verdicts.GetCurrentMembershipsAsync(pairs);
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
                // Kept when the correction carries none, rather than blanked. A judgement revised
                // through the API has no timing to offer, and overwriting the original with null
                // would silently shrink the sample the average review time is computed from.
                stored.ReviewSeconds = verdict.ReviewSeconds ?? stored.ReviewSeconds;
                // The population is not revised: it records where the question came from the first
                // time it was asked, and a correction does not move a product between queues.
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
                ReviewSeconds = verdict.ReviewSeconds,
                SubjectWasMember = currentMembers.Contains((verdict.ProductId, verdict.FamilyId)),
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

    /// <inheritdoc/>
    public async Task<List<FamilyVerdictDto>> ListVerdictsAsync()
    {
        var summaries = await _verdicts.ListWithMembershipAsync();

        return summaries
            .Select(summary => new FamilyVerdictDto
            {
                ProductId = summary.ProductId,
                Sku = summary.Sku,
                ProductName = summary.ProductName,
                FamilyId = summary.FamilyId,
                FamilyName = summary.FamilyName,
                Outcome = summary.Outcome.ToString(),
                IsCurrentMember = summary.IsCurrentMember,
                PendingAction = PendingActionFor(summary),
                MarginAtReview = summary.MarginAtReview,
                ReviewedAt = summary.ReviewedAt
            })
            .ToList();
    }

    /// <inheritdoc/>
    public async Task<FamilyReviewMetricsDto> GetMetricsAsync()
    {
        var summaries = await _verdicts.ListWithMembershipAsync();

        // Split by what the product was **when it was judged**, never by what it is now. Deriving
        // the population from the present state was the first attempt and it is wrong for exactly
        // the judgements that were acted on: a rejected member that was removed reads as a
        // rejected candidate, inflating one queue and emptying the other.
        var members = summaries.Where(s => s.SubjectWasMember).ToList();
        var candidates = summaries.Where(s => !s.SubjectWasMember).ToList();

        var timed = summaries.Where(s => s.ReviewSeconds.HasValue).ToList();

        return new FamilyReviewMetricsDto
        {
            TotalJudged = summaries.Count,
            MembersJudged = members.Count,
            MembersConfirmed = members.Count(s => s.Outcome == FamilyReviewOutcome.Confirmed),
            CandidatesJudged = candidates.Count,
            CandidatesConfirmed = candidates.Count(s => s.Outcome == FamilyReviewOutcome.Confirmed),
            MemberConfirmationRate = Rate(
                members.Count(s => s.Outcome == FamilyReviewOutcome.Confirmed), members.Count),
            CandidateAcceptanceRate = Rate(
                candidates.Count(s => s.Outcome == FamilyReviewOutcome.Confirmed), candidates.Count),
            TimedJudgements = timed.Count,
            // Null and never zero when nothing was timed. Zero would read as an instantaneous
            // review, which is a claim; null reads as "not measured", which is the truth.
            AverageReviewSeconds = timed.Count == 0
                ? null
                : Math.Round(timed.Average(s => s.ReviewSeconds!.Value), 1),
            PendingActions = summaries.Count(s => PendingActionFor(s) != "none")
        };
    }

    private static double? Rate(int part, int whole) =>
        whole == 0 ? null : Math.Round(part * 100d / whole, 1);

    /// <summary>
    /// What the catalog would have to change for a judgement to be honoured.
    /// </summary>
    /// <remarks>
    /// Only two of the four combinations imply anything. A member the reviewer rejected is still
    /// in its family until somebody removes it, and a candidate they confirmed still belongs to
    /// nothing until somebody adds it; a confirmed member and a rejected candidate are decisions
    /// the catalog already reflects.
    /// </remarks>
    private static string PendingActionFor(FamilyVerdictSummary summary) => summary switch
    {
        { Outcome: FamilyReviewOutcome.Rejected, IsCurrentMember: true } => "remove",
        { Outcome: FamilyReviewOutcome.Confirmed, IsCurrentMember: false } => "add",
        _ => "none"
    };

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
