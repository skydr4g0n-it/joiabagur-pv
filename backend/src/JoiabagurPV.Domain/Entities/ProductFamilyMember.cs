namespace JoiabagurPV.Domain.Entities;

/// <summary>
/// One product's membership of a <see cref="ProductFamily"/>, carrying what tells this variant
/// from its siblings and where it sits among them.
/// </summary>
/// <remarks>
/// <para>
/// The variant label and the position are properties of the <em>relationship</em>, not of the
/// product: the same ring is "S" only with respect to the family it belongs to. That is why this
/// is a row of its own rather than two columns on <see cref="Product"/>.
/// </para>
/// <para>
/// There is deliberately no navigation property from <see cref="Product"/>, and the catalog gains
/// no column. The foreign key is declared from this side alone, following the same reasoning the
/// AI profile applied: a model that offers no traversal is one nobody reaches by accident.
/// </para>
/// <para>
/// <strong>These rows are not stable.</strong> Membership is declared as a whole list, and the
/// declaration is written by deleting every row and inserting the new set — updating in place is
/// what turns a reorder into a cycle the change tracker cannot order. Nothing anywhere references
/// <see cref="BaseEntity.Id"/> of a membership, so the churn costs nothing; the one consequence is
/// that <see cref="BaseEntity.CreatedAt"/> means "when the list was last written", <strong>not</strong>
/// "when this product joined the family".
/// </para>
/// </remarks>
public class ProductFamilyMember : BaseEntity
{
    /// <summary>
    /// Maximum length of <see cref="VariantLabel"/>. Generous on purpose: "talla 12 ajustable" fits
    /// comfortably, and the vocabulary of labels is closed by the assisted flow rather than here.
    /// </summary>
    /// <remarks>
    /// On the entity rather than on the EF configuration so the validators can see it too: the
    /// application layer does not reference infrastructure, and a bound enforced in one place and
    /// guessed in the other is how a request passes validation and then fails at the database.
    /// </remarks>
    public const int VariantLabelMaxLength = 50;

    /// <summary>The family this membership belongs to.</summary>
    public Guid ProductFamilyId { get; set; }

    /// <summary>Navigation back to the owning family.</summary>
    public ProductFamily? Family { get; set; }

    /// <summary>
    /// The product that is a member. Unique across every family: a product belongs to at most one,
    /// and that is enforced by the database, not by a check in the service.
    /// </summary>
    /// <remarks>
    /// An application check leaves a race open between two administrators, and — worse — a second
    /// membership raises no error anywhere. It would surface downstream as two family identifiers
    /// emitted for one product and as incoherent documents in the vector index.
    /// </remarks>
    public Guid ProductId { get; set; }

    /// <summary>
    /// What distinguishes this variant from its siblings — "S", "M", "L", "ajustable", "talla 12".
    /// </summary>
    /// <remarks>
    /// Optional, because a member whose variant has not been determined yet is a legitimate state
    /// that the rule-based warnings are meant to report rather than a defect to block on. Two
    /// members of one family carrying the <em>same</em> label are a defect, though, and are rejected:
    /// labels that cannot be told apart defeat the point of the family. PostgreSQL treats nulls as
    /// distinct, so a single unique index over family and label gives both behaviours at once.
    /// </remarks>
    public string? VariantLabel { get; set; }

    /// <summary>
    /// Where this member sits among its siblings, starting at zero.
    /// </summary>
    /// <remarks>
    /// Derived from the position in the declared list, never sent by the caller, which makes gaps
    /// and duplicates impossible to express. Unique within the family all the same: two members
    /// sharing a position produce a sibling list whose order differs between reads, and a
    /// non-deterministic order in a disambiguation screen is worse than no order at all.
    /// </remarks>
    public int SortOrder { get; set; }
}
