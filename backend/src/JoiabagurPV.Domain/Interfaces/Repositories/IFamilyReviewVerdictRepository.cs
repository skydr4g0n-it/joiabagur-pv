using JoiabagurPV.Domain.Common;
using JoiabagurPV.Domain.Entities;

namespace JoiabagurPV.Domain.Interfaces.Repositories;

/// <summary>
/// Repository interface for the human judgements recorded about products and families.
/// </summary>
public interface IFamilyReviewVerdictRepository : IRepository<FamilyReviewVerdict>
{
    /// <summary>
    /// Every pair a person has already ruled on, as identifiers and nothing else.
    /// </summary>
    /// <remarks>
    /// Sent to the AI service on every audit, because it holds no verdict of its own. Projected to
    /// the two identifiers rather than loaded as entities: at the scale this catalogue reaches —
    /// one row per judgement over hundreds of memberships — hydrating them to read two columns is
    /// the whole table for a request that only serialises them.
    /// </remarks>
    Task<List<(Guid ProductId, Guid FamilyId)>> GetJudgedPairsAsync();

    /// <summary>
    /// The stored judgements for the given pairs, so a batch can correct rather than duplicate.
    /// </summary>
    /// <remarks>
    /// Tracked, unlike <see cref="GetJudgedPairsAsync"/>: these rows are about to be written.
    /// </remarks>
    Task<List<FamilyReviewVerdict>> GetByPairsAsync(
        IReadOnlyCollection<(Guid ProductId, Guid FamilyId)> pairs);

    /// <summary>
    /// Every recorded judgement, with the product, the family and whether the membership exists.
    /// </summary>
    /// <remarks>
    /// The audit deliberately omits judged pairs — that is what makes a dismissal stick — so
    /// without this read nothing can show a reviewer what they decided, and in particular nothing
    /// can show the decisions the catalog has not acted on yet.
    /// </remarks>
    Task<List<FamilyVerdictSummary>> ListWithMembershipAsync();
}
