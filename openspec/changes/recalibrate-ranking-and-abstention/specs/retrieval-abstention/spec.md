## ADDED Requirements

### Requirement: The abstention rule is fixed from the per-query best-hit distribution, not from the per-document one

The abstention rule MUST be chosen from the distribution of the **best retrieval distance per query**, separating queries the catalogue can answer from queries it cannot. It MUST NOT be chosen from the distribution of distances per judged document, because the two answer different questions: a total overlap between the distances of relevant and irrelevant **documents** does not imply that the best hit of an answerable **query** cannot be separated from the best hit of an out-of-domain one.

That distribution MUST be published, and the report MUST state whether a single value separates the two populations. The form of the rule MUST be selected by a criterion written **before** the distribution is inspected.

#### Scenario: The per-query distribution is published

- **WHEN** the abstention calibration completes
- **THEN** the report contains the best-hit distance distribution of the answerable queries and of the out-of-domain ones
- **AND** states whether a single value separates them

#### Scenario: The selection criterion precedes the measurement

- **WHEN** the abstention rule is adopted
- **THEN** the report cites a criterion recorded before the distribution was inspected
- **AND** names which of the declared forms that criterion selected

#### Scenario: The per-document distribution does not decide the form

- **WHEN** the report justifies the chosen form
- **THEN** the justification rests on the per-query best-hit distribution
- **AND** the per-document distribution is cited as a distinct measurement rather than as the reason

### Requirement: Abstention decides whether to answer and never silently returns an empty page

When the rule decides that the catalogue has no answer, the response MUST return no candidate **and** MUST be marked low confidence, so that a deliberate abstention is distinguishable from a dependency failure and from an empty assortment. A dependency failure MUST continue to fail loudly rather than being served behind an abstention.

An abstention MUST NOT be produced by removing candidates one by one: it is a decision about the query, applied to the whole response.

#### Scenario: A plausible but impossible query is abstained on

- **GIVEN** a query that is plausible in the domain and that the catalogue cannot satisfy
- **WHEN** the retrieval runs with the abstention rule active
- **THEN** no candidate is returned
- **AND** the response is marked low confidence

#### Scenario: A dependency failure is not disguised as an abstention

- **GIVEN** the embedding provider fails and no lexical candidate exists
- **WHEN** the request is served
- **THEN** it fails loudly
- **AND** it is not served as an abstention with an empty candidate list

#### Scenario: An empty assortment is not an abstention either

- **GIVEN** the point-of-sale projection holds no assigned product for the requesting token
- **WHEN** the request is served
- **THEN** it fails loudly as the projection capability defines
- **AND** it is not reported as an abstention

### Requirement: Raising abstention on out-of-domain queries must not cost answers on answerable ones

An abstention rule MUST NOT be adopted unless it raises the abstention rate over the out-of-domain category **and** leaves the answerable queries answered. The report MUST publish both figures for every candidate rule: the abstention rate over out-of-domain queries and the number of answerable queries that became abstentions.

A rule that abstains on any query whose labelled relevant set is non-empty MUST be reported as costing an answer, and that cost MUST be weighed explicitly rather than absorbed into an aggregate.

#### Scenario: Both sides of the trade are published

- **WHEN** a candidate abstention rule is evaluated
- **THEN** the report gives its abstention rate over out-of-domain queries
- **AND** the number of answerable queries it turned into abstentions

#### Scenario: A rule that silences answerable queries is not adopted on the aggregate alone

- **GIVEN** a candidate rule that raises out-of-domain abstention
- **AND** abstains on queries whose labelled relevant set is non-empty
- **WHEN** the decision is taken
- **THEN** that cost is reported for each affected query
- **AND** the decision states it explicitly rather than citing only the aggregate

### Requirement: The out-of-domain category is large enough to calibrate against

The golden set MUST carry enough out-of-domain queries for an abstention rate to be a usable figure, and the count MUST be recorded with the set. Out-of-domain queries MUST be plausible within the domain and impossible for the catalogue, never nonsense text, because a rule measured against nonsense discriminates nothing.

Because every document is grade zero for an out-of-domain query by the annotation criterion, adding such a query MUST NOT require per-document judgements.

#### Scenario: The out-of-domain count is recorded and sufficient

- **WHEN** the golden set is loaded
- **THEN** the number of out-of-domain queries is reported
- **AND** the load fails if it falls below the declared minimum

#### Scenario: An out-of-domain query is plausible and impossible

- **GIVEN** a query in the out-of-domain category
- **WHEN** it is reviewed
- **THEN** it names something a customer could plausibly ask a jeweller for
- **AND** the catalogue contains nothing that satisfies it

#### Scenario: Adding an out-of-domain query needs no per-document labelling

- **WHEN** an out-of-domain query is added to the golden set
- **THEN** no per-document judgement is required for it
- **AND** every retrieved document counts as grade zero by the annotation criterion

### Requirement: Whether the abstention rule alters the candidate set is declared

The adopted rule MUST declare whether it changes which candidates are retrieved or only whether they are served. A rule expressed as a distance bound inside the retrieval statement changes the candidate set; a rule applied after fusion does not.

That declaration MUST be recorded with the rule, because a calibration that re-scores persisted candidate windows is only valid while the candidate set is unchanged.

#### Scenario: The rule declares its effect on the candidate set

- **WHEN** the abstention rule is adopted
- **THEN** the report states whether it alters the candidate set or only the decision to serve it

#### Scenario: A candidate-set-altering rule invalidates persisted windows

- **GIVEN** an abstention rule that changes the retrieval statement's distance bound
- **WHEN** candidate windows captured before that change are re-scored
- **THEN** the run is refused
- **AND** the mismatch is reported

### Requirement: The abstention decision is observable

The stage that decides abstention MUST log, with the request trace identifier, the rule in force, the best distance observed for the query, and the decision taken. It MUST NOT log any embedding vector.

#### Scenario: The abstention decision is logged with its inputs

- **WHEN** the abstention stage runs
- **THEN** it logs the rule in force, the best observed distance and the decision
- **AND** the entry carries the request trace identifier

#### Scenario: No vector reaches the logs

- **WHEN** the abstention stage logs
- **THEN** no embedding vector appears in the entry

### Requirement: Abstention tests run offline

Tests for this capability MUST run without calling an embedding provider, a language model provider or a remote database. The rule's behaviour MUST be exercised against fixtures, including the case of an answerable query that must not be abstained on.

#### Scenario: The offline suite makes no external call

- **GIVEN** the abstention test suite
- **WHEN** it runs without credentials configured
- **THEN** it passes
- **AND** no provider call and no network call is made

#### Scenario: An answerable query is not abstained on

- **GIVEN** a fixture query whose labelled relevant set is non-empty
- **WHEN** the abstention rule is applied
- **THEN** candidates are returned
- **AND** the response is not an abstention
