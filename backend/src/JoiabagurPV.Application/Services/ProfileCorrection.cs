using System.Text.Json;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Which way a reviewer moved a field.
/// </summary>
/// <remarks>
/// Recording only whether a field changed is what the stratified design was built to avoid.
/// The direction is what separates an <em>omission</em> — the extractor missed something the
/// source text stated — from a <em>hallucination</em> — the extractor asserted something the
/// text does not support. They are different defects with different remedies: one widens a
/// vocabulary, the other tightens a prompt, and a single "corrected: yes" figure cannot tell a
/// reader which of the two the catalog has.
/// </remarks>
public enum CorrectionDirection
{
    /// <summary>The reviewer left the value as proposed.</summary>
    Confirmation = 1,

    /// <summary>The reviewer supplied what was not there. An omission was caught.</summary>
    Addition = 2,

    /// <summary>The reviewer took away what the text does not support. A hallucination was caught.</summary>
    Removal = 3,

    /// <summary>The reviewer replaced one value with another.</summary>
    Substitution = 4
}

/// <summary>
/// One field's proposal, its value in force, and the direction between them.
/// </summary>
/// <param name="Field">Field name as the provenance documents key it.</param>
/// <param name="Direction">How the reviewer moved it.</param>
/// <param name="Proposed">The raw proposal, rendered for a log or a response.</param>
/// <param name="InForce">The value in force, rendered the same way.</param>
public record FieldCorrection(
    string Field,
    CorrectionDirection Direction,
    string Proposed,
    string InForce);

/// <summary>
/// Compares the values in force against the raw proposal, field by field.
/// </summary>
/// <remarks>
/// <para>
/// <strong>The raw proposal is never rewritten.</strong> The correction rate <em>is</em> the
/// difference between that column and the values in force, so a review that edited it would
/// destroy the metric silently and with no way to recover it — the profile would simply agree
/// with itself. Nothing here writes; it only reads and compares.
/// </para>
/// <para>
/// The classification is derived from the set difference for list-valued fields rather than
/// from a count, so that a piece the reviewer declares silver <em>and</em> gold-plated reads as
/// an addition while one whose emerald the text never named reads as a removal, and a list that
/// both gained and lost an element reads as neither. Comparing counts would call that last case
/// an addition or a removal depending on arithmetic that has nothing to do with what happened.
/// </para>
/// </remarks>
public static class ProfileCorrection
{
    private static readonly JsonSerializerOptions ProposalOptions = new()
    {
        // The same casing the proposal was written with. Reading it back under a different
        // policy yields a document whose every field is null, which would classify the entire
        // corpus as an addition and read as a spectacular extractor failure.
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true
    };

    private static readonly JsonSerializerOptions ListOptions = new();

    /// <summary>
    /// The fields a review covers, in reporting order.
    /// </summary>
    /// <remarks>
    /// The four sensitive ones first, because they are the ones whose error reaches a customer
    /// and the ones the strata are built from; the three commercial tags after, because they are
    /// what bulk approval is legitimately for.
    /// </remarks>
    public static readonly IReadOnlyList<string> ReviewedFields =
    [
        ProfileFields.PieceType,
        ProfileFields.Materials,
        ProfileFields.StoneType,
        ProfileFields.SizeLabel,
        ProfileFields.ColorTags,
        ProfileFields.StyleTags,
        ProfileFields.OccasionTags
    ];

    /// <summary>Which of the reviewed fields hold a list rather than a single value.</summary>
    public static bool IsList(string field) =>
        field is ProfileFields.Materials
            or ProfileFields.ColorTags
            or ProfileFields.StyleTags
            or ProfileFields.OccasionTags;

    /// <summary>
    /// Classifies every reviewed field of one profile.
    /// </summary>
    /// <param name="profile">The profile, carrying both its proposal and its values in force.</param>
    /// <returns>One classification per reviewed field, in reporting order.</returns>
    /// <remarks>
    /// A profile whose proposal cannot be read is reported as confirming everything rather than
    /// as having corrected everything. The alternative would let an unreadable document inflate
    /// the published correction rate, which is the one number this capability exists to produce.
    /// </remarks>
    public static IReadOnlyList<FieldCorrection> Classify(ProductAiProfile profile)
    {
        ArgumentNullException.ThrowIfNull(profile);

        var proposal = ParseProposal(profile.ProposedProfileJson);

        return
        [
            Scalar(ProfileFields.PieceType, proposal?.PieceType?.Value, profile.PieceType),
            List(ProfileFields.Materials, proposal?.Materials?.Value, profile.MaterialsJson),
            Scalar(ProfileFields.StoneType, proposal?.StoneType?.Value, profile.StoneType),
            Scalar(ProfileFields.SizeLabel, proposal?.SizeLabel?.Value, profile.SizeLabel),
            List(ProfileFields.ColorTags, proposal?.ColorTags?.Value, profile.ColorTagsJson),
            List(ProfileFields.StyleTags, proposal?.StyleTags?.Value, profile.StyleTagsJson),
            List(ProfileFields.OccasionTags, proposal?.OccasionTags?.Value, profile.OccasionTagsJson)
        ];
    }

    /// <summary>Reads a stored proposal, or null when it cannot be read.</summary>
    public static AiProposedProfile? ParseProposal(string? proposedProfileJson)
    {
        if (string.IsNullOrWhiteSpace(proposedProfileJson))
        {
            return null;
        }

        try
        {
            return JsonSerializer.Deserialize<AiProposedProfile>(proposedProfileJson, ProposalOptions);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    /// <summary>Reads a stored list column into its elements, normalised.</summary>
    public static IReadOnlyList<string> ParseList(string? json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return [];
        }

        try
        {
            return Normalise(JsonSerializer.Deserialize<List<string>>(json, ListOptions));
        }
        catch (JsonException)
        {
            return [];
        }
    }

    /// <summary>
    /// Trims, drops blanks and removes repeats, keeping the order the reviewer gave.
    /// </summary>
    /// <remarks>
    /// Case is left alone. The vocabularies are lowercase and the size label is not — "M" is a
    /// ring size and "m" is a typo of it — so folding case here would corrupt one field to tidy
    /// another. Comparison is case-insensitive instead, which is where the tolerance belongs.
    /// </remarks>
    public static IReadOnlyList<string> Normalise(IEnumerable<string?>? values)
    {
        if (values is null)
        {
            return [];
        }

        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var result = new List<string>();

        foreach (var raw in values)
        {
            var value = raw?.Trim();
            if (string.IsNullOrEmpty(value) || !seen.Add(value))
            {
                continue;
            }

            result.Add(value);
        }

        return result;
    }

    /// <summary>
    /// Classifies a single-valued field.
    /// </summary>
    /// <param name="proposed">The value the extractor proposed, or null if it proposed none.</param>
    /// <param name="inForce">The value the catalog now claims, or null if the reviewer cleared it.</param>
    public static CorrectionDirection ForScalar(string? proposed, string? inForce)
    {
        var before = Blank(proposed) ? null : proposed!.Trim();
        var after = Blank(inForce) ? null : inForce!.Trim();

        if (string.Equals(before, after, StringComparison.OrdinalIgnoreCase))
        {
            return CorrectionDirection.Confirmation;
        }

        if (before is null)
        {
            return CorrectionDirection.Addition;
        }

        return after is null ? CorrectionDirection.Removal : CorrectionDirection.Substitution;
    }

    /// <summary>
    /// Classifies a list-valued field from the set difference in both directions.
    /// </summary>
    /// <param name="proposed">The elements the extractor proposed.</param>
    /// <param name="inForce">The elements the catalog now claims.</param>
    public static CorrectionDirection ForList(
        IEnumerable<string?>? proposed,
        IEnumerable<string?>? inForce)
    {
        var before = Normalise(proposed);
        var after = Normalise(inForce);

        var gained = after.Except(before, StringComparer.OrdinalIgnoreCase).Any();
        var lost = before.Except(after, StringComparer.OrdinalIgnoreCase).Any();

        return (gained, lost) switch
        {
            (false, false) => CorrectionDirection.Confirmation,
            (true, false) => CorrectionDirection.Addition,
            (false, true) => CorrectionDirection.Removal,
            _ => CorrectionDirection.Substitution
        };
    }

    /// <summary>Wire name of a direction, lowercase, as the screen and the report read it.</summary>
    public static string Name(CorrectionDirection direction) => direction switch
    {
        CorrectionDirection.Confirmation => "confirmation",
        CorrectionDirection.Addition => "addition",
        CorrectionDirection.Removal => "removal",
        CorrectionDirection.Substitution => "substitution",
        _ => throw new ArgumentOutOfRangeException(nameof(direction), direction, "Unknown direction.")
    };

    private static FieldCorrection Scalar(string field, string? proposed, string? inForce) =>
        new(field, ForScalar(proposed, inForce), proposed ?? string.Empty, inForce ?? string.Empty);

    private static FieldCorrection List(string field, List<string>? proposed, string? inForceJson)
    {
        var before = Normalise(proposed);
        var after = ParseList(inForceJson);

        return new FieldCorrection(
            field,
            ForList(before, after),
            string.Join(", ", before),
            string.Join(", ", after));
    }

    private static bool Blank(string? value) => string.IsNullOrWhiteSpace(value);
}
