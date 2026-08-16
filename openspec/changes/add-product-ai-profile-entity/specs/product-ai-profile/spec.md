## ADDED Requirements

### Requirement: Each product has at most one AI profile

The system SHALL persist AI-proposed catalog attributes as a profile bound to exactly one product. Uniqueness MUST be enforced by a database constraint rather than by an application check, because a duplicate profile produces no error and would surface later as duplicated documents in the vector index. Deleting a product MUST be restricted rather than cascading into the profile, so that removing a catalog row cannot silently destroy review work.

#### Scenario: A second profile for the same product is rejected

- **WHEN** a second profile is persisted for a product that already has one
- **THEN** the write fails on the database's uniqueness constraint
- **AND** the existing profile is left unchanged

#### Scenario: Uniqueness is enforced by the database, not by an application check

- **WHEN** the index over the product identifier is read from the database catalog
- **THEN** it is reported as unique
- **AND** the guarantee therefore holds for any writer, including one that forgets to check first

#### Scenario: The foreign key to the product does not cascade

- **WHEN** the delete rule of the profile's product foreign key is read from the database catalog
- **THEN** it is `RESTRICT` rather than the framework's default of `CASCADE`
- **AND** removing a product therefore cannot silently take the review work with it

### Requirement: A profile records the provenance and confidence of every field

The profile SHALL store, for each proposed field, the confidence with which it was proposed and whether its value is `rule` or `inferred`. It SHALL also retain the original AI proposal unmodified, separate from the values in force, so that a later correction can be compared against what was originally proposed. Material, colour, style and occasion values MUST be stored as lists and MUST never be null: an absence of evidence is an empty list, never a default value.

#### Scenario: Provenance travels with every field

- **WHEN** a profile is persisted from a proposal
- **THEN** the stored profile exposes a confidence value for each proposed field
- **AND** it exposes, for each proposed field, whether the value came from a rule or was inferred

#### Scenario: The raw proposal is stored apart from the values in force

- **WHEN** a profile is persisted from a proposal
- **THEN** the raw proposal is retrievable exactly as the AI service returned it
- **AND** it is held separately from the values in force, so that the two can be compared field by field

#### Scenario: A product can hold several materials at once

- **WHEN** a profile is persisted for a piece proposed as silver with gold plating
- **AND** the profile is read back
- **THEN** both materials are present as separate list entries

#### Scenario: No evidence of material yields an empty list

- **WHEN** a proposal carries no material
- **THEN** the stored profile holds an empty list
- **AND** it holds neither a null nor a default material

### Requirement: Sensitive inferred fields require human review

The system SHALL apply a per-field review policy. The sensitive fields are piece type, materials, stone type and size label. A sensitive field MUST require human review when its value is inferred. A sensitive field MUST NOT require human review when its value comes from a deterministic rule. Commercial tag fields — colour, style and occasion — MUST be auto-approved when their confidence reaches the configured threshold, and MUST require review below it. Any field below the threshold MUST require review regardless of its kind. A profile SHALL be pending when at least one of its fields requires review, and approved when none does.

Family membership is explicitly outside this policy: the product family is a business entity owned by another capability, and the family and variant values a proposal carries MUST be ignored.

#### Scenario: An inferred sensitive field leaves the profile pending

- **WHEN** a proposal carries an inferred value for piece type, materials, stone type or size label
- **AND** the routed review mode is applied
- **THEN** the profile is left pending review
- **AND** the per-field detail identifies which field caused it

#### Scenario: A rule-sourced sensitive field does not require review

- **WHEN** a proposal carries a sensitive field whose value comes from a deterministic rule
- **AND** no other field requires review
- **THEN** the profile is left approved
- **AND** the rule provenance of that field remains recorded

#### Scenario: High-confidence tags are auto-approved

- **WHEN** colour, style or occasion tags are proposed with a confidence at or above the configured threshold
- **AND** no sensitive field requires review
- **THEN** the profile is left approved without human intervention

#### Scenario: Low-confidence tags send the profile to review

- **WHEN** the same tags are proposed with a confidence below the configured threshold
- **THEN** the profile is left pending review

#### Scenario: Family and variant proposals are ignored

- **WHEN** a proposal carries a family or a variant value
- **THEN** no product family relationship is created or modified
- **AND** the routing outcome is unaffected by those values

### Requirement: Review thresholds come from configuration

The confidence thresholds governing the review policy SHALL be bound from application configuration and validated at application start, not compiled as constants. A failure MUST prevent the application from starting and MUST name the offending configuration key. These thresholds are recalibrated against the evaluation golden set in a later change, which a compiled value would make impossible without a code change.

#### Scenario: Thresholds are read from configuration

- **WHEN** the review policy is evaluated
- **THEN** the threshold applied is the configured value rather than a hard-coded one

#### Scenario: An invalid threshold prevents startup

- **WHEN** the application starts with a threshold outside the range zero to one
- **THEN** startup fails
- **AND** the error names the offending configuration key

### Requirement: Review status and review origin are independent

The profile SHALL record its review status — pending, approved or rejected — separately from its review origin, which states whether the current status was produced by bulk auto-approval or by a person. The indexing feed selects by status alone, and human-review metrics select by origin alone; a single combined value would make one of those two selections silently wrong.

#### Scenario: Bulk auto-approval is approved and distinguishable

- **WHEN** a batch is enriched in bulk mode
- **THEN** the resulting profiles are approved
- **AND** their review origin identifies them as bulk auto-approved rather than human-reviewed

#### Scenario: Routing outcome survives bulk approval

- **WHEN** a batch is enriched in bulk mode and a sensitive field is inferred
- **THEN** the profile is still approved
- **AND** the per-field confidence and provenance still record that the field would have required review

### Requirement: The profile carries the storage that human-review metrics will need

The profile SHALL provide the fields from which the correction rate per field and the average review time can later be computed **without a further migration**: the raw AI proposal held apart from the values in force, the reviewing user, the instant of the review, and its duration. The duration MUST be optional, because it is measured by the client rather than observable by the server, and is meaningless for bulk approval, where it MUST be left absent rather than fabricated.

Populating these fields when a person reviews a profile is **outside this capability**. What is required here is that they exist, that they accept absence, and that batch enrichment never leaves a profile claiming a human reviewed it.

#### Scenario: Batch enrichment never claims a human review

- **WHEN** a batch produces or replaces a profile
- **THEN** its review origin is bulk
- **AND** no reviewing user, review instant or review duration is recorded on it

#### Scenario: The review fields accept absence

- **WHEN** the schema of the profile is inspected
- **THEN** the reviewing user, the review instant and the review duration all accept null

### Requirement: Batch enrichment is restricted to administrators

The system SHALL expose exactly one operation for this capability: enriching a batch of products. It MUST be available only to administrators. An operator MUST receive HTTP 403 and an unauthenticated caller HTTP 401, and in neither case may a profile be created or modified. The request MUST be validated explicitly before any work is done, and a batch larger than the size the AI contract accepts MUST be rejected with HTTP 400.

This capability MUST expose no read route: no profile retrieval, no review queue, no metrics and no aggregation. Approving or rejecting a profile is likewise outside this capability.

#### Scenario: An operator cannot enrich the catalog

- **WHEN** a user with the operator role requests batch enrichment
- **THEN** the response status is 403
- **AND** no profile is created or modified

#### Scenario: An unauthenticated caller is rejected

- **WHEN** batch enrichment is requested without authentication
- **THEN** the response status is 401

#### Scenario: An oversized batch is rejected

- **WHEN** batch enrichment is requested with more products than the AI contract accepts in one call
- **THEN** the response status is 400
- **AND** no call is made to the AI service

#### Scenario: The capability exposes no read surface

- **WHEN** the routes of this capability are enumerated
- **THEN** the only route is the batch enrichment operation

### Requirement: Enrichment is idempotent on the inputs it was derived from

The profile SHALL store a hash of the product inputs the enrichment was derived from — identifier, name, description and collection, in a fixed order. A product whose hash is unchanged MUST be skipped and reported as unchanged, and **no call MUST be made to the AI service** on its behalf, so that repeating a batch neither costs a model call nor overwrites work a person has already reviewed. An explicit option MUST exist to force re-enrichment regardless of the hash.

When the hash does change, the proposal is new: the profile returns to the routing outcome, its origin returns to bulk, and the previous review data is cleared and the fact recorded in the log.

#### Scenario: An unchanged product is skipped without calling the AI service

- **WHEN** a batch is requested for a product whose stored hash matches its current inputs
- **THEN** the product is reported as skipped unchanged
- **AND** no request is issued to the AI service for it
- **AND** any existing human review of that profile is left intact

#### Scenario: Forcing re-enrichment overrides the hash

- **WHEN** a batch is requested with the force option for a product whose hash is unchanged
- **THEN** the product is enriched again

#### Scenario: Changed inputs reset the review state

- **WHEN** a product whose name or description has changed is enriched again
- **THEN** the profile takes the review status the routing policy produces
- **AND** its review origin returns to bulk
- **AND** the previous reviewer and review instant are cleared

#### Scenario: A batch that loses a race reports it apart from a failure

- **WHEN** another batch persists a profile for one of these products while this batch is waiting on the AI service
- **THEN** the batch still succeeds and persists the rest of its profiles
- **AND** that product is reported as skipped for concurrency, counted separately from failures
- **AND** the profile the other batch wrote is left intact

> The window here is the call to the extraction model, which takes seconds, so this is an
> ordinary outcome rather than a pathological interleaving. It is not a failure — the product
> ended up enriched, just by somebody else — and reporting it as one would send an
> administrator to re-run a batch chasing a problem that does not exist.

### Requirement: An unavailable enrichment implementation is reported, never simulated

When the AI service reports that the enrichment route has no implementation yet, the system MUST answer with HTTP 503 and a message naming the change that will deliver it. It MUST NOT fall back to any other source and MUST NOT persist a profile, because there is no degraded path for enrichment: producing attributes without the extractor would be inventing catalog data.

#### Scenario: An unimplemented route surfaces as unavailable

- **WHEN** the AI service reports the enrichment route as not implemented
- **THEN** the response status is 503
- **AND** the message names the change that delivers the implementation
- **AND** no profile is created or modified

### Requirement: Schema properties that fail silently are asserted against the database

The migration SHALL be covered by assertions read from the PostgreSQL catalog for the properties whose incorrect value raises no error: JSON document columns landing as text instead of `jsonb`, the uniqueness of the product index, and the delete rule of each foreign key. Closed vocabularies MUST be stored as text with validation rather than as database enumeration types, because an enumeration type survives its table being dropped and breaks the next migration weeks later. The model MUST have no pending differences against the migrations.

#### Scenario: JSON columns are jsonb, not text

- **WHEN** the column types of the profile table are read from the database catalog
- **THEN** every JSON document column reports type `jsonb`

#### Scenario: The product index is unique

- **WHEN** the index over the product identifier is read from the database catalog
- **THEN** it is reported as unique

#### Scenario: Foreign keys restrict instead of cascading

- **WHEN** the delete rules of the profile foreign keys are read from the database catalog
- **THEN** each of them is `RESTRICT`

#### Scenario: The model matches the migrations

- **WHEN** the model is compared against the migration snapshot
- **THEN** there are no pending differences
