using FluentAssertions;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;
using JoiabagurPV.Domain.Enums;
using Microsoft.Extensions.Options;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// The hybrid review policy: which fields a person still has to look at.
/// </summary>
/// <remarks>
/// No database, no HTTP, no container. That is the point of the policy being a pure class: the
/// rule it encodes is the part of this capability that has to be obviously right, and a test
/// that needs a container to check a boolean would be run far less often.
/// </remarks>
public class ProfileReviewPolicyTests
{
    private const double TagThreshold = 0.80;

    private static ProfileReviewPolicy CreatePolicy(double tagThreshold = TagThreshold) =>
        new(Options.Create(new ProfileReviewOptions
        {
            TagAutoApproveThreshold = tagThreshold,
            MinimumFieldConfidence = 0.50
        }));

    /// <summary>
    /// A proposal in which nothing needs review: every sensitive field comes from a rule and
    /// every tag clears the threshold. Individual tests spoil exactly one thing.
    /// </summary>
    private static AiProposedProfile CleanProposal() => new()
    {
        ProductId = "P-1",
        Sku = "JBG-1",
        PieceType = Text("anillo", 0.95, AiFieldSource.Rule),
        Materials = List(["plata"], 0.95, AiFieldSource.Rule),
        StoneType = Text("ninguna", 0.95, AiFieldSource.Rule),
        SizeLabel = Text("M", 1.0, AiFieldSource.Rule),
        ColorTags = List(["dorado"], 0.95, AiFieldSource.Inferred),
        StyleTags = List(["marino"], 0.95, AiFieldSource.Inferred),
        OccasionTags = List(["regalo"], 0.95, AiFieldSource.Inferred)
    };

    private static AiProposedText Text(string value, double confidence, AiFieldSource source) =>
        new() { Value = value, Confidence = confidence, Source = source };

    private static AiProposedList List(string[] value, double confidence, AiFieldSource source) =>
        new() { Value = [.. value], Confidence = confidence, Source = source };

    [Theory]
    [InlineData(ProfileFields.PieceType)]
    [InlineData(ProfileFields.Materials)]
    [InlineData(ProfileFields.StoneType)]
    [InlineData(ProfileFields.SizeLabel)]
    public void Routing_WhenSensitiveFieldInferred_MarksPendingReview(string field)
    {
        var proposal = CleanProposal();

        // Spoil exactly one field: high confidence, but inferred rather than derived by a rule.
        switch (field)
        {
            case ProfileFields.PieceType:
                proposal.PieceType = Text("anillo", 0.99, AiFieldSource.Inferred);
                break;
            case ProfileFields.Materials:
                proposal.Materials = List(["plata"], 0.99, AiFieldSource.Inferred);
                break;
            case ProfileFields.StoneType:
                proposal.StoneType = Text("circonita", 0.99, AiFieldSource.Inferred);
                break;
            case ProfileFields.SizeLabel:
                proposal.SizeLabel = Text("M", 0.99, AiFieldSource.Inferred);
                break;
        }

        var outcome = CreatePolicy().Route(proposal);

        outcome.Status.Should().Be(ProfileReviewStatus.Pending,
            "an attribute a model inferred and nobody vouched for reaches a customer through the "
            + "operator, however confident the model claims to be");
        outcome.FieldsPendingReview.Should().Equal([field],
            "the per-field detail has to name which field caused it, or the review screen cannot "
            + "highlight anything");
    }

    [Fact]
    public void Routing_WhenSensitiveFieldFromRule_DoesNotRequireReview()
    {
        var outcome = CreatePolicy().Route(CleanProposal());

        outcome.Status.Should().Be(ProfileReviewStatus.Approved);
        outcome.FieldsPendingReview.Should().BeEmpty(
            "a size read off the SKU by a regex is not a guess; asking a person to re-read it is "
            + "the cost that makes reviewing a thousand products impossible");
        outcome.FieldSource[ProfileFields.SizeLabel].Should().Be(ProfileFieldSources.Rule,
            "the provenance stays recorded so the exemption is auditable afterwards");
    }

    [Fact]
    public void Routing_WhenTagConfidenceAboveThreshold_AutoApproves()
    {
        var proposal = CleanProposal();
        proposal.ColorTags = List(["dorado"], TagThreshold, AiFieldSource.Inferred);

        var outcome = CreatePolicy().Route(proposal);

        outcome.Status.Should().Be(ProfileReviewStatus.Approved,
            "a wrongly tagged piece ranks slightly worse; it does not mis-sell anything");
        outcome.FieldsPendingReview.Should().BeEmpty();
    }

    [Fact]
    public void Routing_WhenTagConfidenceBelowThreshold_MarksPendingReview()
    {
        var proposal = CleanProposal();
        proposal.StyleTags = List(["marino"], TagThreshold - 0.01, AiFieldSource.Inferred);

        var outcome = CreatePolicy().Route(proposal);

        outcome.Status.Should().Be(ProfileReviewStatus.Pending);
        outcome.FieldsPendingReview.Should().Equal([ProfileFields.StyleTags]);
    }

    /// <summary>
    /// Guards the reason the threshold lives in configuration: it is meant to be recalibrated
    /// against the golden set, and a compiled value is one nobody recalibrates.
    /// </summary>
    [Fact]
    public void Routing_ThresholdComesFromConfiguration_NotFromAConstant()
    {
        var proposal = CleanProposal();
        proposal.ColorTags = List(["dorado"], 0.60, AiFieldSource.Inferred);

        CreatePolicy(tagThreshold: 0.80).Route(proposal).Status
            .Should().Be(ProfileReviewStatus.Pending);

        CreatePolicy(tagThreshold: 0.50).Route(proposal).Status
            .Should().Be(ProfileReviewStatus.Approved);
    }

    [Fact]
    public void Routing_RecordsConfidenceAndSourceForEveryPresentField()
    {
        var outcome = CreatePolicy().Route(CleanProposal());

        outcome.FieldConfidence.Keys.Should().BeEquivalentTo(
            [
                ProfileFields.PieceType, ProfileFields.Materials, ProfileFields.StoneType,
                ProfileFields.SizeLabel, ProfileFields.ColorTags, ProfileFields.StyleTags,
                ProfileFields.OccasionTags
            ]);
        outcome.FieldSource.Should().HaveSameCount(outcome.FieldConfidence);
    }

    [Fact]
    public void Routing_WhenOptionalFieldIsAbsent_DoesNotInventIt()
    {
        var proposal = CleanProposal();
        proposal.StoneType = null;

        var outcome = CreatePolicy().Route(proposal);

        outcome.FieldConfidence.Should().NotContainKey(ProfileFields.StoneType,
            "a piece with no stone is not a piece with an unknown stone; recording a confidence "
            + "for a field that was never proposed would put it in the correction-rate denominator");
        outcome.Status.Should().Be(ProfileReviewStatus.Approved);
    }

    /// <summary>
    /// Family membership is listed among the sensitive attributes in the design and is
    /// deliberately absent here: it belongs to the product-family capability, and a second
    /// opinion about it in this one would create two truths about the same thing.
    /// </summary>
    [Fact]
    public void Routing_IgnoresFamilyAndVariantProposals()
    {
        var proposal = CleanProposal();
        proposal.FamilyId = Text("F-000", 0.10, AiFieldSource.Inferred);
        proposal.VariantLabel = Text("M", 0.10, AiFieldSource.Inferred);

        var outcome = CreatePolicy().Route(proposal);

        outcome.Status.Should().Be(ProfileReviewStatus.Approved,
            "a low-confidence family hint must not send a profile to review for a decision this "
            + "capability does not make");
        outcome.FieldConfidence.Should().NotContainKey("family_id");
    }
}
