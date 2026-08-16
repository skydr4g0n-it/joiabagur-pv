using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Domain.Enums;

namespace JoiabagurPV.Application.Interfaces;

/// <summary>
/// Field names as they are written into the profile's provenance documents.
/// </summary>
/// <remarks>
/// Constants rather than literals because these strings are read by the review screen and by
/// whatever SQL computes the correction rate per field. A typo would not break anything — it
/// would produce a key nobody ever matches, and a metric quietly reporting zero corrections.
/// </remarks>
public static class ProfileFields
{
    public const string PieceType = "piece_type";
    public const string Materials = "materials";
    public const string StoneType = "stone_type";
    public const string SizeLabel = "size_label";
    public const string ColorTags = "color_tags";
    public const string StyleTags = "style_tags";
    public const string OccasionTags = "occasion_tags";
}

/// <summary>
/// Provenance values, matching the wire vocabulary of the enrichment contract.
/// </summary>
public static class ProfileFieldSources
{
    public const string Rule = "rule";
    public const string Inferred = "inferred";
}

/// <summary>
/// What the review policy decided about one proposal.
/// </summary>
/// <param name="Status">Where the profile lands: pending when anything needs a person.</param>
/// <param name="FieldsPendingReview">Which fields put it there, in stable order.</param>
/// <param name="FieldConfidence">Confidence per field, for persistence and for the review screen.</param>
/// <param name="FieldSource">Provenance per field, same purpose.</param>
/// <param name="AggregateConfidence">Mean confidence over the fields present.</param>
public record ProfileRoutingOutcome(
    ProfileReviewStatus Status,
    IReadOnlyList<string> FieldsPendingReview,
    IReadOnlyDictionary<string, double> FieldConfidence,
    IReadOnlyDictionary<string, string> FieldSource,
    decimal AggregateConfidence);

/// <summary>
/// Decides, field by field, what a person still has to look at.
/// </summary>
public interface IProfileReviewPolicy
{
    /// <summary>
    /// Applies the hybrid review policy to one proposal.
    /// </summary>
    /// <param name="proposal">The proposal as the AI service returned it.</param>
    /// <returns>The routing outcome, including the per-field detail worth persisting.</returns>
    ProfileRoutingOutcome Route(AiProposedProfile proposal);
}
