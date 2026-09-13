using System.Text.Json;
using JoiabagurPV.Application.Interfaces;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// The evidence stratum a profile belongs to, derived from how its sensitive fields were
/// established rather than from how sure the extractor claimed to be.
/// </summary>
/// <remarks>
/// The confidence column is not a probability: the extraction service never copies the model's
/// own score, and emits a four-value staircase instead — a rule produced it, the vocabulary
/// phrase is literally in the source text, the model asserted it with no such phrase, or it is
/// absent. Stratifying on that staircase is therefore stratifying on the kind of evidence behind
/// a value, which is what makes the strata mean different things to a reviewer.
/// </remarks>
public enum EvidenceStratum
{
    /// <summary>Nothing was extracted for at least one sensitive field. Is the emptiness real?</summary>
    Absence = 1,

    /// <summary>A value was asserted whose phrase is not in the text. Removals are expected here.</summary>
    NoSpan = 2,

    /// <summary>Every value has a phrase behind it. Only an omission is still findable here.</summary>
    WithSpan = 3
}

/// <summary>
/// Which stratum a profile is in, and which field put it there.
/// </summary>
/// <param name="Stratum">The stratum.</param>
/// <param name="DecidingField">The sensitive field with the weakest evidence.</param>
/// <param name="WeakestConfidence">That field's confidence, after the absent-stone rule.</param>
public record ProfileStratumAssignment(
    EvidenceStratum Stratum,
    string DecidingField,
    double WeakestConfidence);

/// <summary>
/// Assigns a profile to exactly one evidence stratum. Pure: no database, no clock, no HTTP.
/// </summary>
/// <remarks>
/// <para>
/// <strong>One implementation, two consumers.</strong> The review queue and the metrics report
/// both call this. Computing the stratum twice is how a queue and a report begin to disagree
/// about the same profile without either of them being obviously wrong, and the disagreement
/// would surface as a correction rate attributed to the wrong population.
/// </para>
/// <para>
/// An absent stone type does not lower the stratum. Most jewellery carries no stone, so reading
/// its absence as missing evidence would drag the majority of a clean catalog into the stratum
/// reserved for values nothing was found for — and spend the scarcest attention in the batch
/// confirming that a plain silver ring has no emerald in it.
/// </para>
/// </remarks>
public static class ProfileEvidenceStratum
{
    /// <summary>Wire code of the stratum of absence.</summary>
    public const string AbsenceCode = "A";

    /// <summary>Wire code of the stratum of values asserted without a textual span.</summary>
    public const string NoSpanCode = "B";

    /// <summary>Wire code of the stratum of values asserted with one.</summary>
    public const string WithSpanCode = "C";

    /// <summary>
    /// Confidence assumed for a sensitive field the profile carries no entry for.
    /// </summary>
    /// <remarks>
    /// The same value the extractor writes for an absent field, so a field missing from the
    /// document and a field recorded as absent are treated identically. They mean the same thing
    /// and the difference between them is an accident of serialisation.
    /// </remarks>
    private const double AbsentConfidence = 0.20;

    /// <summary>Upper bound of the stratum of absence.</summary>
    private const double AbsenceCeiling = 0.20;

    /// <summary>Upper bound of the stratum of values asserted without a span.</summary>
    private const double NoSpanCeiling = 0.45;

    /// <summary>
    /// The fields the stratum is computed from, in the order that breaks a tie.
    /// </summary>
    /// <remarks>
    /// The size label is deliberately absent. It is the only field the extractor ever produces
    /// from a deterministic rule, so it carries confidence 1,00 wherever it exists and would
    /// never be the weakest — including it would add a term that cannot change the outcome and
    /// could only mislead a reader into thinking it might.
    /// </remarks>
    public static readonly IReadOnlyList<string> StratumFields =
    [
        ProfileFields.PieceType,
        ProfileFields.Materials,
        ProfileFields.StoneType
    ];

    /// <summary>
    /// Assigns the stratum from a profile's per-field confidence.
    /// </summary>
    /// <param name="fieldConfidence">Confidence per field, keyed as the profile stores it.</param>
    /// <returns>The stratum, the field that decided it, and that field's confidence.</returns>
    public static ProfileStratumAssignment Assign(IReadOnlyDictionary<string, double> fieldConfidence)
    {
        ArgumentNullException.ThrowIfNull(fieldConfidence);

        var weakestField = StratumFields[0];
        var weakest = ConfidenceOf(fieldConfidence, StratumFields[0]);

        // Strictly-less-than, walking a fixed order: a tie keeps the earlier field, so the same
        // profile always names the same deciding field. An unstable answer here would read as a
        // different diagnosis of the same row every time the queue is drawn.
        foreach (var field in StratumFields.Skip(1))
        {
            var confidence = ConfidenceOf(fieldConfidence, field);
            if (confidence < weakest)
            {
                weakest = confidence;
                weakestField = field;
            }
        }

        var stratum = weakest <= AbsenceCeiling
            ? EvidenceStratum.Absence
            : weakest <= NoSpanCeiling
                ? EvidenceStratum.NoSpan
                : EvidenceStratum.WithSpan;

        return new ProfileStratumAssignment(stratum, weakestField, weakest);
    }

    /// <summary>
    /// Assigns the stratum from the raw confidence document a profile carries.
    /// </summary>
    /// <param name="fieldConfidenceJson">The stored <c>FieldConfidenceJson</c>.</param>
    /// <returns>The stratum, the field that decided it, and that field's confidence.</returns>
    /// <remarks>
    /// A document that cannot be read is treated as carrying no confidence at all, which lands
    /// the profile in the stratum of absence. That is the honest reading: a profile whose
    /// provenance is unintelligible has no evidence behind its values, whatever they say.
    /// </remarks>
    public static ProfileStratumAssignment AssignFromJson(string? fieldConfidenceJson) =>
        Assign(ParseConfidence(fieldConfidenceJson));

    /// <summary>
    /// Reads a stored confidence document into a dictionary.
    /// </summary>
    /// <param name="fieldConfidenceJson">The stored <c>FieldConfidenceJson</c>.</param>
    /// <returns>Confidence per field; empty when the document is absent or unreadable.</returns>
    public static IReadOnlyDictionary<string, double> ParseConfidence(string? fieldConfidenceJson)
    {
        if (string.IsNullOrWhiteSpace(fieldConfidenceJson))
        {
            return new Dictionary<string, double>(StringComparer.Ordinal);
        }

        try
        {
            return JsonSerializer.Deserialize<Dictionary<string, double>>(fieldConfidenceJson)
                ?? new Dictionary<string, double>(StringComparer.Ordinal);
        }
        catch (JsonException)
        {
            return new Dictionary<string, double>(StringComparer.Ordinal);
        }
    }

    /// <summary>Wire code of a stratum.</summary>
    public static string Code(EvidenceStratum stratum) => stratum switch
    {
        EvidenceStratum.Absence => AbsenceCode,
        EvidenceStratum.NoSpan => NoSpanCode,
        EvidenceStratum.WithSpan => WithSpanCode,
        _ => throw new ArgumentOutOfRangeException(nameof(stratum), stratum, "Unknown stratum.")
    };

    /// <summary>Parses a wire code, or null when it names no stratum.</summary>
    public static EvidenceStratum? TryParse(string? code) => code?.Trim().ToUpperInvariant() switch
    {
        AbsenceCode => EvidenceStratum.Absence,
        NoSpanCode => EvidenceStratum.NoSpan,
        WithSpanCode => EvidenceStratum.WithSpan,
        _ => null
    };

    /// <summary>Every stratum, in reviewing order.</summary>
    public static IReadOnlyList<EvidenceStratum> All =>
        [EvidenceStratum.Absence, EvidenceStratum.NoSpan, EvidenceStratum.WithSpan];

    /// <summary>
    /// One sensitive field's confidence, after the absent-stone rule.
    /// </summary>
    /// <remarks>
    /// <para>
    /// The stone is the exception, and it is the whole reason this is a method rather than a
    /// dictionary lookup with a single default.
    /// </para>
    /// <para>
    /// Both spellings of "no stone" are treated alike: the key missing from the document, and
    /// the key present carrying the confidence the extractor writes for an absent value. They
    /// assert the same thing about the piece, and which one gets written depends only on whether
    /// the extractor emitted a stone object at all. <strong>This widens nothing in practice:</strong>
    /// measured over the 1.168 approved profiles on 2026-09-13, stone confidence is either
    /// missing (540), 0,85 (359) or 0,45 (269) — no row carries 0,20 — so the second spelling
    /// never fires and the published stratum sizes of A 122 · B 285 · C 761 are unaffected.
    /// </para>
    /// </remarks>
    private static double ConfidenceOf(IReadOnlyDictionary<string, double> confidence, string field)
    {
        if (field == ProfileFields.StoneType)
        {
            return confidence.TryGetValue(field, out var stone) && stone > AbsenceCeiling
                ? stone
                : 1.0;
        }

        return confidence.TryGetValue(field, out var stored) ? stored : AbsentConfidence;
    }
}
