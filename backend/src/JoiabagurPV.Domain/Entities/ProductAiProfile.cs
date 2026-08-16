using JoiabagurPV.Domain.Enums;

namespace JoiabagurPV.Domain.Entities;

/// <summary>
/// The AI-proposed catalog attributes of one product, together with where each of them came
/// from and whether a person has vouched for them.
/// </summary>
/// <remarks>
/// <para>
/// This is the first data in the system produced by a model that the business will use to sell.
/// A search event only records what happened and nobody decides on it; a vector document is a
/// derived index that can be thrown away and rebuilt. A profile <em>asserts things about a
/// piece</em> — that it is silver, that it is a ring, that the size is M — and those assertions
/// reach an operator who repeats them to a customer. An attribute invented by a model and
/// vouched for by nobody is worse than an absent one, which is why every field here travels with
/// its confidence and its provenance instead of arriving anonymously.
/// </para>
/// <para>
/// There is deliberately no navigation property from <see cref="Product"/>. The catalog is the
/// authority on what a piece costs and whether it exists; it has no business being traversable
/// into a set of proposals, and a model that offers no traversal is one nobody reaches by
/// accident.
/// </para>
/// </remarks>
public class ProductAiProfile : BaseEntity
{
    /// <summary>
    /// The product this profile describes. One profile per product, enforced by a unique index
    /// rather than by an application check — a duplicate raises no error and would surface much
    /// later as duplicated documents in the vector index.
    /// </summary>
    public Guid ProductId { get; set; }

    // ── Values in force ───────────────────────────────────────────────────────────────────
    // These are what the catalog currently claims. A reviewer edits these; the proposal they
    // were derived from stays untouched in ProposedProfileJson so a correction remains visible.

    /// <summary>Kind of piece — ring, necklace, earring. Sensitive: an error sells the wrong thing.</summary>
    public string? PieceType { get; set; }

    /// <summary>
    /// Materials, as a JSON array. A list rather than a single value because a piece is
    /// routinely silver <em>and</em> gold-plated, and the retrieval filter is an overlap test.
    /// An empty array when there is no evidence — never null, and never a default material.
    /// </summary>
    public required string MaterialsJson { get; set; }

    /// <summary>Stone, when the piece has one. Sensitive.</summary>
    public string? StoneType { get; set; }

    /// <summary>Size label — S, M, L, a ring number. Sensitive: the wrong one does not fit.</summary>
    public string? SizeLabel { get; set; }

    /// <summary>Colour tags, as a JSON array. Commercial: an error costs a worse ranking, not a bad sale.</summary>
    public required string ColorTagsJson { get; set; }

    /// <inheritdoc cref="ColorTagsJson"/>
    public required string StyleTagsJson { get; set; }

    /// <inheritdoc cref="ColorTagsJson"/>
    public required string OccasionTagsJson { get; set; }

    // ── Provenance and quality ────────────────────────────────────────────────────────────

    /// <summary>
    /// Aggregate confidence over the fields actually present. Exists to order the review queue,
    /// nothing else: the decision to review a field is taken per field, never from this number.
    /// </summary>
    public decimal AiConfidence { get; set; }

    /// <summary>Confidence per field, as a JSON object keyed by field name.</summary>
    public required string FieldConfidenceJson { get; set; }

    /// <summary>
    /// Provenance per field — <c>rule</c> or <c>inferred</c> — as a JSON object keyed by field
    /// name. This is the column the whole review policy turns on: a sensitive field that came
    /// from a deterministic rule needs no human, and one a model inferred does.
    /// </summary>
    public required string FieldSourceJson { get; set; }

    /// <summary>
    /// The raw proposal, exactly as the AI service returned it. Written once per
    /// <see cref="SourceHash"/> and never edited afterwards.
    /// </summary>
    /// <remarks>
    /// Keeping it is what makes the correction rate of the extractor computable at all: the
    /// metric is the difference between this and the values in force. Stored as state rather
    /// than as an event log on purpose — a comparison of two columns cannot drift out of step
    /// with the data the way a parallel log can.
    /// </remarks>
    public required string ProposedProfileJson { get; set; }

    /// <summary>Provider model that produced the proposal, when the service reported one.</summary>
    public string? GeneratedByModel { get; set; }

    /// <summary>
    /// Version of the extraction prompt behind the proposal. Cheap to store and impossible to
    /// reconstruct afterwards, which is the whole reason it is here: the delivery is expected to
    /// show the measured impact of one prompt version against the next.
    /// </summary>
    public string? PromptVersion { get; set; }

    /// <summary>
    /// SHA-256 of the <strong>product inputs</strong> the proposal was derived from — SKU, name,
    /// description and collection, in a fixed order.
    /// </summary>
    /// <remarks>
    /// <strong>Not the same hash as the indexer's.</strong> The Python side computes its own
    /// <c>source_hash</c> over the canonical document text of an approved profile, to decide
    /// whether an embedding must be recomputed. This one covers the inputs, and answers two
    /// different questions: whether re-running a batch has to pay for a model call, and whether
    /// re-running it would overwrite work a person already did. The names are nearly identical
    /// and the meanings are not, so it is said here rather than left to be discovered.
    /// </remarks>
    public required string SourceHash { get; set; }

    // ── Review ────────────────────────────────────────────────────────────────────────────

    /// <summary>Where the profile stands. The indexing feed selects on this alone.</summary>
    public ProfileReviewStatus ReviewStatus { get; set; }

    /// <summary>Who put it there. The human-review metrics select on this alone.</summary>
    public ProfileReviewOrigin ReviewOrigin { get; set; }

    /// <summary>Reviewer, once a person has actually decided.</summary>
    public Guid? ReviewedByUserId { get; set; }

    /// <summary>When that decision was taken, stamped by the server.</summary>
    public DateTime? ReviewedAt { get; set; }

    /// <summary>
    /// How long the review took, in milliseconds, as measured by the browser.
    /// </summary>
    /// <remarks>
    /// Optional because the server cannot observe it: how long someone looks at a row is a fact
    /// of the client, not of the request. Left null for bulk approval by field, where a shared
    /// timestamp across forty rows would produce an average that flatters the process — a null
    /// drops out of the metric, a fabricated number corrupts it.
    /// </remarks>
    public int? ReviewDurationMs { get; set; }
}
