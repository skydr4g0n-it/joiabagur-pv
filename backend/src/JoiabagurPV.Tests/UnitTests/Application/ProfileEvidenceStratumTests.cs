using FluentAssertions;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// The evidence stratum: which question a reviewer is being asked about a profile.
/// </summary>
/// <remarks>
/// Pure, and tested as such. The stratum decides both what enters the batch and how the
/// published rate is broken down, so an error here would not surface as a failure — it would
/// surface as a correction rate attributed to the wrong population, which reads as a finding.
/// </remarks>
public class ProfileEvidenceStratumTests
{
    private const double Span = 0.85;
    private const double NoSpan = 0.45;
    private const double Absent = 0.20;

    /// <summary>
    /// A profile whose three sensitive fields all carry a textual span. Individual tests spoil
    /// exactly one of them.
    /// </summary>
    private static Dictionary<string, double> WithSpanEverywhere() => new(StringComparer.Ordinal)
    {
        [ProfileFields.PieceType] = Span,
        [ProfileFields.Materials] = Span,
        [ProfileFields.StoneType] = Span,
        [ProfileFields.SizeLabel] = 1.0
    };

    [Fact]
    public void Stratum_StoneTypeAbsent_DoesNotLowerStratum()
    {
        // A ring of silver, described as such, with no stone — which is most of the catalog.
        var confidence = WithSpanEverywhere();
        confidence.Remove(ProfileFields.StoneType);

        var assignment = ProfileEvidenceStratum.Assign(confidence);

        assignment.Stratum.Should().Be(EvidenceStratum.WithSpan);
        assignment.DecidingField.Should().NotBe(ProfileFields.StoneType);
    }

    [Fact]
    public void Stratum_StoneTypeRecordedAsAbsent_DoesNotLowerStratum()
    {
        // The same piece, but with the absence written down rather than left out. A profile
        // cannot land in a different stratum for a difference that is one of serialisation.
        var confidence = WithSpanEverywhere();
        confidence[ProfileFields.StoneType] = Absent;

        ProfileEvidenceStratum.Assign(confidence).Stratum.Should().Be(EvidenceStratum.WithSpan);
    }

    [Theory]
    [InlineData(ProfileFields.PieceType)]
    [InlineData(ProfileFields.Materials)]
    public void Stratum_SensitiveFieldAbsent_IsStratumOfAbsence(string field)
    {
        var confidence = WithSpanEverywhere();
        confidence[field] = Absent;

        var assignment = ProfileEvidenceStratum.Assign(confidence);

        assignment.Stratum.Should().Be(EvidenceStratum.Absence);
        assignment.DecidingField.Should().Be(field);
    }

    [Theory]
    [InlineData(ProfileFields.PieceType)]
    [InlineData(ProfileFields.Materials)]
    [InlineData(ProfileFields.StoneType)]
    public void Stratum_SensitiveFieldAssertedWithoutSpan_IsStratumOfNoSpan(string field)
    {
        var confidence = WithSpanEverywhere();
        confidence[field] = NoSpan;

        var assignment = ProfileEvidenceStratum.Assign(confidence);

        assignment.Stratum.Should().Be(EvidenceStratum.NoSpan);
        assignment.DecidingField.Should().Be(field);
    }

    [Fact]
    public void Stratum_TakesTheWorstField_NotTheAverage()
    {
        // Two fields with a span and one without. An average would put this in the stratum of
        // spans and the reviewer would be asked "does anything seem to be missing?" about a
        // profile whose actual defect is a value the text never mentions.
        var confidence = WithSpanEverywhere();
        confidence[ProfileFields.Materials] = NoSpan;

        ProfileEvidenceStratum.Assign(confidence).Stratum.Should().Be(EvidenceStratum.NoSpan);
    }

    [Fact]
    public void Stratum_SizeLabelFromRule_DoesNotRaiseStratum()
    {
        // The only field the extractor ever produces from a rule, and therefore the only one
        // that always carries 1,00. Letting it into the computation would say nothing, but a
        // reader would reasonably assume it might.
        var confidence = WithSpanEverywhere();
        confidence[ProfileFields.Materials] = Absent;
        confidence[ProfileFields.SizeLabel] = 1.0;

        ProfileEvidenceStratum.Assign(confidence).Stratum.Should().Be(EvidenceStratum.Absence);
    }

    [Fact]
    public void Stratum_ComputedIdenticallyForQueueAndMetrics()
    {
        // The queue reads the stored document; the metrics report reads the same document for
        // the same profile. Two entry points, one answer — if these ever diverge, a batch and
        // the figures drawn from it would describe different populations while both looked right.
        var profiles = new[]
        {
            """{"piece_type":0.85,"materials":0.85,"stone_type":0.85}""",
            """{"piece_type":0.85,"materials":0.45,"stone_type":0.85}""",
            """{"piece_type":0.20,"materials":0.85}""",
            """{"piece_type":0.85,"materials":0.85}""",
            """{"materials":0.45,"stone_type":0.20}""",
            "{}"
        };

        foreach (var document in profiles)
        {
            var fromQueue = ProfileEvidenceStratum.AssignFromJson(document);
            var fromMetrics = ProfileEvidenceStratum.Assign(
                ProfileEvidenceStratum.ParseConfidence(document));

            fromMetrics.Should().BeEquivalentTo(
                fromQueue,
                because: $"the queue and the metrics must agree about {document}");
        }
    }

    [Fact]
    public void Stratum_UnreadableConfidenceDocument_IsStratumOfAbsence()
    {
        // A profile whose provenance cannot be read has no evidence behind its values, whatever
        // they claim. Reading it as the stratum of spans would flatter it on the strength of a
        // document nobody could parse.
        ProfileEvidenceStratum.AssignFromJson("not json at all").Stratum
            .Should().Be(EvidenceStratum.Absence);
    }

    [Theory]
    [InlineData(EvidenceStratum.Absence, "A")]
    [InlineData(EvidenceStratum.NoSpan, "B")]
    [InlineData(EvidenceStratum.WithSpan, "C")]
    public void Stratum_CodeRoundTrips(EvidenceStratum stratum, string code)
    {
        ProfileEvidenceStratum.Code(stratum).Should().Be(code);
        ProfileEvidenceStratum.TryParse(code).Should().Be(stratum);
        ProfileEvidenceStratum.TryParse(code.ToLowerInvariant()).Should().Be(stratum);
    }

    [Fact]
    public void Stratum_UnknownCode_ParsesToNothing()
    {
        ProfileEvidenceStratum.TryParse("D").Should().BeNull();
        ProfileEvidenceStratum.TryParse(null).Should().BeNull();
    }
}
