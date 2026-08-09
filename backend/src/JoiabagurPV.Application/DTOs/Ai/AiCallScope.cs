namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// Caller identity and point-of-sale scope carried into every jbg-ai call.
/// </summary>
/// <remarks>
/// <para>
/// This type <em>authorises nothing</em>. Whoever builds a scope has already validated that
/// the user is assigned to that point of sale, against <c>UserPointOfSale</c>. The client
/// only transports it.
/// </para>
/// <para>
/// <see cref="ForPointOfSale"/> is deliberately the only way to construct a scope, and it
/// requires a concrete point of sale. From C22 onward the <c>pos_id</c> claim becomes the
/// retriever's only hard filter, so a sentinel value such as "*" or "system" reaching it
/// would be a cross-POS leak wearing a convenience-parameter costume. Making that state
/// unconstructible is cheaper than asking people not to write it.
/// </para>
/// <para>
/// A sealed class rather than a record struct on purpose: every struct has an implicit
/// <c>default</c> value, which would be a scope with an empty point of sale and would
/// defeat the guarantee above. A private constructor on a class has no such hole.
/// </para>
/// <para>
/// Routes with no point of sale — catalog-wide enrichment and index sync — will need a
/// different scope. Adding it is the job of the first change that calls them (C08 or C13),
/// together with the jbg-ai rule that keeps such a scope away from retrieval routes.
/// </para>
/// </remarks>
public sealed class AiCallScope
{
    private AiCallScope(Guid userId, string role, Guid pointOfSaleId)
    {
        UserId = userId;
        Role = role;
        PointOfSaleId = pointOfSaleId;
    }

    /// <summary>Identifier of the user on whose behalf the call is made.</summary>
    public Guid UserId { get; }

    /// <summary>Role of that user.</summary>
    public string Role { get; }

    /// <summary>Point of sale the call is scoped to.</summary>
    public Guid PointOfSaleId { get; }

    /// <summary>
    /// Builds a scope for a concrete point of sale. The only construction path.
    /// </summary>
    /// <param name="userId">User the call is made for. Must not be empty.</param>
    /// <param name="role">Role of that user. Must not be blank.</param>
    /// <param name="pointOfSaleId">Point of sale the call is scoped to. Must not be empty.</param>
    /// <exception cref="ArgumentException">Any argument is empty or blank.</exception>
    public static AiCallScope ForPointOfSale(Guid userId, string role, Guid pointOfSaleId)
    {
        if (userId == Guid.Empty)
        {
            throw new ArgumentException("A gateway call scope requires a user.", nameof(userId));
        }

        if (string.IsNullOrWhiteSpace(role))
        {
            throw new ArgumentException("A gateway call scope requires a role.", nameof(role));
        }

        if (pointOfSaleId == Guid.Empty)
        {
            throw new ArgumentException(
                "A gateway call scope requires a concrete point of sale. There is no scope without one.",
                nameof(pointOfSaleId));
        }

        return new AiCallScope(userId, role, pointOfSaleId);
    }
}
