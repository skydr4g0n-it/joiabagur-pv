# profile-review Specification

## Purpose
Human review of the AI product profiles, and the two figures it produces. The capability the
enrichment service delegated to by exposing a single write operation and declaring that reading,
approving and measuring belong elsewhere.

The queue is drawn by review **origin** over approved **status**, never by status. The indexing feed
selects approved profiles, so opening a batch into a pending status would withdraw those documents
from the vector index for the length of a session and force them to be re-embedded on re-approval,
degrading the corpus the system sells from in order to inspect it. Status governs what is indexed;
origin governs what these metrics count, and the two are independent by the enrichment spec's own
requirement. Nothing about the batch is persisted: it is drawn by ordering each evidence stratum by
a stable hash of the product identifier combined with a configured seed, so the sample behind a
published figure is reconstructable by anyone who was not there, without an entity and without the
migration an entity would cost.

The batch is **stratified by evidence rather than ordered by confidence**, and the stratum is
computed in one place shared by the queue and the metrics. Confidence here is not a probability: the
extractor never copies the model's own score and emits a four-value staircase describing what kind of
evidence stands behind a value — a deterministic rule produced it, its vocabulary phrase is literally
in the source text, the model asserted it with no such phrase, or it is absent. Stratifying on that
staircase separates populations a confidence ordering merges, because the span check can only detect
a value asserted *without* evidence and is structurally blind to one the extractor failed to extract.
An absent stone type does not lower a stratum, since most jewellery carries no stone.

The criterion a reviewer applies is **fidelity to the source text**, never the truth of the physical
piece: the system holds no photographs and no visual embeddings, and the text of both the synthetic
and the real portions of the corpus was written by a language model, so the second question is not
executable while the first is exactly what the enrichment metrics claim to measure. That makes the
product's full name and description part of the requirement rather than context, and makes a missing
description something to state rather than render as a blank. Every field travels with its confidence
and its provenance, and the provenance distinguishes three cases rather than two — rule, inference,
and a field the extractor proposed nothing for — because defaulting an absence to inference accuses
the model of a guess it never made.

A correction is recorded **with its direction** — confirmation, addition, removal or substitution,
derived from the set difference for list-valued fields — because the direction is what separates an
omission from a hallucination, defects with different remedies. The raw proposal is **immutable**: the
correction rate is the difference between that record and the values in force, so rewriting it would
destroy the metric silently and with no way to recover it. Review time is accepted in the same request
that records the judgement and an individual review must carry one, because a stopwatch accumulated in
a screen dies with the tab — the previous review capability recorded sixty-four judgements and six
durations for precisely that reason. Bulk approval is bounded to one field within one stratum and
fabricates no time: unbounded, it is how a batch stops containing any evidence.

The figures are reported per field, per stratum and per direction, with a total weighted by the real
size of each stratum in the corpus rather than in the sample, since the strata are sampled at
deliberately different rates. Profiles nobody reviewed leave both the numerator and the denominator,
and the count per origin is reported so the reviewed share of the corpus is readable. An absence of
measured time is reported as an absence and never as a zero, with the timed and the bulk populations
counted apart. Rejected profiles are offered as their own list with the question inverted — is any
rejection wrong? — and consume no stratum's quota, because they are a different question with a
different base rate and cluster in the scarcest stratum. Every operation is administrator-only: a
review rewrites what the catalogue asserts about a piece, and those assertions reach a customer
through an operator. A list that could not be computed is never presented as one that came back
empty, and the queue can be worked without a pointing device, with the shortcuts inert while focus
sits inside a text-editing field.

## Requirements

### Requirement: The review queue is drawn by review origin, never by review status

The system SHALL compose the review queue from profiles whose review origin is bulk and whose review
status is approved. Reviewing a profile MUST change its origin to human; it MUST NOT change its
status merely by entering or leaving the queue.

Drawing the queue by status is not an equivalent alternative. The indexing feed selects approved
profiles, so moving a batch to a pending status would withdraw those documents from the vector index
for the duration of the session and force them to be re-embedded on re-approval. Status governs what
is indexed; origin governs what the human-review metrics count. The two are already required to be
independent, and this capability spends that independence rather than adding a state.

#### Scenario: Entering the queue changes no status

- **WHEN** the review queue is requested
- **THEN** every profile it returns has bulk origin and approved status
- **AND** no profile's review status is modified by the request

#### Scenario: The indexed corpus is unchanged while a session is open

- **WHEN** the queue has been requested and no review has yet been recorded
- **THEN** the number of documents the indexing feed considers indexable is the same as before the request

#### Scenario: Recording a review moves the origin

- **WHEN** a reviewer records a judgement on a profile
- **THEN** that profile's review origin becomes human
- **AND** its reviewing user and review instant are stamped by the server, never taken from the request body

### Requirement: The batch is stratified by evidence, and the stratum is computed in one place

The system SHALL assign every queued profile to exactly one evidence stratum, derived from the
**lowest** per-field confidence among the sensitive inferred fields, treating an absent stone type as
unremarkable rather than as missing evidence. The strata MUST be: absence, asserted without a textual
span, and asserted with one.

The function that assigns the stratum MUST be shared by the queue and by the metrics. Computing it
twice is how a queue and a report begin to disagree about the same profile without either being
obviously wrong.

Ordering the queue by confidence instead of stratifying it is not equivalent, and the difference is
measurable: the confidence signal is derived from whether a vocabulary phrase appears in the source
text, so it can only detect a value asserted **without** evidence and is structurally blind to a
value the extractor **failed to extract**. A confidence-ordered queue concentrates on one error class
and never reaches the other.

#### Scenario: Every queued item declares its stratum

- **WHEN** the queue is requested
- **THEN** each item reports which stratum it belongs to
- **AND** reports which field placed it there

#### Scenario: An absent stone type does not lower the stratum

- **GIVEN** a profile whose piece type and materials were asserted with a textual span and which declares no stone type
- **WHEN** its stratum is computed
- **THEN** it is assigned to the stratum of values asserted with a span, not to the stratum of absence

#### Scenario: The queue and the metrics agree on the stratum

- **WHEN** the same profile appears in the queue and in the metrics report
- **THEN** both attribute it to the same stratum

### Requirement: The sample is deterministic and is not persisted

The system SHALL select the batch by ordering each stratum by a stable hash of the product identifier
combined with a configured seed, and MUST return the same products in the same order for the same
seed. The batch MUST NOT be persisted as an entity.

Reproducibility is what the batch needs; storage is not. Persisting it would require a further
migration for no gain, and a declared seed lets anyone reconstruct the batch that produced a published
figure.

#### Scenario: The same seed yields the same batch

- **WHEN** the queue is requested twice with the same seed
- **THEN** both responses contain the same products in the same order

#### Scenario: The quota of each stratum is honoured

- **WHEN** the queue is requested with a quota per stratum
- **THEN** each stratum contributes at most its quota
- **AND** a stratum holding fewer profiles than its quota contributes all of them and reports that it is exhausted

#### Scenario: No batch entity is created

- **WHEN** the queue is requested
- **THEN** no row is written to any table

### Requirement: The source text accompanies the proposal, because it is the criterion

The system SHALL present, for every queued profile, the product's full name and description alongside
the proposed values. When a product has no description, the absence MUST be stated rather than
rendered as an empty space.

The criterion a reviewer applies is whether the **source text supports the value**, never whether the
value is true of the physical piece. The second is not executable: the system holds no photographs and
no visual embeddings, and the text of both the synthetic and the real portions of the corpus was
written by a language model. The first is exactly what the enrichment metrics claim to measure — the
extractor, not the truth of the datum — so the criterion is part of the requirement rather than a
convention a reviewer is left to infer.

#### Scenario: The text is shown beside the values

- **WHEN** a profile is presented for review
- **THEN** the product's name and description are shown with it

#### Scenario: A missing description is stated

- **GIVEN** a product with no description
- **WHEN** its profile is presented for review
- **THEN** the absence of a description is stated explicitly

### Requirement: Every field carries its confidence and its provenance, and an absence is not an inference

The system SHALL present every field with its confidence and its provenance, and the provenance
MUST distinguish three cases: a deterministic rule produced the value, a model inferred it, or the
extractor proposed nothing for that field. A field the extractor never proposed MUST NOT be
reported as inferred.

A per-field *pending review* mark was specified here first and is deliberately not required, because
measuring it against the corpus showed it carries no information. Over the 1.114 profiles of the
queue the mark is **constant in six of the seven fields** — always on for piece type, materials and
stone type, always off for the three commercial tags — because the extractor marks those six the
same way in every single product. A signal that never varies is not a signal. What tells a reviewer
where the risk is, and does vary, is the pair the fields already carry: a value at `0,45` asserted
by a model is a different proposition from one at `1,00` produced by a rule.

The third provenance case is what that measurement uncovered. The seventh field, the size label, is
the only one whose mark varied — and it varied because an absent field was being defaulted to
inferred: **613 of those 1.114 profiles carry no size label at all**, and reporting them as inferred
at `0,20` reads as "the model asserted this with no evidence" about a field the model never spoke
to. That is an accusation against the extractor rather than a description of the data, and it would
inflate a reviewer's sense of how much of the catalogue was guessed.

#### Scenario: Provenance distinguishes a rule from an inference

- **GIVEN** a profile whose materials were inferred and whose size label came from a rule
- **WHEN** it is presented for review
- **THEN** the materials report that a model inferred them
- **AND** the size label reports that a rule produced it

#### Scenario: A field the extractor never proposed is reported as absent

- **GIVEN** a profile for which the extractor proposed no size label
- **WHEN** it is presented for review
- **THEN** that field's provenance reports an absence
- **AND** it is not reported as inferred

#### Scenario: Confidence travels with every field

- **WHEN** a profile is presented for review
- **THEN** each field reports its confidence

### Requirement: A correction is recorded with its direction, and the raw proposal is never rewritten

The system SHALL classify every reviewed field as a confirmation, an addition, a removal or a
substitution, by comparing the value in force against the raw proposal. For list-valued fields the
classification MUST be derived from the set difference, so that adding a material is an addition and
dropping one is a removal.

The raw proposal MUST NOT be modified by a review, ever. The correction rate is the difference between
that record and the values in force; rewriting it destroys the metric silently and without any way to
recover it.

Recording only whether a field changed is insufficient. The direction is what separates an omission —
the extractor missed something the text stated — from a hallucination — the extractor asserted
something the text does not support, and those are different defects with different remedies.

#### Scenario: Adding a material is recorded as an addition

- **GIVEN** a profile proposing a single material and a description naming a second one
- **WHEN** the reviewer adds the second material and saves
- **THEN** the correction is recorded with direction addition on the materials field
- **AND** the raw proposal is unchanged

#### Scenario: Clearing an unsupported value is recorded as a removal

- **GIVEN** a profile asserting a stone type that the source text does not name
- **WHEN** the reviewer clears the field and saves
- **THEN** the correction is recorded with direction removal on the stone type field

#### Scenario: An untouched field is recorded as a confirmation

- **WHEN** the reviewer saves a profile without changing a given field
- **THEN** that field is recorded as a confirmation rather than omitted from the record

### Requirement: Review time is persisted with the judgement, never held in a screen

The system SHALL accept the measured duration of a review in the same request that records the
judgement, and MUST persist it with that profile. An individual review MUST carry a duration.

The duration is measured by the client because the server cannot observe how long a person looked at a
row. Accumulating it in screen state loses it: the previous review capability recorded sixty-four
judgements and six durations for exactly that reason, and the average its delivery required did not
exist for that session.

#### Scenario: A duration is stored with the judgement

- **WHEN** an individual review is recorded with a measured duration
- **THEN** that duration is persisted on the profile in the same operation

#### Scenario: Losing the session does not lose recorded durations

- **GIVEN** a reviewer has recorded several individual reviews
- **WHEN** the session ends without warning
- **THEN** every duration already recorded remains persisted

#### Scenario: An individual review without a duration is rejected

- **WHEN** an individual review is recorded with no duration
- **THEN** the request is rejected

### Requirement: Bulk approval is bounded to one field within one stratum, and fabricates no time

The system SHALL allow approving one field across many profiles at once, and MUST reject a bulk
operation whose selection spans more than one field or more than one stratum. A bulk approval MUST
leave the review duration absent and MUST be marked as bulk.

Bulk approval is legitimate and cheap for commercial tags. Unbounded, it is how the batch stops
containing any evidence: a stratum approved wholesale yields a correction rate of zero that says
nothing about the extractor, and a shared timestamp across forty rows would produce an average that
flatters the process.

#### Scenario: Bulk approval across strata is rejected

- **WHEN** a bulk approval selects profiles belonging to more than one stratum
- **THEN** the request is rejected and no profile is modified

#### Scenario: Bulk approval across fields is rejected

- **WHEN** a bulk approval names more than one field
- **THEN** the request is rejected and no profile is modified

#### Scenario: Bulk approval records no duration

- **WHEN** a bulk approval succeeds over a set of profiles
- **THEN** each of those profiles has an absent review duration
- **AND** each is marked as approved in bulk

### Requirement: The correction rate is reported per field, per stratum and per direction

The system SHALL report the correction rate broken down by field, by evidence stratum and by
direction, together with a total weighted by the real size of each stratum in the corpus.

An unweighted total computed over a stratified sample describes the sample and not the catalog, and
the strata are deliberately sampled at very different rates.

#### Scenario: The rate is broken down by field

- **WHEN** the metrics are requested
- **THEN** a correction rate is reported for each reviewed field

#### Scenario: The rate is broken down by stratum and direction

- **WHEN** the metrics are requested
- **THEN** each field's rate is further split by evidence stratum and by correction direction

#### Scenario: The total is weighted by stratum size

- **WHEN** the metrics are requested
- **THEN** the overall correction rate is weighted by the size of each stratum in the corpus, not by its size in the sample

### Requirement: The metrics count human-reviewed profiles alone

The system SHALL exclude profiles whose review origin is bulk from both the numerator and the
denominator of the correction rate, and MUST report how many profiles carry each origin so that the
reviewed share of the corpus is readable.

#### Scenario: Bulk profiles do not enter the rate

- **GIVEN** most profiles still carry bulk origin and some carry human origin
- **WHEN** the metrics are requested
- **THEN** no bulk-origin profile contributes to the correction rate

#### Scenario: The reviewed share is reported

- **WHEN** the metrics are requested
- **THEN** the count of profiles with each review origin is reported

### Requirement: An absence of measured time is reported as an absence, never as a zero

The system SHALL report the average review time as absent when no review carries a measured duration,
and MUST report the timed and the bulk populations separately, each with its count.

A zero asserts an instantaneous review, which is a claim. An absence reports that nothing was
measured, which is the truth. Mixing a population that was timed with one that cannot be timed
produces an average that describes neither.

#### Scenario: No timings yields an absent average

- **GIVEN** no recorded review carries a duration
- **WHEN** the metrics are requested
- **THEN** the average review time is absent rather than zero

#### Scenario: The two populations are counted apart

- **WHEN** the metrics are requested
- **THEN** the number of reviews carrying a duration and the number approved in bulk are reported separately
- **AND** the average is computed over the timed population only

### Requirement: Rejected profiles are reviewed with the inverted question and consume no quota

The system SHALL offer the profiles whose review status is rejected as a separate list, asking whether
any rejection is **wrong**, and MUST allow returning such a profile to approved with its reviewer
recorded. These profiles MUST NOT consume the quota of any evidence stratum.

They are a different question with a different base rate. Most of them are correctly rejected
non-jewellery, and they cluster in the stratum of absence; letting them consume its quota would spend
the scarcest attention in the batch confirming that a candle is not a piece of jewellery.

#### Scenario: Rejected profiles are served apart

- **WHEN** the rejected profiles are requested
- **THEN** they are returned as their own list
- **AND** none of them appears in the stratified queue

#### Scenario: A wrong rejection can be undone

- **WHEN** a reviewer returns a rejected profile to approved
- **THEN** its status becomes approved, its origin becomes human, and its reviewer and instant are recorded

### Requirement: Profile review is restricted to administrators

The system SHALL restrict every operation of this capability — reading the queue, recording a review,
approving in bulk, reviewing rejected profiles and reading the metrics — to administrators. An
operator MUST receive HTTP 403 and an unauthenticated caller HTTP 401, and in neither case may any
profile be modified.

A review rewrites what the catalog asserts about a piece, and those assertions reach a customer
through an operator. It is not an operator's call.

#### Scenario: An operator is refused

- **WHEN** a user with the operator role calls any operation of this capability
- **THEN** the response is HTTP 403
- **AND** no profile is created or modified

#### Scenario: An unauthenticated caller is refused

- **WHEN** an unauthenticated caller invokes any operation of this capability
- **THEN** the response is HTTP 401

### Requirement: A list that could not be computed is never presented as an empty list

The system SHALL distinguish, in the review screen, a list that was computed and came back empty from
one that could not be computed, and MUST state the reason in the second case.

On a screen whose subject is catalogue quality, "nothing to review" reads as "nothing is wrong",
which is precisely the conclusion this capability exists to establish with evidence rather than to
imply by failure.

#### Scenario: A failed read is reported as a failure

- **WHEN** the queue cannot be computed
- **THEN** the screen reports that it could not be computed and why
- **AND** does not display an empty-queue state

### Requirement: A reviewer can work the queue without the mouse

The system SHALL provide keyboard operation for approving, rejecting and advancing through the
review queue, sufficient to traverse a queue end to end without pointing device. The shortcuts MUST
NOT fire while focus is inside a text-editing field.

#### Scenario: A queue is traversed by keyboard

- **WHEN** a reviewer uses the keyboard to approve, reject and advance
- **THEN** the queue can be traversed from first to last item without using the mouse

#### Scenario: Typing into a field does not trigger a shortcut

- **GIVEN** focus is inside a text-editing field
- **WHEN** the reviewer types a character bound to a shortcut
- **THEN** the character is entered into the field and no review action is triggered
