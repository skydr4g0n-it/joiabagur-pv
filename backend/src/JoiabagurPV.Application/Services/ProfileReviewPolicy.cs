using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Enums;
using Microsoft.Extensions.Options;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Decides, field by field, what a person still has to look at.
/// </summary>
/// <remarks>
/// <para>
/// Deliberately pure: no database, no HTTP, no clock. The rule it encodes is the one part of
/// this capability that has to be obviously correct on reading, and a policy embedded in the
/// service that persists could only be exercised through a container.
/// </para>
/// <para>
/// The rule itself: an attribute whose error reaches a customer needs a human when a model
/// inferred it, and does not when a deterministic rule produced it. An attribute whose error
/// merely costs a worse ranking can be approved on confidence alone. Everything below the floor
/// goes to review regardless.
/// </para>
/// </remarks>
public class ProfileReviewPolicy : IProfileReviewPolicy
{
    /// <summary>
    /// The attributes whose error reaches a customer.
    /// </summary>
    /// <remarks>
    /// Family membership belongs to this list in the design and is deliberately absent here: the
    /// product family is a business entity owned by its own capability, and a second opinion
    /// about it in this one would create two truths about the same thing.
    /// </remarks>
    public static readonly IReadOnlySet<string> SensitiveFields = new HashSet<string>(StringComparer.Ordinal)
    {
        ProfileFields.PieceType,
        ProfileFields.Materials,
        ProfileFields.StoneType,
        ProfileFields.SizeLabel
    };

    private readonly ProfileReviewOptions _options;

    public ProfileReviewPolicy(IOptions<ProfileReviewOptions> options)
    {
        _options = options?.Value ?? throw new ArgumentNullException(nameof(options));
    }

    /// <inheritdoc/>
    public ProfileRoutingOutcome Route(AiProposedProfile proposal)
    {
        ArgumentNullException.ThrowIfNull(proposal);

        var confidences = new Dictionary<string, double>(StringComparer.Ordinal);
        var sources = new Dictionary<string, string>(StringComparer.Ordinal);
        var pending = new List<string>();

        foreach (var (field, confidence, source) in Enumerate(proposal))
        {
            confidences[field] = confidence;
            sources[field] = source == AiFieldSource.Rule ? ProfileFieldSources.Rule : ProfileFieldSources.Inferred;

            if (RequiresReview(field, confidence, source))
            {
                pending.Add(field);
            }
        }

        // Mean over the fields actually present. Not weighted towards the sensitive ones: a
        // weighting needs weights somebody can defend, and this number only orders a review
        // queue — the decision to review is taken per field, never from this.
        var aggregate = confidences.Count == 0
            ? 0m
            : (decimal)Math.Round(confidences.Values.Average(), 3);

        return new ProfileRoutingOutcome(
            pending.Count == 0 ? ProfileReviewStatus.Approved : ProfileReviewStatus.Pending,
            pending,
            confidences,
            sources,
            aggregate);
    }

    private bool RequiresReview(string field, double confidence, AiFieldSource source)
    {
        // Provenance first, and it is absolute for the sensitive fields. A size read off the SKU
        // by a regex is not a guess, so no amount of caution justifies a person re-reading it —
        // that is the whole trade that makes reviewing ~1.000 products conceivable at all.
        if (source == AiFieldSource.Rule)
        {
            return false;
        }

        if (SensitiveFields.Contains(field))
        {
            return true;
        }

        return confidence < _options.TagAutoApproveThreshold
            || confidence < _options.MinimumFieldConfidence;
    }

    private static IEnumerable<(string Field, double Confidence, AiFieldSource Source)> Enumerate(
        AiProposedProfile proposal)
    {
        if (proposal.PieceType is { } pieceType)
        {
            yield return (ProfileFields.PieceType, pieceType.Confidence, pieceType.Source);
        }

        yield return (ProfileFields.Materials, proposal.Materials.Confidence, proposal.Materials.Source);

        if (proposal.StoneType is { } stoneType)
        {
            yield return (ProfileFields.StoneType, stoneType.Confidence, stoneType.Source);
        }

        if (proposal.SizeLabel is { } sizeLabel)
        {
            yield return (ProfileFields.SizeLabel, sizeLabel.Confidence, sizeLabel.Source);
        }

        yield return (ProfileFields.ColorTags, proposal.ColorTags.Confidence, proposal.ColorTags.Source);
        yield return (ProfileFields.StyleTags, proposal.StyleTags.Confidence, proposal.StyleTags.Source);
        yield return (ProfileFields.OccasionTags, proposal.OccasionTags.Confidence, proposal.OccasionTags.Source);
    }
}
