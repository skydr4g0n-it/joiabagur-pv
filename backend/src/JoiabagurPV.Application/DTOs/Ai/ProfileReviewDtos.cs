namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// What the review queue was asked for.
/// </summary>
/// <remarks>
/// The seed and the quota are overridable here for tests and for reproducing an earlier batch,
/// not for a reviewer to vary mid-session: a session that silently changed seed halfway would
/// produce a figure nobody could reconstruct, which is the one property the sampling exists to
/// provide.
/// </remarks>
public class ProfileReviewQueueRequest
{
    /// <summary>Largest page a caller may ask for.</summary>
    public const int MaxPageSize = 50;

    /// <summary>Restrict to one evidence stratum — <c>A</c>, <c>B</c> or <c>C</c>.</summary>
    public string? Stratum { get; set; }

    /// <summary>Page, one-based.</summary>
    public int Page { get; set; } = 1;

    /// <summary>Items per page, capped at <see cref="MaxPageSize"/>.</summary>
    public int PageSize { get; set; } = MaxPageSize;

    /// <summary>Overrides the configured sampling seed.</summary>
    public string? Seed { get; set; }

    /// <summary>Overrides the configured quota per stratum.</summary>
    public int? QuotaPerStratum { get; set; }
}

/// <summary>
/// What one stratum contributed to the batch, and what it holds in the corpus.
/// </summary>
/// <remarks>
/// <see cref="CorpusSize"/> travels with the batch because the published total is weighted by
/// the real size of each stratum and not by its size in the sample. Re-deriving it later from a
/// second query is the same mistake as computing the stratum twice.
/// </remarks>
public class ProfileReviewStratumDto
{
    /// <summary>Stratum code — <c>A</c>, <c>B</c> or <c>C</c>.</summary>
    public string Stratum { get; set; } = string.Empty;

    /// <summary>What the stratum means, in the reviewer's language.</summary>
    public string Label { get; set; } = string.Empty;

    /// <summary>
    /// The question the reviewer is being asked about this stratum's profiles.
    /// </summary>
    /// <remarks>
    /// Not decoration. Where every value already has a phrase behind it, the span check has
    /// asked "is the phrase present?" and answered yes, so the only thing a person can still
    /// add is what is <em>missing</em> — and asking "is it correct?" there is how a reviewer
    /// confirms an omission without reading the description to the end.
    /// </remarks>
    public string Question { get; set; } = string.Empty;

    /// <summary>How many profiles of this stratum the corpus holds.</summary>
    public int CorpusSize { get; set; }

    /// <summary>How many were asked for.</summary>
    public int Quota { get; set; }

    /// <summary>How many the draw actually produced.</summary>
    public int Drawn { get; set; }

    /// <summary>Whether the stratum ran out before its quota was met.</summary>
    public bool Exhausted { get; set; }
}

/// <summary>
/// One field of a profile, as the review screen has to show it.
/// </summary>
public class ProfileReviewFieldDto
{
    /// <summary>Field name, as the provenance documents key it.</summary>
    public string Field { get; set; } = string.Empty;

    /// <summary>Whether the field holds several values rather than one.</summary>
    public bool IsList { get; set; }

    /// <summary>The single value in force, when the field holds one.</summary>
    public string? Value { get; set; }

    /// <summary>The values in force, when the field holds a list.</summary>
    public List<string> Values { get; set; } = [];

    /// <summary>The single value the extractor proposed.</summary>
    public string? ProposedValue { get; set; }

    /// <summary>The values the extractor proposed.</summary>
    public List<string> ProposedValues { get; set; } = [];

    /// <summary>Confidence the extractor recorded, on the four-value evidence staircase.</summary>
    public double Confidence { get; set; }

    /// <summary>Provenance — <c>rule</c> or <c>inferred</c>.</summary>
    public string Source { get; set; } = string.Empty;

    /// <summary>Whether an error in this field reaches a customer.</summary>
    public bool Sensitive { get; set; }

    /// <summary>
    /// Whether the hybrid policy requires a person to vouch for this field.
    /// </summary>
    /// <remarks>
    /// Sensitive <em>and</em> inferred. A size read off a SKU by a regex is not a guess, so no
    /// amount of caution justifies a person re-reading it — that trade is what makes reviewing a
    /// catalog of this size conceivable at all.
    /// </remarks>
    public bool PendingReview { get; set; }

    /// <summary>Whether the value in force already differs from the proposal.</summary>
    public bool AlreadyCorrected { get; set; }
}

/// <summary>
/// One profile as it reaches the review screen, with the text it is judged against.
/// </summary>
public class ProfileReviewItemDto
{
    /// <summary>The product.</summary>
    public Guid ProductId { get; set; }

    /// <summary>Its SKU.</summary>
    public string Sku { get; set; } = string.Empty;

    /// <summary>Its full name.</summary>
    public string Name { get; set; } = string.Empty;

    /// <summary>
    /// Its description, or null when it has none.
    /// </summary>
    /// <remarks>
    /// The criterion a reviewer applies is whether the <strong>source text supports the
    /// value</strong>, never whether the value is true of the physical piece: the system holds
    /// no photographs and no visual embeddings, and the text of both the synthetic and the real
    /// portions of the corpus was written by a language model. So the text is not context here,
    /// it is the evidence, and it travels with every item.
    /// </remarks>
    public string? Description { get; set; }

    /// <summary>
    /// Whether the product has a description at all.
    /// </summary>
    /// <remarks>
    /// Carried explicitly so the screen can state the absence rather than render a blank. A gap
    /// where the evidence should be reads as "nothing worth saying", when what it means is that
    /// the reviewer has less to judge against than usual.
    /// </remarks>
    public bool HasDescription { get; set; }

    /// <summary>Stratum code — <c>A</c>, <c>B</c> or <c>C</c>.</summary>
    public string Stratum { get; set; } = string.Empty;

    /// <summary>The sensitive field whose evidence placed it in that stratum.</summary>
    public string StratumDecidingField { get; set; } = string.Empty;

    /// <summary>The question this stratum asks of the reviewer.</summary>
    public string Question { get; set; } = string.Empty;

    /// <summary>Every reviewed field, with its confidence, provenance and proposal.</summary>
    public List<ProfileReviewFieldDto> Fields { get; set; } = [];

    /// <summary>Where the profile stands.</summary>
    public string ReviewStatus { get; set; } = string.Empty;

    /// <summary>Who put it there.</summary>
    public string ReviewOrigin { get; set; } = string.Empty;

    /// <summary>Version of the extraction prompt behind the proposal.</summary>
    public string? PromptVersion { get; set; }
}

/// <summary>
/// The stratified batch, with the seed that produced it.
/// </summary>
public class ProfileReviewQueueDto
{
    /// <summary>
    /// The seed this batch was drawn with.
    /// </summary>
    /// <remarks>
    /// Echoed back so the figure a session produces can be tied to the batch that produced it
    /// without anyone having to remember what the configuration said at the time.
    /// </remarks>
    public string Seed { get; set; } = string.Empty;

    /// <summary>What each stratum contributed, and what it holds.</summary>
    public List<ProfileReviewStratumDto> Strata { get; set; } = [];

    /// <summary>The page of items asked for.</summary>
    public List<ProfileReviewItemDto> Items { get; set; } = [];

    /// <summary>Items in the whole batch, across every page.</summary>
    public int TotalCount { get; set; }

    /// <summary>Page returned, one-based.</summary>
    public int Page { get; set; }

    /// <summary>Items per page.</summary>
    public int PageSize { get; set; }
}

/// <summary>
/// One reviewer's judgement on one profile.
/// </summary>
/// <remarks>
/// <para>
/// The values are a <strong>full declaration of what the catalog should claim</strong> after the
/// review, not a patch. A field omitted from a patch and a field the reviewer deliberately
/// cleared are indistinguishable, and telling those two apart is exactly what the removal
/// direction measures — so the request carries everything the screen was showing.
/// </para>
/// <para>
/// The reviewer and the instant are absent on purpose: the server stamps both. A body that could
/// name its own reviewer would let the metric be attributed to somebody who reviewed nothing.
/// </para>
/// </remarks>
public class RecordProfileReviewRequest
{
    /// <summary>The product whose profile is being reviewed.</summary>
    public Guid ProductId { get; set; }

    /// <summary>The verdict — <c>approved</c> or <c>rejected</c>.</summary>
    public string Verdict { get; set; } = "approved";

    /// <summary>
    /// How long the review took, in milliseconds, as the browser measured it.
    /// </summary>
    /// <remarks>
    /// Required on an individual review, and required in <em>this</em> request rather than
    /// accumulated in the screen. The previous review capability recorded sixty-four judgements
    /// and six durations because its stopwatch lived in component state and died with the tab,
    /// and the average its delivery required does not exist for that session.
    /// </remarks>
    public int? ReviewDurationMs { get; set; }

    /// <summary>Kind of piece after the review, or null if the reviewer cleared it.</summary>
    public string? PieceType { get; set; }

    /// <summary>Materials after the review. Empty when the piece has none.</summary>
    public List<string> Materials { get; set; } = [];

    /// <summary>Stone after the review, or null if the reviewer cleared it.</summary>
    public string? StoneType { get; set; }

    /// <summary>Size label after the review, or null if the reviewer cleared it.</summary>
    public string? SizeLabel { get; set; }

    /// <summary>Colour tags after the review.</summary>
    public List<string> ColorTags { get; set; } = [];

    /// <summary>Style tags after the review.</summary>
    public List<string> StyleTags { get; set; } = [];

    /// <summary>Occasion tags after the review.</summary>
    public List<string> OccasionTags { get; set; } = [];
}

/// <summary>
/// One field's classification, as recorded for a single review.
/// </summary>
/// <param name="Field">The field.</param>
/// <param name="Direction">Confirmation, addition, removal or substitution.</param>
public record ProfileFieldDirectionDto(string Field, string Direction);

/// <summary>
/// What a recorded review produced.
/// </summary>
public class RecordProfileReviewResponse
{
    /// <summary>The product reviewed.</summary>
    public Guid ProductId { get; set; }

    /// <summary>Status the reviewer left it in.</summary>
    public string ReviewStatus { get; set; } = string.Empty;

    /// <summary>The stratum it was reviewed in.</summary>
    public string Stratum { get; set; } = string.Empty;

    /// <summary>One classification per reviewed field.</summary>
    public List<ProfileFieldDirectionDto> Directions { get; set; } = [];

    /// <summary>How many fields the reviewer actually moved.</summary>
    public int CorrectedFields { get; set; }

    /// <summary>The duration persisted with the judgement.</summary>
    public int? ReviewDurationMs { get; set; }
}

/// <summary>
/// Approving one field across many profiles at once.
/// </summary>
/// <remarks>
/// <para>
/// <see cref="Fields"/> is a list so that naming more than one is <em>expressible</em> and can
/// therefore be refused. A single-valued property would make the rule unbreakable by
/// construction and untestable by the same token, and the rule is the thing that keeps the batch
/// from being emptied of evidence.
/// </para>
/// <para>
/// The stratum is declared by the caller and verified against every selected profile, rather
/// than inferred from the selection. Inferring it would accept any selection whatsoever and
/// report afterwards which stratum it happened to be.
/// </para>
/// </remarks>
public class BulkApproveProfilesRequest
{
    /// <summary>The field being approved. Exactly one.</summary>
    public List<string> Fields { get; set; } = [];

    /// <summary>The stratum every selected profile must belong to.</summary>
    public string? Stratum { get; set; }

    /// <summary>The profiles whose field is being approved.</summary>
    public List<Guid> ProductIds { get; set; } = [];
}

/// <summary>
/// What a bulk approval produced.
/// </summary>
public class BulkApproveProfilesResponse
{
    /// <summary>The field approved.</summary>
    public string Field { get; set; } = string.Empty;

    /// <summary>The stratum it was approved within.</summary>
    public string Stratum { get; set; } = string.Empty;

    /// <summary>How many profiles were marked.</summary>
    public int Approved { get; set; }
}

/// <summary>
/// Returning a rejected profile to approved.
/// </summary>
public class RestoreRejectedProfileRequest
{
    /// <summary>The product whose profile was wrongly rejected.</summary>
    public Guid ProductId { get; set; }

    /// <summary>How long the judgement took, when it was timed.</summary>
    public int? ReviewDurationMs { get; set; }
}

/// <summary>
/// The rejected profiles, offered with the question inverted.
/// </summary>
/// <remarks>
/// A different question with a different base rate. Most of these are correctly rejected
/// non-jewellery — candles, postcards, keyrings — and they cluster in the stratum of absence;
/// letting them consume its quota would spend the scarcest attention in the batch confirming
/// that a candle is not a piece of jewellery.
/// </remarks>
public class RejectedProfilesDto
{
    /// <summary>The rejected profiles.</summary>
    public List<ProfileReviewItemDto> Items { get; set; } = [];

    /// <summary>How many there are in total.</summary>
    public int TotalCount { get; set; }

    /// <summary>Page returned, one-based.</summary>
    public int Page { get; set; }

    /// <summary>Items per page.</summary>
    public int PageSize { get; set; }

    /// <summary>The question this list asks.</summary>
    public string Question { get; set; } = string.Empty;
}

/// <summary>
/// One field's correction rate inside one stratum, broken down by direction.
/// </summary>
public class ProfileFieldStratumCorrectionDto
{
    /// <summary>Stratum code.</summary>
    public string Stratum { get; set; } = string.Empty;

    /// <summary>Reviewed profiles of this stratum that carry this field's judgement.</summary>
    public int Reviewed { get; set; }

    /// <summary>Of those, how many the reviewer moved.</summary>
    public int Corrected { get; set; }

    /// <summary>Share moved, as a percentage. Null when nothing was reviewed.</summary>
    public double? CorrectionRate { get; set; }

    /// <summary>Left as proposed.</summary>
    public int Confirmations { get; set; }

    /// <summary>An omission the reviewer supplied.</summary>
    public int Additions { get; set; }

    /// <summary>An unsupported value the reviewer took away.</summary>
    public int Removals { get; set; }

    /// <summary>A value the reviewer replaced.</summary>
    public int Substitutions { get; set; }

    /// <summary>How many profiles this stratum holds in the corpus, for the weighting.</summary>
    public int CorpusSize { get; set; }
}

/// <summary>
/// One field's correction rate, per stratum and weighted across them.
/// </summary>
public class ProfileFieldCorrectionDto
{
    /// <summary>The field.</summary>
    public string Field { get; set; } = string.Empty;

    /// <summary>Reviewed profiles carrying this field's judgement.</summary>
    public int Reviewed { get; set; }

    /// <summary>Of those, how many the reviewer moved.</summary>
    public int Corrected { get; set; }

    /// <summary>Share moved over the sample, as a percentage.</summary>
    public double? SampleCorrectionRate { get; set; }

    /// <summary>
    /// Share moved, weighted by the real size of each stratum in the corpus.
    /// </summary>
    /// <remarks>
    /// The figure that describes the catalog. Its unweighted twin above describes the sample,
    /// and the two differ on purpose: the strata are sampled at deliberately different rates, so
    /// an unweighted total over this batch would report a catalog that does not exist.
    /// </remarks>
    public double? WeightedCorrectionRate { get; set; }

    /// <summary>The breakdown the weighting is computed from.</summary>
    public List<ProfileFieldStratumCorrectionDto> ByStratum { get; set; } = [];
}

/// <summary>
/// One stratum's overall figures, across every reviewed field.
/// </summary>
public class ProfileStratumCorrectionDto
{
    /// <summary>Stratum code.</summary>
    public string Stratum { get; set; } = string.Empty;

    /// <summary>What the stratum means.</summary>
    public string Label { get; set; } = string.Empty;

    /// <summary>How many profiles it holds in the corpus.</summary>
    public int CorpusSize { get; set; }

    /// <summary>How many of its profiles a person reviewed.</summary>
    public int ProfilesReviewed { get; set; }

    /// <summary>Of those, how many carry at least one corrected field.</summary>
    public int ProfilesWithAnyCorrection { get; set; }

    /// <summary>Field judgements recorded in this stratum.</summary>
    public int FieldsReviewed { get; set; }

    /// <summary>Of those, how many were moved.</summary>
    public int FieldsCorrected { get; set; }

    /// <summary>Share of field judgements moved, as a percentage.</summary>
    public double? CorrectionRate { get; set; }

    /// <summary>Omissions supplied.</summary>
    public int Additions { get; set; }

    /// <summary>Unsupported values taken away.</summary>
    public int Removals { get; set; }

    /// <summary>Values replaced.</summary>
    public int Substitutions { get; set; }
}

/// <summary>
/// What the human review of the AI profiles produced, as figures the delivery can cite.
/// </summary>
/// <remarks>
/// <para>
/// Computed from the two stored columns rather than tallied in a screen: the correction rate is
/// the difference between the raw proposal and the values in force, and a figure that lives in
/// component state is gone when the tab closes.
/// </para>
/// <para>
/// The timed and the bulk populations are reported apart, and the average is <c>null</c> and
/// never <c>0</c> when nothing was timed. A zero asserts an instantaneous review, which is a
/// claim; an absence reports that nothing was measured, which is the truth. This is the rule the
/// family review metrics already follow, copied rather than redesigned.
/// </para>
/// </remarks>
public class ProfileReviewMetricsDto
{
    /// <summary>Profiles in the corpus.</summary>
    public int ProfilesTotal { get; set; }

    /// <summary>Profiles a person reviewed.</summary>
    public int ProfilesReviewedByHuman { get; set; }

    /// <summary>Profiles nobody looked at.</summary>
    public int ProfilesAutoBulk { get; set; }

    /// <summary>Share of the corpus a person reviewed, as a percentage.</summary>
    public double? ReviewedShare { get; set; }

    /// <summary>Reviews carrying a measured duration.</summary>
    public int TimedReviews { get; set; }

    /// <summary>Reviews approved in bulk, which carry none by design.</summary>
    public int BulkApprovedReviews { get; set; }

    /// <summary>
    /// Average seconds per review, over the timed population only.
    /// </summary>
    /// <remarks>Null when nothing was timed, never zero.</remarks>
    public double? AverageReviewSeconds { get; set; }

    /// <summary>Shortest timed review, in seconds.</summary>
    public double? MinReviewSeconds { get; set; }

    /// <summary>Longest timed review, in seconds.</summary>
    public double? MaxReviewSeconds { get; set; }

    /// <summary>Field judgements recorded across every reviewed profile.</summary>
    public int FieldsReviewed { get; set; }

    /// <summary>Of those, how many were moved.</summary>
    public int FieldsCorrected { get; set; }

    /// <summary>Share of field judgements moved over the sample, as a percentage.</summary>
    public double? SampleCorrectionRate { get; set; }

    /// <summary>
    /// Share of field judgements moved, weighted by the size of each stratum in the corpus.
    /// </summary>
    /// <remarks>The headline figure, and the one the delivery cites.</remarks>
    public double? WeightedCorrectionRate { get; set; }

    /// <summary>The rate per field, each split by stratum and direction.</summary>
    public List<ProfileFieldCorrectionDto> Fields { get; set; } = [];

    /// <summary>The rate per stratum, across every field.</summary>
    public List<ProfileStratumCorrectionDto> Strata { get; set; } = [];

    /// <summary>Profiles per prompt version, so two versions are never silently merged.</summary>
    public Dictionary<string, int> ProfilesByPromptVersion { get; set; } = [];

    /// <summary>The seed the batch is drawn with, so a figure names its own sample.</summary>
    public string Seed { get; set; } = string.Empty;
}
