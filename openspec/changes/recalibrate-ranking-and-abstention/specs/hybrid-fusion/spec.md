## MODIFIED Requirements

### Requirement: Weights and smoothing are configuration, and the weakest branch weighs less

The per-**branch** weights and the smoothing constant MUST be read from settings and MUST NOT be written into the code. Their effective values MUST also travel as parameters of the retrieval orchestration call, so that several configurations can be evaluated in one process without restarting it and without adding a field to the retrieval request schema.

**The fusion is composed in two stages.** The lists belonging to the lexical branch MUST first be fused with each other into one ranked lexical list, and that list MUST then be fused with the vector list under the per-branch weights. The consequence is normative: **a branch's total vote MUST be exactly its declared weight, whatever number of lists it is composed of and however many of them returned candidates.** A single flat fusion over every list is forbidden as the live path, because it makes the effective weight of a branch depend on how many of its own lists happened to match — a property of the query that no configuration declares.

The weights internal to the lexical branch MUST be equal and MUST NOT be swept, because the measured evidence establishes that both of its lists are necessary and not that either is worth more.

Only the **ratio** of the branch weights may change the order, so a calibration sweep over them MUST be one-dimensional and MUST be expressed as that ratio. The default ratio MUST be declared with a rationale that can be stated in one sentence.

The previous requirement that the vector weight be lower than either lexical weight is **withdrawn**: it was fixed under a rubric that its own report declared to be the lexical branch's objective function, and under the graded golden set it makes the vector branch unable to place a candidate that the lexical branch did not also produce.

#### Scenario: Weights are not hardcoded

- **WHEN** the fused retrieval runs
- **THEN** the branch weights and the smoothing constant come from settings or from the call parameters
- **AND** no weight value is written into the fusion module

#### Scenario: Two configurations run in one process

- **GIVEN** the settings supply a default set of weights
- **WHEN** the orchestration call is made once with those weights and once with different ones
- **THEN** both calls succeed without restarting the process
- **AND** neither call mutates the settings object

#### Scenario: A branch's vote does not depend on how many of its lists matched

- **GIVEN** a query for which both lexical lists return the same document
- **AND** a query for which only one lexical list returns anything
- **WHEN** each is fused
- **THEN** the lexical branch holds its declared weight in both cases
- **AND** the position at which the vector branch's best candidate can enter the result is the same for both

#### Scenario: The vector branch can place a candidate without lexical consensus

- **GIVEN** a query whose best-matching document the lexical branch ranks nowhere near the top
- **AND** which the vector branch ranks first
- **WHEN** the fusion runs under the default branch weights
- **THEN** that document appears among the first few fused candidates
- **AND** it is not placed behind every candidate the lexical branch produced

#### Scenario: Documents both branches agree on come first

- **GIVEN** a candidate produced by both branches and candidates produced by only one
- **WHEN** the fusion runs under equal branch weights
- **THEN** the candidate both branches produced precedes the others

#### Scenario: The internal lexical weights are equal and not swept

- **WHEN** the calibration report is inspected
- **THEN** the weights internal to the lexical branch appear as equal declared values
- **AND** they are not listed among the weights the sweep explored

#### Scenario: The branch-weight sweep is one-dimensional

- **WHEN** the branch weights are calibrated
- **THEN** the grid is expressed as the ratio between them
- **AND** two weight pairs with the same ratio produce the same order

### Requirement: All fused lists are truncated at the same depth, coupled to the smoothing constant

Every list entering a fusion stage MUST be truncated at the same depth, and that depth MUST be configurable. The depth MUST be of the same order as the smoothing constant, because a list far longer than the smoothing constant hands positive votes to candidates the other lists do not score at all, and that tail displaces the candidates two lists rank well without ranking first.

**The depth MUST be honoured per branch and not per list.** A branch composed of several lists MUST NOT be able to contribute more distinct candidates to the inter-branch fusion than a branch composed of one, because that is a second, independent way of over-weighting it: the ranked list a branch presents to the inter-branch stage MUST itself be truncated at the configured depth.

The branch depth MUST be a separate parameter from the size of the over-retrieval window the endpoint returns, which depends on the page size the caller requested, even when their default values coincide.

#### Scenario: The lists of one stage are cut at the same point

- **GIVEN** the lexical branch matched several hundred documents and the vector branch returned a full list
- **WHEN** a fusion stage runs
- **THEN** every list entering it is truncated at the configured depth before fusing
- **AND** no list enters the stage longer than another

#### Scenario: A multi-list branch contributes no more candidates than a single-list one

- **GIVEN** the lexical branch's two lists return disjoint sets of candidates
- **WHEN** the inter-branch fusion runs
- **THEN** the lexical branch contributes at most the configured depth of distinct candidates
- **AND** that is the same number the vector branch can contribute

#### Scenario: Branch depth and the returned window are distinct

- **GIVEN** a request whose page size makes the over-retrieval window smaller than the branch depth
- **WHEN** the retrieval runs
- **THEN** the branch depth used to fuse is unchanged by the requested page size
- **AND** the number of candidates returned still follows the over-retrieval rule

### Requirement: Structural filters extracted from the query text demote and never exclude

Filters inferred by rule from the operator's text — a price ceiling, a size, materials named in the query — MUST be applied as an ordering and MUST NOT remove any candidate. Candidates breaking such a constraint MUST be moved behind those satisfying it, and MUST remain inside the over-retrieval window that is returned, so that the caller that owns the authoritative price and stock still sees them.

Within each such block the fused order MUST be preserved, **except** where a ranking signal that this capability does not own reorders it. Such a signal MUST rank below every block produced by a typed constraint, so that what the operator expressed always outranks a signal they did not ask about; and it MUST reorder only, never remove.

Filters supplied explicitly in the request body MUST keep excluding, because a person selected them. The retriever MUST NOT require a candidate to carry every material named in the query, and MUST NOT invent a filter the query did not express. The piece type MUST NOT be applied as a filter at all, because a lexical match on the canonical term is already equivalent to filtering by it and a filter would constrain only the branch that rescues paraphrase.

#### Scenario: A price ceiling reorders without removing

- **GIVEN** the query expresses a price ceiling
- **WHEN** the retrieval runs
- **THEN** candidates within the ceiling are ordered ahead of those above it
- **AND** candidates above the ceiling are still present in the returned candidates

#### Scenario: A ranking signal reorders inside a block but never across blocks

- **GIVEN** the query expresses a price ceiling
- **AND** a ranking signal applies to the candidates
- **WHEN** the candidates are ordered
- **THEN** every candidate within the ceiling still precedes every candidate above it
- **AND** the signal decides the order only among candidates the ceiling ranks equally

#### Scenario: A body filter still excludes

- **GIVEN** the request body carries a material filter
- **WHEN** the retrieval runs
- **THEN** every returned candidate satisfies it

#### Scenario: Multiple materials in the text do not require all of them

- **GIVEN** the query names more than one material
- **WHEN** the retrieval runs
- **THEN** a candidate carrying only one of them is still returned
- **AND** it is not required to carry every named material

#### Scenario: No filter is invented

- **GIVEN** a query expressing no price, size or material constraint
- **WHEN** the retrieval runs
- **THEN** no such constraint is applied to the ordering
- **AND** the extracted filters reported for the request are empty

#### Scenario: A document with no extracted materials is not deleted

- **GIVEN** the query names a material
- **AND** some documents carry no extracted materials at all
- **WHEN** the retrieval runs
- **THEN** those documents may still appear among the candidates

## ADDED Requirements

### Requirement: The lexical branch weighs less when its best candidate matched less of the query

The weight of the lexical branch MUST be scaled by how much of the query its best candidate actually matched, measured as the coordination tally the lexical branch already computes. The scaling MUST be continuous and MUST introduce no configured parameter of its own: a branch whose best candidate matched everything the query can express keeps its full declared weight, and one whose best candidate matched a fraction of it keeps that fraction.

**The denominator MUST count only the counting groups whose text-search query is non-empty.** A group whose terms reduce to nothing under the language configuration — a stop word the operator typed — can never match any document, so counting it in the denominator would lower the weight of a query that is in fact fully anchored, and would do so on exactly the queries where the lexical branch is strongest. The denominator MUST be computed in the same statement that computes the coordination tally, so that no additional round trip is spent on it.

The scaling MUST NOT be derived from whether the branch's typed list is empty, because a list built from the operator's literal text can be empty on a query the equivalence groups answer perfectly.

#### Scenario: Full coverage leaves the lexical weight untouched

- **GIVEN** a query whose best lexical candidate matches every counting group with a non-empty text-search query
- **WHEN** the fusion runs
- **THEN** the lexical branch keeps its full declared weight
- **AND** the fused order is the one the unscaled weights produce

#### Scenario: A stop-word group does not lower coverage

- **GIVEN** a query containing a stop word that becomes a counting group with an empty text-search query
- **AND** whose best lexical candidate matches every other counting group
- **WHEN** coverage is computed
- **THEN** the empty group is excluded from the denominator
- **AND** the coverage is full

#### Scenario: Partial coverage lowers the lexical weight

- **GIVEN** a query whose best lexical candidate matches only part of the counting groups that can match
- **WHEN** the fusion runs
- **THEN** the lexical branch's effective weight is scaled down in that proportion
- **AND** the vector branch's candidates rise accordingly

#### Scenario: Coverage introduces no configured parameter

- **WHEN** the settings are inspected
- **THEN** no parameter governs the strength of the coverage scaling
- **AND** the scaling is the proportion itself
- **AND** switching the rule off is available as a control and a rollback, which is not a strength

#### Scenario: The scaling is measured against the rule switched off

- **WHEN** the adaptive scaling is adopted
- **THEN** the report compares it against the same fusion with the rule off
- **AND** states the per-category effect of the difference
- **AND** a comparison between two forms of the scaling is not accepted in place of that control

#### Scenario: An empty typed list does not by itself lower the weight

- **GIVEN** a query whose literal phrasing matches no document but whose equivalence groups match well
- **WHEN** coverage is computed
- **THEN** it is computed from the coordination tally of the group-based list
- **AND** the emptiness of the typed list does not lower it

### Requirement: The flat fusion remains selectable so the published baseline stays reproducible

The single-stage fusion over every list MUST remain selectable by configuration, with the weights that were in force before this change. It MUST NOT be the default. Its purpose is normative rather than operational: the evaluation's published baseline row was measured under it, and a configuration that can no longer be reproduced cannot serve as the row every other row is read against.

The fusion mode in force MUST be recorded in the fusion stage log and in the provenance of any evaluation run.

#### Scenario: The flat mode reproduces the published baseline

- **GIVEN** the flat fusion mode and the weights in force before this change
- **WHEN** the baseline configuration is evaluated against the same golden set version
- **THEN** its metrics match the published baseline

#### Scenario: The flat mode is not the default

- **WHEN** the default configuration is loaded
- **THEN** the two-stage fusion is in force

#### Scenario: The mode in force is recorded

- **WHEN** the fusion stage logs
- **THEN** it names the fusion mode in force
- **AND** an evaluation run records that mode in its provenance
