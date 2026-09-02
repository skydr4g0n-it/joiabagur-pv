## ADDED Requirements

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

The per-list weights and the smoothing constant MUST be read from settings and MUST NOT be written into the code. Their effective values MUST also travel as parameters of the retrieval orchestration call, so that several configurations can be evaluated in one process without restarting it and without adding a field to the retrieval request schema. The default weight of the vector list MUST be lower than the default weight of either lexical list, because the vector branch returns a full list of candidates whether or not it has understood the query and therefore always votes at full strength. The two lexical weights MUST sum to the weight of a single lexical list, so that when expansion is disabled — and the two lexical lists become identical — the fused result is exactly what one lexical list at full weight would produce.

#### Scenario: Weights are not hardcoded
- **WHEN** the fused retrieval runs
- **THEN** the weights and the smoothing constant come from settings or from the call parameters
- **AND** no weight value is written into the fusion module

#### Scenario: Two configurations run in one process
- **GIVEN** the settings supply a default set of weights
- **WHEN** the orchestration call is made once with those weights and once with different ones
- **THEN** both calls succeed without restarting the process
- **AND** neither call mutates the settings object

#### Scenario: The vector branch does not outweigh the lexical branch by default
- **WHEN** the default configuration is loaded
- **THEN** the weight of the vector list is lower than the weight of the typed lexical list
- **AND** it is lower than the weight of the expanded lexical list

#### Scenario: Disabled expansion degrades to a single lexical vote
- **GIVEN** query expansion is disabled, so the typed and expanded lists are identical
- **WHEN** the fusion runs
- **THEN** the fused order is the same as fusing one lexical list at the combined lexical weight

### Requirement: All fused lists are truncated at the same depth, coupled to the smoothing constant

Every list entering the fusion MUST be truncated at the same depth, and that depth MUST be configurable. The depth MUST be of the same order as the smoothing constant, because a list far longer than the smoothing constant hands positive votes to candidates the other lists do not score at all, and that tail displaces the candidates two lists rank well without ranking first. The branch depth MUST be a separate parameter from the size of the over-retrieval window the endpoint returns, which depends on the page size the caller requested, even when their default values coincide.

#### Scenario: The three lists are cut at the same point
- **GIVEN** the lexical branch matched several hundred documents and the vector branch returned a full list
- **WHEN** the fusion runs
- **THEN** every list is truncated at the configured depth before fusing
- **AND** no list enters the fusion longer than another

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

Filters inferred by rule from the operator's text — a price ceiling, a size, materials named in the query — MUST be applied as an ordering and MUST NOT remove any candidate. Candidates breaking such a constraint MUST be moved behind those satisfying it while preserving the fused order within each block, and MUST remain inside the over-retrieval window that is returned, so that the caller that owns the authoritative price and stock still sees them. Filters supplied explicitly in the request body MUST keep excluding, because a person selected them. The retriever MUST NOT require a candidate to carry every material named in the query, and MUST NOT invent a filter the query did not express. The piece type MUST NOT be applied as a filter at all, because a lexical match on the canonical term is already equivalent to filtering by it and a filter would constrain only the branch that rescues paraphrase.

#### Scenario: A price ceiling reorders without removing
- **GIVEN** the query expresses a price ceiling
- **WHEN** the retrieval runs
- **THEN** candidates within the ceiling are ordered ahead of those above it
- **AND** the fused order is preserved inside each of those two blocks
- **AND** candidates above the ceiling are still present in the returned candidates

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

Every returned candidate MUST report the branches that produced it, and the value MUST NOT be a constant. When the vector branch contributed the candidate, its mapped distance MUST be reported as the vector diagnostic; when a lexical branch contributed it, its text-rank MUST be reported as the lexical diagnostic; a diagnostic for a branch that did not see the candidate MUST be absent rather than fabricated. The response MUST be marked low confidence when no returned candidate was produced by more than one branch, because that is the signature of the branches disagreeing entirely. That marking MUST NOT change how many candidates are returned or in what order, and MUST NOT suppress results.

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
- **GIVEN** no returned candidate was produced by more than one branch
- **WHEN** the response is inspected
- **THEN** it is marked low confidence
- **AND** the candidates are still returned
- **AND** their order is unchanged by that marking

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
