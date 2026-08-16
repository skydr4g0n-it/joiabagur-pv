using JoiabagurPV.Domain.Enums;

namespace JoiabagurPV.Domain.Entities;

/// <summary>
/// A group of products that are the same piece in several variants — the same ring in sizes S, M
/// and L — held as a business entity a person can correct.
/// </summary>
/// <remarks>
/// <para>
/// This replaces a generated text key that used to live inside the AI profile. The key broke on a
/// hyphen, so two variants of one piece landed in different groups and the system stopped warning
/// precisely where the warning mattered; an administrator could not fix it, and re-running the
/// enrichment overwrote any fix; and, having no identity of its own, there was nothing to compare
/// against in order to spot a product that ought to belong to an existing family.
/// </para>
/// <para>
/// <strong>Not a <see cref="Collection"/>.</strong> A collection groups by editorial criteria —
/// "Summer 2024" — and a product may belong to none of many unrelated ones. A family groups
/// variants of one piece and a product belongs to <strong>at most one</strong>, which is enforced
/// by a unique index on the membership rather than by any check in code.
/// </para>
/// </remarks>
public class ProductFamily : BaseEntity
{
    /// <summary>
    /// Maximum length of <see cref="Name"/>. Mirrors <c>Product.Name</c>: a family is named after
    /// the piece it groups.
    /// </summary>
    /// <remarks>
    /// Declared on the entity rather than on the EF configuration because both the persistence
    /// layer and the request validators need it, and the application layer cannot see
    /// infrastructure. A bound enforced in one place and guessed in the other is how a request
    /// passes validation and then fails at the database.
    /// </remarks>
    public const int NameMaxLength = 200;

    /// <summary>
    /// What the family is called — typically the piece without its variant, "Anillo erizo de mar".
    /// </summary>
    /// <remarks>
    /// Deliberately <strong>not unique</strong>. Two families may legitimately carry the same name,
    /// and a uniqueness constraint would force the assisted flow to invent disambiguating suffixes
    /// when approving hundreds of suggestions at once — which is the generated-key problem this
    /// entity exists to remove, reintroduced through the back door.
    /// </remarks>
    public required string Name { get; set; }

    /// <summary>Free-form note about the family. Optional.</summary>
    public string? Description { get; set; }

    /// <summary>
    /// The members of the family, each one a product with its variant label and its position.
    /// </summary>
    public ICollection<ProductFamilyMember> Members { get; set; } = new List<ProductFamilyMember>();

    // ── Provenance of the family itself ───────────────────────────────────────────────────────
    // Written by hand today, populated by the assisted-approval flow later. The three fields are
    // here from the first migration because that later change has no migration turn of its own.

    /// <summary>Whether this family was created by hand or approved from an AI suggestion.</summary>
    public FamilyOrigin Origin { get; set; } = FamilyOrigin.Manual;

    /// <summary>
    /// The administrator who approved the suggestion this family came from, when it came from one.
    /// </summary>
    /// <remarks>
    /// Null for a family created by hand: manual creation must not have to invent a reviewer, and a
    /// fabricated one would corrupt the very figure this column exists to make countable.
    /// </remarks>
    public Guid? ApprovedByUserId { get; set; }

    /// <summary>When that approval happened, stamped by the server. Null alongside the approver.</summary>
    public DateTime? ApprovedAt { get; set; }
}
