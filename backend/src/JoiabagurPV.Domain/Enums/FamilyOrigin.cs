namespace JoiabagurPV.Domain.Enums;

/// <summary>
/// How a <see cref="Entities.ProductFamily"/> came to exist.
/// </summary>
/// <remarks>
/// Grouping ~350 families by hand is not viable, and leaving them to a model is what the design
/// review rejected outright: a family a model invented and nobody confirmed is exactly the failure
/// this entity replaced a generated text key to avoid. The agreed flow is mixed — the AI proposes,
/// an administrator approves or edits, and the family stays editable afterwards — so the data has
/// to be able to say which of the two produced each row.
/// <para>
/// Only <see cref="Manual"/> is written today. <see cref="AiApproved"/> exists from the first
/// migration because the change that will write it has no migration turn of its own, and adding a
/// column later would cost one of the six the plan allows.
/// </para>
/// </remarks>
public enum FamilyOrigin
{
    /// <summary>
    /// An administrator created the family directly, without any suggestion behind it.
    /// </summary>
    Manual = 1,

    /// <summary>
    /// A person approved a suggestion the AI produced. The approving user and the moment of
    /// approval are recorded alongside, which is what makes the human step countable rather than
    /// merely claimed.
    /// </summary>
    AiApproved = 2
}
