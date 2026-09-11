# retrieval-evaluation Specification

## Purpose
How retrieval quality is measured in this service, and what makes one measurement comparable to another. The yardstick is a golden set versioned in the repository under `ai-service/evals/golden/` — the queries, the graded judgements, the frozen query vectors and the written annotation criterion that predates the first judgement — and never a database table, so moving the yardstick costs a code review and every figure taken before a move stays interpretable against the version it used. Its composition is not a documented intention but an executable validation that fails the load: queries whose best document shares no term with them after synonym expansion, queries that resolve only to fields of low corpus coverage, stone-value queries the piece type does not discriminate, the three classes of synonym dictionary entry, out-of-domain queries plausible within the jewellery domain rather than nonsense every configuration abstains on, literal code and product-name queries, and anchoring to real products evaluated per category so that no category is composed entirely of synthetic ones. Queries that were used to fix the fusion weights, the branch depth or the coordination rule carry a mark, and every metric is published three times — whole set, tuning subset, new queries — because a result visible only on the first is not a confirmation but a candidate for overfitting.

Judgements are graded on three levels and published on both scales under one declared binarisation rule, with a divergence between the two readings reported as a finding rather than resolved by picking one. They are keyed by the pair of query and document, so a later configuration appends to them instead of re-recording what exists, and each carries the content hash of the text it was made against, so labels resting on since-changed documents are counted beside the metrics and not in a separate log. The judged pool is the union of what the indexed configurations return, deepened in blocks while the previous block still contributed a relevant document and stopped at the branch depth beyond which the live retriever cannot surface anything; the depth reached is recorded per query, everything outside the pool is declared irrelevant by assumption, and the unjudged share of a configuration's top results marks that row not comparable instead of scoring it silently. Retrieval always executes over the complete indexed catalogue — restricting the corpus by data origin is not an available configuration — while the breakdown by origin counts only the relevant documents of each, and the report records how often an irrelevant synthetic product outranks the first relevant real one, so that interference is measured rather than assumed.

The comparison is against baselines that replicate what they claim to replicate: the substring-over-name plus exact-code product search that preceded this project's AI work, the degraded Spanish full-text searcher composed over the same text the .NET side indexes rather than over the richer canonical document — an equivalence an automated test breaks when the renderer drifts — and a context-only configuration that places the whole catalogue in the model context without retrieval, priced per query, carrying no product price, truncating deterministically with the omitted count recorded, and projected to the catalogue size at which it no longer fits. Every run records its provenance — golden set version, configuration, index fingerprint, embedding model version and code revision — and two runs whose provenance differs are reported as not comparable rather than compared; query embeddings are frozen per embedding model version so that repeating a run does not depend on a provider answering identically. Latency is two figures, retrieval and end-to-end, measured warm with the first execution discarded, and cost comes from a versioned price list, recorded as zero rather than absent for a configuration that calls no paid provider and declared unverified when the source cannot be reached. Abstention is measured over the out-of-domain category with its distance distribution published, and its figures stay provisional while this capability leaves the live distance threshold untouched. A configured default moves only under a rule written before the measurement, and the outcome is documented whether or not anything moves. The normative output is the versioned report and the per-query detail under `ai-service/evals/results/`, written on every run; persistence to the evaluation tables is optional and the component that produces the results does not depend on the one that stores them. The harness tests run offline against fixtures, with no provider and no production database.

## Requirements

### Requirement: The golden set is a versioned repository artefact with a written annotation criterion
The golden set, its judgements, its frozen query vectors and its annotation criterion MUST live as files under `ai-service/evals/golden/` and be versioned in the repository. They MUST NOT be stored only in the database: changing the yardstick MUST require a code review, and every measurement taken before a change MUST remain interpretable against the version it used.

The annotation criterion MUST be written before any judgement is recorded, and MUST define each grade by a condition that can be checked against the query and the document, not by a subjective impression. The set MUST carry a version identifier that every evaluation run records.

#### Scenario: The criterion exists before the first judgement
- **WHEN** the golden set is loaded
- **THEN** an annotation criterion document exists alongside it
- **AND** the criterion defines the intermediate grade as a failure of one attribute the query named explicitly
- **AND** no judgement predates the criterion

#### Scenario: The golden set is not read from the database
- **WHEN** the harness loads the golden set
- **THEN** it reads the repository files
- **AND** it does not require a database connection to do so

### Requirement: The golden set composition is validated by code and its violation fails the load
Loading the golden set MUST fail when the set does not satisfy the composition that makes it able to arbitrate the disputes it exists for. The validation MUST be executable and MUST NOT be a documented intention.

The set MUST contain at least: twelve queries with at least one maximum-grade document whose canonical text contains **no term of the query after synonym expansion**; five queries that resolve only to fields of low corpus coverage; four queries that name a stone value where the piece type does not discriminate; six synonym queries covering the three classes of dictionary entry — stemmer artefact, commercial synonym and directional bridge; five out-of-domain queries that are plausible within the jewellery domain and have no relevant document; and four queries that are a literal code or product name.

Anchoring to real products MUST be evaluated per category, so that no category is composed entirely of synthetic products.

#### Scenario: A set without unanchored queries is rejected
- **WHEN** the golden set contains fewer than twelve queries whose best document shares no term with the query after expansion
- **THEN** the load fails and names the unmet requirement
- **AND** no evaluation runs

#### Scenario: Nonsense text does not satisfy the out-of-domain category
- **WHEN** an out-of-domain query is not plausible within the jewellery domain
- **THEN** the load fails
- **AND** the message states that every configuration abstains on nonsense, so the metric would not discriminate

#### Scenario: A wholly synthetic category is rejected
- **WHEN** every relevant document of a category belongs to synthetic products
- **THEN** the load fails
- **AND** the message states that the category cannot be compared across data origins

### Requirement: Relevance is graded, and both the graded and the binary readings are published
Each judgement MUST take one of three grades. The report MUST publish every ranking metric twice: once using the grades and once using the binary reading derived from them, where a document is relevant when its grade is at least the intermediate one. The binarisation rule MUST be fixed and declared, never chosen per configuration.

When the two readings order the configurations differently, the report MUST state it as a finding.

#### Scenario: Both readings appear in the report
- **WHEN** an evaluation run completes
- **THEN** the report contains the graded metrics and the binary metrics for every configuration
- **AND** the binarisation rule is stated once and applies to all of them

#### Scenario: Divergence between readings is surfaced
- **WHEN** the graded reading and the binary reading rank two configurations in opposite order
- **THEN** the report states that the comparison is not robust to the choice of scale

### Requirement: Queries used to calibrate the retriever are marked and reported separately
Queries that were used to fix the fusion weights, the branch depth or the coordination rule MUST be marked in the golden set. Every metric MUST be reported three times: over the whole set, over the marked subset only, and over the unmarked subset only.

A configuration decision MUST NOT be presented as confirmed unless the result points the same way in the three readings.

#### Scenario: The three readings are published
- **WHEN** an evaluation run completes
- **THEN** each metric appears for the whole set, for the tuning subset and for the new queries
- **AND** queries carry the mark that assigns them to a subset

#### Scenario: A result that only holds on the tuning subset is not a confirmation
- **WHEN** a configuration wins on the tuning subset and loses on the new queries
- **THEN** the report states that the decision is not confirmed
- **AND** identifies the divergence as possible overfitting

### Requirement: Pooling deepens where relevant documents keep appearing and declares how far it judged
The set of documents to judge MUST be the union, without repetition, of what each indexed configuration returns. Documents outside that union MUST be treated as irrelevant, and that assumption MUST be declared in the report.

Pooling MUST start at a common base depth, MUST continue in blocks while the previous block contributed at least one relevant document, and MUST stop at the branch depth beyond which the live retriever cannot surface a document. The depth reached MUST be recorded per query.

#### Scenario: A query with few relevant documents stops early
- **WHEN** a block of pooled documents contributes no relevant document
- **THEN** pooling stops for that query
- **AND** the depth reached is recorded

#### Scenario: Pooling never exceeds what the retriever can show
- **WHEN** pooling would continue past the configured branch depth
- **THEN** it stops at that depth
- **AND** the report states that documents beyond it cannot be surfaced by the live pipeline

### Requirement: Judgements are appendable and unjudged results are reported
Judgements MUST be identified by the pair of query and document, so that a later change can add judgements without re-recording the existing ones. Every configuration MUST report the proportion of its top results that carry no judgement, and a configuration whose proportion is high MUST be marked as not comparable in the report.

#### Scenario: A later configuration adds judgements without invalidating the previous ones
- **WHEN** judgements are added for documents that were not previously pooled
- **THEN** the existing judgements are unchanged
- **AND** the golden set version reflects the addition

#### Scenario: A configuration promoting unjudged documents is not silently penalised
- **WHEN** a configuration returns results a large share of which carry no judgement
- **THEN** the report states the share
- **AND** marks that row as not comparable rather than presenting its score as final

### Requirement: Metrics are reported by data origin and retrieval always runs over the whole corpus
Retrieval MUST execute over the complete indexed catalogue regardless of the breakdown. Queries MUST be grouped by the origin of their relevant documents, and each group's metrics MUST count only the relevant documents of that origin. Restricting the retrieval corpus to a single origin MUST NOT be an available configuration.

The report MUST additionally record how often an irrelevant synthetic product outranks the first relevant real document, so that "the synthetic corpus is easier" can be distinguished from "the synthetic corpus interferes".

#### Scenario: The real portion is not measured over a smaller corpus
- **WHEN** metrics are computed for the real portion
- **THEN** the retrieval that produced them ran over the whole indexed catalogue
- **AND** no configuration exists that restricts the corpus by data origin

#### Scenario: Synthetic interference is measured, not assumed
- **WHEN** a query whose relevant documents are real is evaluated
- **THEN** the report records whether an irrelevant synthetic product preceded the first relevant real document

### Requirement: Baseline configurations replicate the semantics they claim to replicate
The evaluation MUST include a baseline that reproduces the product search that existed before this project's AI work — substring match over the product name plus exact code match — and a separate baseline that reproduces the degraded Spanish full-text searcher. The two MUST carry names that do not confuse one with the other.

The full-text baseline MUST be composed over the same text the .NET searcher indexes, and MUST NOT be composed over the canonical document, which carries additional extracted fields and would make the baseline stronger than the thing it replicates. An automated test MUST fail if the canonical document renderer changes in a way that breaks that equivalence.

Neither baseline calls an external provider, and both MUST record a cost of zero rather than an absent value.

#### Scenario: The legacy baseline answers a natural-language query the way the old searcher did
- **WHEN** the legacy baseline is evaluated on a multi-word natural-language query
- **THEN** it returns only products whose name contains the query as a substring
- **AND** its behaviour matches the pre-existing product search semantics

#### Scenario: The full-text baseline does not see the extracted fields
- **WHEN** the full-text baseline is composed
- **THEN** the text it searches consists of the product name, the code and the description line
- **AND** it does not include the extracted type, materials, colours, style or occasion lines

#### Scenario: A renderer change breaks the fidelity test, not the fidelity
- **WHEN** the canonical document renderer stops emitting the description line with its expected prefix
- **THEN** the fidelity test fails

### Requirement: The context-only baseline measures why retrieval exists, and declares what it did not see
The evaluation MUST include a configuration that places the whole catalogue in the model context without retrieval. It MUST record the size in tokens of that context, the cost per query, and the projection of that size for larger catalogues up to the point where it no longer fits.

The context MUST NOT contain product prices, because the authority over price is not this service. When the catalogue exceeds the configured context budget, the configuration MUST truncate deterministically and MUST record how many documents were omitted, rather than failing or truncating silently.

Its measurement MUST be recorded with the model and the date that produced it, and MUST NOT be presented as reproducible.

#### Scenario: A catalogue larger than the budget is truncated deterministically
- **WHEN** the compacted catalogue exceeds the context budget
- **THEN** the omitted documents are the same on every run
- **AND** the run records how many were omitted
- **AND** the reported recall is accompanied by that count

#### Scenario: The context carries no price
- **WHEN** the context-only configuration builds its prompt
- **THEN** no product price appears in it

#### Scenario: The scale projection is part of the result
- **WHEN** the context-only configuration is measured
- **THEN** the report states the token size for the current catalogue and for larger ones
- **AND** identifies the size at which the catalogue no longer fits

### Requirement: A run is comparable to another only when its provenance matches
Every evaluation run MUST record the golden set version, the configuration, a stable fingerprint of the indexed document set, the embedding model version and the code revision that produced it. Two runs whose provenance differs MUST be reported as not comparable rather than compared.

Query embeddings MUST be frozen as a versioned artefact keyed by the embedding model version, so that repeating a run does not depend on the provider answering identically.

#### Scenario: Repeating a run yields identical metrics
- **WHEN** the same configuration runs twice with the same provenance
- **THEN** the metrics are identical

#### Scenario: A moved index makes previous runs incomparable
- **WHEN** the indexed document set changes and a run is compared with an earlier one
- **THEN** the report states that the two are not comparable and names the differing element

### Requirement: Abstention is measured and its distance distribution published, and the threshold is not changed
The evaluation MUST measure abstention over the out-of-domain category and MUST publish the distribution of retrieval distances separating relevant from irrelevant documents.

The report MUST state that the abstention figures are provisional, because the live distance threshold admits substantially the whole catalogue and the observed abstention therefore reflects branch mechanics rather than a confidence decision. This change MUST NOT modify the live distance threshold.

#### Scenario: The distribution is published per grade
- **WHEN** an evaluation run completes
- **THEN** the report contains the distance distribution of relevant documents and of irrelevant ones
- **AND** states whether the two are separable by a single value

#### Scenario: Abstention figures are marked provisional
- **WHEN** abstention is reported
- **THEN** the report states that recalibration of the threshold belongs to a later change
- **AND** the configured threshold is unchanged by this one

### Requirement: Judgements record the document text they were made against
Every judgement MUST record the content hash the document carried when it was judged. Each run MUST report how many judgements rest on a document whose text has since changed, and that figure MUST appear alongside the metrics rather than in a separate log.

#### Scenario: A re-enriched product is detected after labelling
- **WHEN** a judged document's canonical text changes after the judgement was recorded
- **THEN** the run reports that judgement as resting on stale text
- **AND** the count appears next to the metrics

### Requirement: The report is always written to the repository and database persistence is optional
Every run MUST produce a versioned report and a per-query detail file under `ai-service/evals/results/`. Writing to the evaluation tables MUST happen only when explicitly requested, and the component that produces the results MUST NOT depend on the component that persists them.

The harness MUST produce its report even when nothing is written to the database.

#### Scenario: A run without persistence still produces its report
- **WHEN** the harness runs without requesting persistence
- **THEN** the report and the per-query detail are written to the repository
- **AND** no evaluation table is written

#### Scenario: Baseline runs are persisted like any other
- **WHEN** persistence is requested
- **THEN** the runs of the zero-cost baselines are persisted as well
- **AND** the ablation table is complete rather than missing its reference rows

### Requirement: Latency is reported as two figures, measured warm and repeated
Each configuration MUST report the retrieval latency excluding the embedding provider round trip and the end-to-end latency including it. The acceptance criterion for latency applies to the first. The report MUST publish the second alongside the agreed budget.

Measurement MUST discard the first execution of each query and MUST repeat the remaining ones, so that the reported percentiles do not describe a cold start.

#### Scenario: Both latency figures appear per configuration
- **WHEN** an evaluation run completes
- **THEN** each configuration reports retrieval latency and end-to-end latency
- **AND** the acceptance criterion is applied to the retrieval figure

#### Scenario: The cold execution is excluded
- **WHEN** latency is measured for a query
- **THEN** the first execution is discarded
- **AND** the reported percentiles derive from the repeated warm executions

### Requirement: Cost per query is recorded for every configuration from a versioned price list
Provider prices MUST live in a versioned file carrying the date and the source they were taken from. Every configuration MUST record a cost per query, and a configuration that calls no paid provider MUST record zero rather than an absent value.

When the price source cannot be verified at measurement time, the file MUST record that the date is unknown and the report MUST declare the cost as unverified rather than carrying figures taken from memory.

#### Scenario: A configuration without provider calls records zero
- **WHEN** a lexical baseline is evaluated
- **THEN** its recorded cost per query is zero

#### Scenario: Unverifiable prices are declared, not invented
- **WHEN** the price source cannot be reached while measuring
- **THEN** the price file records an unknown date
- **AND** the report declares the cost figures unverified

### Requirement: A configured default changes only when the verdict is material
A default retrieval setting MUST NOT be changed on the basis of this evaluation unless the improvement exceeds the agreed margin, points the same way in the three readings of the tuning split, and degrades no measured category beyond the agreed margin. The rule MUST be recorded before the measurement is executed.

The outcome MUST be documented whether or not any default moves.

#### Scenario: A small improvement does not move a default
- **WHEN** a configuration improves the ranking metric by less than the agreed margin
- **THEN** the default is unchanged
- **AND** the report records the measured difference and the decision not to act on it

#### Scenario: A change of default is justified against the written rule
- **WHEN** a default is changed
- **THEN** the report shows the three readings and the per-category effect
- **AND** cites the rule that was written before the measurement

### Requirement: Evaluation tests run offline
The test suite of the evaluation harness MUST run without calling embedding providers, language model providers or a production database. Metric computation, golden set validation, pooling and report generation MUST be exercised against fixtures.

#### Scenario: The suite passes with no provider reachable
- **WHEN** the evaluation tests run with no provider credentials available
- **THEN** they pass
- **AND** no outbound provider call is made

#### Scenario: A ranking metric is verified against a hand-computed value
- **WHEN** the ranking metric is computed over a fixed fixture
- **THEN** it equals the value computed by hand for that fixture
