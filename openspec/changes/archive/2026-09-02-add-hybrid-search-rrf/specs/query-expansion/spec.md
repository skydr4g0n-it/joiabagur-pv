## ADDED Requirements

### Requirement: The enable flag selects the expansion arm without touching the request contract
Expansion MUST be controlled by a flag whose default is supplied by settings and whose effective value is passed as a parameter of the retrieval orchestration call, so that a caller can evaluate several configurations in one process. The flag MUST NOT be added to the retrieval request schema and MUST NOT cause the committed OpenAPI snapshot to be regenerated. When expansion is disabled every token MUST become a single-element group carrying its original form and `matched` MUST be empty.

Disabling the flag now changes what the endpoint returns, because the lexical branch consumes the groups: the expanded lexical list degenerates into the typed one. The fusion MUST degrade exactly, so that the result is the same as fusing a single lexical list at the combined lexical weight. Turning the flag off therefore remains a meaningful rollback and a valid ablation arm rather than an inconsistent state.

#### Scenario: Disabled expansion yields the original tokens
- **GIVEN** the expansion flag is disabled
- **WHEN** a query containing a known synonym is expanded
- **THEN** every group has exactly one element equal to the typed token
- **AND** `matched` is empty

#### Scenario: The flag is not part of the request contract
- **WHEN** the change is applied
- **THEN** the retrieval request schema has no expansion field
- **AND** the committed OpenAPI snapshot is not regenerated

#### Scenario: Two configurations run in one process
- **GIVEN** the settings default enables expansion
- **WHEN** the orchestration call is made once with expansion enabled and once disabled
- **THEN** both calls succeed without restarting the process
- **AND** neither call mutates the settings object

#### Scenario: Disabling expansion degrades the fusion exactly
- **GIVEN** the expansion flag is disabled, so the typed and expanded lexical lists are identical
- **WHEN** the retrieval pipeline runs
- **THEN** the fused order equals the order produced by fusing one lexical list at the combined lexical weight
- **AND** no candidate is counted twice for appearing in both identical lists

### Requirement: Expansion emits a stage log and its result is consumed by the lexical branch
The retrieval pipeline MUST emit a structured log entry for the expansion stage alongside the embed, search, lexical, filter and fusion stages, carrying the request trace identifier, whether expansion was enabled, the token count and the number of resolved terms. The operator query MUST be logged only at Debug level, and the full expanded classes MUST NOT be logged at Information level.

The expansion result MUST be consumed by the lexical branch: its groups compose the expanded lexical query, and its resolved terms are the lookup the rule-based structural filters use, so that no second mapping from typed term to vocabulary field is built over the same data. The log entry MUST no longer report the result as unconsumed.

#### Scenario: The expansion stage is traceable
- **GIVEN** a request whose token carries a trace identifier
- **WHEN** the real retrieval pipeline runs
- **THEN** a structured log entry for the expansion stage carries that trace identifier
- **AND** it reports whether expansion was enabled and how many terms resolved

#### Scenario: The groups reach the lexical query
- **GIVEN** expansion is enabled and the query contains a known synonym
- **WHEN** the retrieval pipeline runs
- **THEN** the lexical branch searches for the canonical surface forms of that synonym's class
- **AND** the response contains candidates that the typed form alone would not have matched

#### Scenario: The resolved terms feed the structural filters
- **GIVEN** expansion is enabled and the query names a material of the closed vocabulary
- **WHEN** the rule-based structural filters are extracted
- **THEN** they are derived from the resolved terms the expansion already reported
- **AND** no second lookup table from typed term to vocabulary field is built

## REMOVED Requirements

### Requirement: The enable flag turns expansion off without changing the response
**Reason**: The clause requiring the HTTP response to be unchanged when the flag is toggled was true only while nothing consumed the expansion. The lexical branch now consumes it, so toggling the flag legitimately changes what is returned. Replaced by *The enable flag selects the expansion arm without touching the request contract*, which keeps every other guarantee — settings default, value by parameter, no request-schema field, single-element groups when disabled — and states the exact degradation instead.

**Migration**: None for callers: the request and response schemas are unchanged and the flag was never part of either. Anything asserting byte-identical responses across the flag must instead assert the exact fusion degradation described in the replacement requirement.

### Requirement: Expansion emits a stage log and is not consumed until the lexical branch exists
**Reason**: The lexical branch exists as of this change and consumes the expansion, so the requirement's central clause — that the result must not alter the retrieval response in any way — no longer describes the system. Replaced by *Expansion emits a stage log and its result is consumed by the lexical branch*, which keeps the observability contract unchanged and states what consumes the groups and the resolved terms.

**Migration**: None for callers. Anything treating `stage=expand` as evidence that the expansion is inert must instead read the lexical and fusion stage logs, which report what the groups produced.
