using JoiabagurPV.Domain.Enums;

namespace JoiabagurPV.Domain.Entities;

/// <summary>
/// A person's judgement about one product's relationship with one family.
/// </summary>
/// <remarks>
/// <para>
/// <strong>The pair is the identity, not the membership.</strong> A verdict is recorded about
/// <c>(product, family)</c> whether or not the product currently belongs to that family, because
/// the two things a reviewer answers are the same question from opposite sides: a member the
/// vectors do not support, and an unassigned product that looks like it belongs. Hanging the
/// record off <see cref="ProductFamilyMember"/> would have covered only the first — an orphan has
/// no membership row to carry it.
/// </para>
/// <para>
/// <strong>One row does three jobs.</strong> It is the dismissal list, so a candidate a person
/// rejected never returns; it is the audit's memory, so a queue that was worked through stays
/// worked through; and it is the per-item approval stamp that C18a deferred here, because the 156
/// families it wrote all record the administrator who fired one batch rather than a judgement
/// about any particular family.
/// </para>
/// <para>
/// <strong>Lives in the transactional schema, not beside the index.</strong> The vectors that
/// raise these questions belong to the AI service, and putting the answers there would have been
/// state nothing invalidates: <c>ai.product_document</c> is a projection that gets tombstoned and
/// rebuilt, so a table beside it inherits none of its lifecycle, deleting a family would leave
/// orphan rows nothing cleans, and the reviewer would be an opaque identifier the screen cannot
/// resolve to a name. Here the foreign keys settle all three without any code.
/// </para>
/// </remarks>
public class FamilyReviewVerdict : BaseEntity
{
    /// <summary>Maximum length of <see cref="Note"/>.</summary>
    /// <remarks>
    /// On the entity rather than on the EF configuration so the request validators can see it:
    /// the application layer does not reference infrastructure, and a bound enforced in one place
    /// and guessed in the other is how a request passes validation and then fails at the database.
    /// </remarks>
    public const int NoteMaxLength = 500;

    /// <summary>The product the judgement is about.</summary>
    public Guid ProductId { get; set; }

    /// <summary>The family the judgement is about.</summary>
    /// <remarks>
    /// Deleting the family takes its verdicts with it. A judgement about a family that no longer
    /// exists answers a question nobody can ask, and keeping it would leave the audit filtering
    /// against rows that point at nothing.
    /// </remarks>
    public Guid ProductFamilyId { get; set; }

    /// <summary>Navigation to the family, so the cascade is declared from the owning side.</summary>
    public ProductFamily? Family { get; set; }

    /// <summary>Whether the product belongs with the family.</summary>
    public FamilyReviewOutcome Outcome { get; set; }

    /// <summary>The administrator who decided.</summary>
    public Guid ReviewedByUserId { get; set; }

    /// <summary>When the decision was made, stamped by the server.</summary>
    public DateTime ReviewedAt { get; set; }

    /// <summary>
    /// The margin the audit reported at the moment of the decision, when it came from the audit.
    /// </summary>
    /// <remarks>
    /// Kept so a stale verdict can be <em>shown</em> as stale — "reviewed at T with margin 0.16;
    /// today 0.31" — rather than silently reopened. Automatic invalidation was considered and
    /// rejected: it needs a rule for how much movement matters, and nobody would maintain it.
    /// Null for a judgement a person made outside the audit, which is a legitimate state and not a
    /// missing value.
    /// </remarks>
    public double? MarginAtReview { get; set; }

    /// <summary>Free-form note about why. Optional.</summary>
    public string? Note { get; set; }
}
