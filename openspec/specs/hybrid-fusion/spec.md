# hybrid-fusion Specification

## Purpose
Rank-based fusion of the retrieval branches behind `POST /v1/retrieval/products`: a pure function that combines several ranked lists of candidate identifiers into one order from a weight per list and a smoothing constant, summing weight over smoothing plus position and never reading the raw scores the branches produced, which live on incomparable scales whose distributions change per query. Weights, the smoothing constant and the single depth at which every list is truncated are configuration with measured defaults, and their effective values travel as parameters of the orchestration call rather than as fields of the frozen request schema. The fusion is composed in two stages — the lexical lists are fused with each other first, and the one lexical list that results is then fused with the vector list under per-branch weights — so a branch's total vote is exactly its declared weight however many of its own lists matched, and the depth is honoured per branch rather than per list. The lexical branch's weight is then scaled down, by no configured parameter of its own, in proportion to how much of the query its best candidate actually matched. The single flat fusion over every list stays selectable so the published evaluation baseline remains reproducible, but it is not the default.

The lexical branch composes its query disjunctively from the equivalence groups the expansion produced, always with bound parameters and without a positional adjacency constraint, and orders its candidates first by how many counting groups they match, where only fields whose absence is evidence — well-covered vocabulary fields and literal words the operator typed — may count. Structural filters extracted by rule from the query text demote and never exclude, so the caller that owns the authoritative price and stock still sees the candidates; filters a person selected in the request body keep excluding. A ranking signal this capability does not own may reorder candidates inside one of those blocks but never across them, so what the operator typed always outranks a signal they did not ask about.

Every candidate reports which branches produced it and at which position, a branch that did not see a candidate reports no diagnostic for it, and total disagreement between branches is marked low confidence only when more than one branch actually ran. The lexical, filter and fusion stages log beside expand, embed and search. The fusion opens no database session, calls no provider and knows nothing about products, so its tests run offline against injected fakes and pin the two defaults that are easy to undo by accident.

## Requirements

### Requirement: Fusion combines several ranked lists by rank, never by raw score

The service MUST provide a fusion function that takes several ranked lists of candidate identifiers together with a weight per list and a smoothing constant, and returns one fused order. A candidate's fused score MUST be the sum, over the lists it appears in, of its weight divided by the smoothing constant plus its position in that list. The function MUST NOT read, combine or normalise the raw scores the branches produced, because those scores live on incomparable scales whose distributions change per query. The function MUST be pure: it MUST NOT open a database session, MUST NOT call a provider, MUST NOT open a socket and MUST NOT know anything about products, materials or text. It MUST also return, per candidate, which lists it appeared in and at which position.

#### Scenario: Consensus outranks a single-list champion
- **GIVEN** two ranked lists of equal weight fused with the configured smoothing constant
- **WHEN** one candidate is second in one list and fifth in the other, and another candidate is first in one list and absent from the other
- **THEN** the candidate present in both lists is ordered first

#### Scenario: Raw branch scores are not consumed
- **WHEN** the fusion runs
- **THEN** it receives only ordered identifiers and weights
- **AND** no cosine distance or text rank value takes part in the computation

#### Scenario: Fusion performs no input or output
- **WHEN** the fusion function runs in the unit test suite
- **THEN** no database session is opened
- **AND** no provider is called
- **AND** no socket is opened

#### Scenario: Provenance travels with each candidate
- **WHEN** a candidate is returned by the fusion
- **THEN** the lists it appeared in are reported
- **AND** its position in each of those lists is reported

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

### Requirement: The lexical query is composed from equivalence groups with terms always parameterised

The lexical branch MUST build its query from the equivalence groups the expansion produced, emitting one text-search query per surface form. Forms inside a group MUST be combined disjunctively, and the groups MUST be combined disjunctively with each other. The composition MUST NOT use a conjunction between groups: measured against this corpus, a conjunction leaves the majority of real operator queries matching zero documents, because the conjunction of individually frequent words matches nothing. Every surface form MUST travel as a bound parameter; query syntax MUST NOT be built by string concatenation of operator input. Multi-word surface forms MUST be composed without a positional adjacency constraint, because adjacency was measured to reduce a known dictionary phrase from six matching documents to none.

#### Scenario: A query with an unmatched word still returns candidates
- **GIVEN** a query whose words include one that matches documents the other words do not
- **WHEN** the lexical branch runs
- **THEN** candidates are returned rather than an empty set
- **AND** the documents matching every group are present among them

#### Scenario: Terms never reach the SQL text
- **WHEN** the lexical query is composed
- **THEN** every surface form is passed as a bound parameter
- **AND** no operator input is concatenated into the statement

#### Scenario: A multi-word dictionary form is not required to be adjacent
- **GIVEN** a dictionary form of more than one word whose parts are not adjacent in the indexed documents
- **WHEN** the lexical branch searches for it
- **THEN** the documents containing both parts are matched

### Requirement: The lexical order rewards matching more of the query, and only fields whose absence is evidence may decide it

Within the lexical branch, candidates MUST be ordered first by how many of the query's counting groups the document matches, and only then by the text-rank score. A group MUST count towards that tally only when the absence of its term is evidence that the document is not relevant: that is, when the group resolved to a vocabulary field whose coverage across the corpus is high, or when it did not resolve at all and is therefore a literal word the operator typed. A group that resolved to a sparsely covered vocabulary field MUST NOT count towards the tally, because in such a field absence carries no information — a document without the tag may be perfectly suitable and simply untagged — while still contributing to the text-rank score. The set of sparsely covered fields MUST be fixed in code with its measured coverage recorded beside it, and MUST NOT be exposed as deployment configuration, because it is a property of the corpus and not of the environment.

#### Scenario: Matching more of the query ranks higher
- **GIVEN** two documents that both satisfy the lexical query
- **WHEN** one matches more of the counting groups than the other
- **THEN** it is ordered first, whatever their text-rank scores

#### Scenario: A group matching no document changes nothing
- **GIVEN** one group of the query matches no document in the corpus
- **WHEN** the lexical branch orders its candidates
- **THEN** the order is the same as if that group had not been present
- **AND** no separate step is required to detect and drop it

#### Scenario: A sparsely covered field cannot jump the queue
- **GIVEN** a query naming both a piece type and an occasion
- **AND** the occasion field is present on a small minority of documents
- **WHEN** the lexical branch orders its candidates
- **THEN** a document carrying the occasion tag does not outrank one matching the piece type without it
- **AND** the occasion term still contributes to the text-rank score

#### Scenario: A literal word the operator typed does decide the order
- **GIVEN** a query containing a term the vocabulary does not resolve
- **WHEN** the lexical branch orders its candidates
- **THEN** documents containing that term are ordered ahead of those that do not

#### Scenario: A mostly subjective query leaves the ordering to the vector branch
- **GIVEN** a query whose only resolved terms belong to sparsely covered fields
- **WHEN** the retrieval runs
- **THEN** the lexical ordering does not discriminate between its candidates by tally
- **AND** the fused order is determined mainly by the vector branch, without any additional weight being configured for that case

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

### Requirement: Each candidate reports which branches produced it, and disagreement between branches is a signal

Every returned candidate MUST report the branches that produced it, and the value MUST NOT be a constant. When the vector branch contributed the candidate, its mapped distance MUST be reported as the vector diagnostic; when a lexical branch contributed it, its text-rank MUST be reported as the lexical diagnostic; a diagnostic for a branch that did not see the candidate MUST be absent rather than fabricated.

**When more than one branch actually ran**, the response MUST be marked low confidence when no returned candidate was produced by more than one of them, because that is the signature of the branches disagreeing entirely. That marking MUST NOT change how many candidates are returned or in what order, and MUST NOT suppress results.

**When only one branch ran** — a single-branch mode was requested, or the embedding provider failed and the request degraded to the lexical branch — the consensus rule MUST NOT be applied, because no candidate can appear in two lists when there is only one and the response would be marked low confidence unconditionally. A field that is always true carries no information, which is the same defect as the constant provenance this capability removes. In that case the marking MUST mean that the retriever returned no candidate at all. The number of branches that ran MUST be reported in the fusion stage log, so that a low-confidence marking can always be read against how it was computed.

#### Scenario: Provenance is real, not constant
- **GIVEN** a fused retrieval returning candidates from both branches
- **WHEN** the response is inspected
- **THEN** at least one candidate reports the lexical branch
- **AND** the reported branches are not the same single value for every candidate

#### Scenario: A diagnostic is absent rather than invented
- **GIVEN** a candidate that only the lexical branch produced
- **WHEN** the response is inspected
- **THEN** its lexical diagnostic carries a value
- **AND** its vector diagnostic is absent

#### Scenario: Total disagreement is reported without hiding results
- **GIVEN** both branches ran
- **AND** no returned candidate was produced by more than one branch
- **WHEN** the response is inspected
- **THEN** it is marked low confidence
- **AND** the candidates are still returned
- **AND** their order is unchanged by that marking

#### Scenario: A single-branch response is not marked low confidence for having one branch
- **GIVEN** only one branch ran, because a single-branch mode was requested
- **WHEN** candidates are returned
- **THEN** the response is not marked low confidence
- **AND** the marking is reserved for the case where the retriever returned nothing

#### Scenario: A response degraded to one branch is not marked low confidence either
- **GIVEN** a fused request whose embedding provider failed
- **AND** the lexical branch produced candidates
- **WHEN** the response is inspected
- **THEN** it is not marked low confidence
- **AND** its candidates report only the branch that produced them

#### Scenario: The fusion log says how many branches ran
- **WHEN** the fusion stage logs
- **THEN** it names the branches that actually ran
- **AND** a low-confidence marking can be read against that number

### Requirement: The fused pipeline is observable stage by stage

The retrieval pipeline MUST emit a structured log entry for the lexical stage, for the structural-filter stage and for the fusion stage, beside the expansion, embedding and search stages that already exist. Each MUST carry the request trace identifier. The lexical entry MUST report the number of candidates and its latency; the filter entry MUST report which constraints were extracted and how many candidates were demoted; the fusion entry MUST report the size of each list, how many candidates appeared in more than one list, and whether the response was marked low confidence. The operator query MUST be logged only at debug level, and embedding vectors MUST NOT be logged at information level.

#### Scenario: The new stages are traceable
- **GIVEN** a request whose token carries a trace identifier
- **WHEN** the real retrieval pipeline runs in fused mode
- **THEN** structured log entries for the lexical, filter and fusion stages carry that trace identifier

#### Scenario: The fusion log reports cross-branch agreement
- **WHEN** the fusion stage logs
- **THEN** it reports the size of each fused list
- **AND** it reports how many candidates were produced by more than one list

### Requirement: Fusion tests run offline and pin the measured defaults

Tests for the fusion, the lexical branch and the structural filters MUST run without opening a socket to an embedding provider, an LLM provider or the database, using injected fakes. The suite MUST pin the two defaults that were measured and are easy to undo by accident: that the vector list weighs less than the lexical lists, and that a conjunction is not used between groups. No test may require the index to contain any particular number of rows.

#### Scenario: The suite stays offline
- **WHEN** the fusion and lexical tests run
- **THEN** they use injected fakes
- **AND** no socket is opened to a provider or to the database

#### Scenario: The measured defaults are pinned
- **WHEN** the suite runs
- **THEN** a test fails if the default vector weight is raised to or above the lexical weight
- **AND** a test fails if the groups are combined conjunctively

### Requirement: The lexical branch truncates under a total order, so ties do not decide silently

The lexical branch orders its candidates by coordination and then by textual rank, and truncates at the configured branch depth; that ordering MUST be a total order. Neither magnitude is one, and in this corpus ties are the norm rather than the exception: coordination takes a handful of values by construction, and the textual rank repeats across documents that match the same fields. When the truncation boundary falls inside a tie, which documents survive is undefined.

The ordering MUST therefore carry a final deterministic key after coordination and rank, so that the list entering the fusion is a function of the query and the index alone. The key MUST NOT alter the relative order of candidates that differ in coordination or in rank.

The fusion consumes rank positions, so an undefined order inside a tie propagates to the fused result and from there to any measurement taken over it.

#### Scenario: Equal coordination and rank resolve the same way on every run
- **GIVEN** two indexed documents with the same coordination and the same textual rank
- **AND** the branch depth truncates the lexical list between them
- **WHEN** the same retrieval runs twice against an unchanged index
- **THEN** the same document survives truncation in both runs

#### Scenario: The tiebreak does not disturb the coordination ordering
- **GIVEN** two candidates whose coordination differs
- **WHEN** the lexical branch orders them
- **THEN** the one matching more counting groups precedes the other, regardless of the deterministic key

#### Scenario: The fused result is stable across runs
- **GIVEN** `STUB_MODE` is disabled and an unchanged index
- **WHEN** the same query is served twice in hybrid mode with the same configuration
- **THEN** the fused candidate list is identical in content and order
