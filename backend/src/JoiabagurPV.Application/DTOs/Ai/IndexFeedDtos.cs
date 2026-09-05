namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>Discriminator values for feed items.</summary>
public static class IndexFeedKinds
{
    public const string Upsert = "upsert";
    public const string Tombstone = "tombstone";
}

/// <summary>Catalog tombstone reasons.</summary>
public static class CatalogTombstoneReasons
{
    public const string Deactivated = "deactivated";
    public const string Unapproved = "unapproved";
}

/// <summary>POS tombstone reason.</summary>
public static class PosTombstoneReasons
{
    public const string Unassigned = "unassigned";
}

/// <summary>Keyset cursor. Null <c>nextCursor</c> means the caller has exhausted the feed.</summary>
public sealed class IndexFeedCursorDto
{
    public DateTime Since { get; init; }

    public Guid SinceId { get; init; }
}

/// <summary>
/// One page of an indexing feed. <see cref="AggregateHash"/> is the digest of the global
/// indexable set, identical on every page of the same reading.
/// </summary>
/// <remarks>
/// Not sealed so <see cref="PosAvailabilityPageDto"/> can add the one field only that feed
/// has. The catalog page keeps this exact shape: serialisation follows the declared type, so
/// widening the base would have added a permanently null field to a contract that has no use
/// for it.
/// </remarks>
public class IndexFeedPageDto
{
    public IReadOnlyList<object> Items { get; init; } = [];

    public IndexFeedCursorDto? NextCursor { get; init; }

    public bool HasMore { get; init; }

    public int PageSize { get; init; }

    public string AggregateHash { get; init; } = string.Empty;
}

/// <summary>
/// One page of the POS availability feed. Adds <see cref="ComputedAsOf"/>, the instant the
/// sales windows on this page were counted against.
/// </summary>
/// <remarks>
/// Always populated, whether the instant came from <c>IndexFeed:SalesAsOf</c> or from the
/// wall clock: a windowed figure whose clock is not declared cannot be reproduced, and the
/// point of declaring it is lost if the field is present only when someone remembered to
/// configure one. The consumer persists it per row, because the feed is incremental and one
/// projection can end up holding rows counted against different instants.
/// </remarks>
public sealed class PosAvailabilityPageDto : IndexFeedPageDto
{
    public DateTime ComputedAsOf { get; init; }
}

/// <summary>
/// Catalog upsert: superset of <c>ProductSourceText</c> plus identifiers, price, band and watermark.
/// Materials and tags are arrays, not the persisted <c>*Json</c> strings. No provenance fields.
/// </summary>
public sealed class CatalogUpsertItemDto
{
    public string Kind { get; init; } = IndexFeedKinds.Upsert;

    public Guid ProductId { get; init; }

    public string Sku { get; init; } = string.Empty;

    public string Name { get; init; } = string.Empty;

    public string? Description { get; init; }

    public string? CollectionName { get; init; }

    public string? PieceType { get; init; }

    public IReadOnlyList<string> Materials { get; init; } = [];

    public string? StoneType { get; init; }

    public string? SizeLabel { get; init; }

    public Guid? FamilyId { get; init; }

    public string? FamilyName { get; init; }

    public string? VariantLabel { get; init; }

    public IReadOnlyList<string> ColorTags { get; init; } = [];

    public IReadOnlyList<string> StyleTags { get; init; } = [];

    public IReadOnlyList<string> OccasionTags { get; init; } = [];

    public decimal Price { get; init; }

    public string PriceBand { get; init; } = string.Empty;

    public bool IsActive { get; init; }

    public DateTime Watermark { get; init; }
}

/// <summary>Catalog tombstone. Source-text fields stay off this body.</summary>
public sealed class CatalogTombstoneItemDto
{
    public string Kind { get; init; } = IndexFeedKinds.Tombstone;

    public Guid ProductId { get; init; }

    public string Reason { get; init; } = string.Empty;

    public DateTime At { get; init; }
}

/// <summary>
/// POS availability upsert. Has no <c>Quantity</c> property — serialising stock exact would
/// leak inventory on a public API route.
/// </summary>
public sealed class PosAvailabilityUpsertItemDto
{
    public string Kind { get; init; } = IndexFeedKinds.Upsert;

    public Guid PointOfSaleId { get; init; }

    public Guid ProductId { get; init; }

    public string QtyBucket { get; init; } = string.Empty;

    public bool IsAssignedHint { get; init; }

    public int Sales30d { get; init; }

    public int Sales90d { get; init; }

    public DateTime? LastSaleAt { get; init; }

    public DateTime Watermark { get; init; }
}

/// <summary>POS tombstone for an unassigned inventory row.</summary>
public sealed class PosAvailabilityTombstoneItemDto
{
    public string Kind { get; init; } = IndexFeedKinds.Tombstone;

    public Guid PointOfSaleId { get; init; }

    public Guid ProductId { get; init; }

    public string Reason { get; init; } = PosTombstoneReasons.Unassigned;

    public DateTime At { get; init; }
}
