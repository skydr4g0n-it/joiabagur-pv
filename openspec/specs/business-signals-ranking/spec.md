# business-signals-ranking Specification

## Purpose
Soft reordering of the retrieved candidates by the business signals the point-of-sale projection carries, calibrated against the golden set rather than asserted. The signal is read without restricting the candidate set: the scope that only reads the projection and the scope that restricts the assortment are two independent parameters of the retrieval orchestration call, so the gain of reordering by availability is measurable apart from the recall cost of the prefilter, and a candidate the point of sale does not carry reports its signals as absent rather than as zero. Availability is applied as a continuous score inside the last block of the ordering key and never as a component that could overturn a price ceiling, a size or a material the operator typed; it demotes and never removes, every candidate stays inside the over-retrieval window because the caller owns the authoritative price and stock, and no exact quantity reaches the response or the logs.

`sales_30d` travels on a retrieved candidate for diagnosis and orders nothing. That prohibition is structural rather than promised — the interface the ordering reads does not carry the field and no weight is declared for it — and it rests on measurement: over the judged set a rule acting only between candidates the fusion ranks equally decided no pair at all, while the same signal used as a component of the ordering key reordered candidates the fusion had separated by many positions and displaced better-graded documents. Weights are configuration and travel as call parameters, so several configurations are evaluated in one process without mutating the settings object, and setting every one of them to zero reproduces the order the fusion and the typed-constraint blocks alone produce.

A weight is adopted under an operational metric whose gain function of labelled grade and availability signal is declared before the measurement is executed and never modifies the recorded judgements, because the annotation criterion judges what a piece is and never what the shop has. Pure relevance is the guardrail: no configuration and no measured category may lose more than the agreed margin, and where the ordering is invariant to a weight's value the report presents the adopted figure as a declared unit rather than as a fitted one. The calibration sweep runs in two phases — a capture phase that retrieves each query once under a frozen fusion configuration and persists its candidate window with the signals each candidate carries, and a re-score phase that explores the weight grid over those windows, reaching no embedding provider and no database, reproducible to the digit, and refusing windows captured under a different fusion. The stage logs its weights and its effect beside the other stages, and its tests run offline.

## Requirements

### Requirement: Business signals are read from the point-of-sale projection without restricting the candidate set
The retriever SHALL be able to read a candidate's availability bucket and sales window from the point-of-sale projection **without** restricting the candidate set to that point of sale. The scope that restricts and the scope that only reads MUST be two independent parameters of the retrieval orchestration call, so that the effect of reordering by availability can be measured separately from the recall cost of the assortment prefilter.

When only the reading scope is supplied, the join MUST preserve every candidate the branches produced. A candidate the point of sale does not carry MUST report its signals as absent, and absent MUST NOT be treated as a value of zero.

#### Scenario: Reading the signal does not reduce the candidate set
- **GIVEN** a query served with the reading scope supplied and the restricting scope omitted
- **WHEN** the candidate set is compared with the same query served with neither
- **THEN** the two candidate sets are identical
- **AND** in the first, candidates the point of sale carries report their availability bucket and their sales window

#### Scenario: A candidate outside the assortment reports absent signals, not zero
- **GIVEN** a candidate that the reading scope's point of sale does not carry
- **WHEN** the candidate is ordered
- **THEN** its availability and sales signals are absent
- **AND** no ordering rule treats that absence as zero stock or as zero sales

#### Scenario: The restricting scope still restricts when supplied
- **GIVEN** a query served with the restricting scope supplied
- **WHEN** the retrieval runs
- **THEN** every candidate belongs to that point of sale's assortment
- **AND** the behaviour is the one the projection capability already defines

### Requirement: The business score orders only candidates that typed constraints rank equally
Availability MUST be applied as a continuous score that decides the order **within** the last block of the ordering key, and MUST NOT be able to overturn a constraint the operator expressed in the query. The blocks produced by a price ceiling, a size or a material named in the text MUST keep their lexicographic precedence over the business score.

No candidate may be removed on the basis of a business signal, and every candidate MUST remain inside the over-retrieval window that is returned, because the caller owns the authoritative price and stock.

#### Scenario: A typed constraint outranks the business score
- **GIVEN** a query expressing a price ceiling and candidates differing in both price and availability
- **WHEN** the candidates are ordered
- **THEN** candidates within the ceiling precede candidates above it regardless of their availability
- **AND** the business score decides the order only between candidates the typed constraints rank equally

#### Scenario: An out-of-stock candidate is demoted and still returned
- **GIVEN** a point of sale carrying both in-stock and zero-stock candidates that match the query
- **WHEN** the candidates are ordered
- **THEN** the zero-stock candidates appear after comparable in-stock ones
- **AND** they are still present among the returned candidates

#### Scenario: No stock value reaches the response as a quantity
- **WHEN** a response carrying business-ranked candidates is inspected
- **THEN** no field reports an exact stock quantity
- **AND** the availability signal is never emitted as a number of units

### Requirement: The sales window is read for diagnosis and orders nothing
The sales window SHALL be readable from the projection and carried on a retrieved candidate, so that the evaluation can publish its distribution and a later capability has an input. **No ordering rule may consume it.** The guarantee MUST be structural rather than a promise: the interface the ordering reads MUST NOT carry the field at all, so a rule cannot consume it by accident.

A weight for it MUST NOT be declared, because a weight is a statement that a signal orders something.

The report MUST record why it orders nothing, and the reason MUST rest on measurement rather than on caution: measured over the judged set, a rule acting only between candidates the fusion ranks **equally** decided no pair at all inside the reported window, while the same signal applied as a component of the ordering key reordered candidates the fusion had separated by many positions and displaced better-graded documents.

#### Scenario: The sales window reaches a candidate
- **WHEN** a candidate is retrieved with a reading scope supplied
- **THEN** its sales window is available for diagnosis
- **AND** a candidate the point of sale does not carry reports it as absent rather than as zero

#### Scenario: The ordering cannot see the sales window
- **WHEN** the interface the ordering reads is inspected
- **THEN** it does not carry the sales window
- **AND** no ordering module names it

#### Scenario: Two candidates differing only in their sales window keep the fused order
- **GIVEN** two candidates the fusion and the availability signal rank equally, one of which sold in the window and one of which did not
- **WHEN** the candidates are ordered
- **THEN** their relative order is the one the fusion produced

#### Scenario: No weight is declared for it
- **WHEN** the settings are inspected
- **THEN** no weight governs the sales window
- **AND** the report states the measured reason it orders nothing

### Requirement: Weights are configuration and travel as call parameters
Every business-signal weight MUST be read from settings and MUST NOT be written into the code. Their effective values MUST also travel as parameters of the retrieval orchestration call, so that several weight configurations can be evaluated in one process without restarting it and without adding a field to the retrieval request schema. A call MUST NOT mutate the settings object.

Setting every business weight to zero MUST reproduce the ordering the pipeline produced before this capability existed.

#### Scenario: No weight is hardcoded
- **WHEN** the business-signals ordering runs
- **THEN** every weight comes from settings or from the call parameters
- **AND** no weight value is written into the ordering module

#### Scenario: Two weight configurations run in one process
- **GIVEN** the settings supply a default set of business weights
- **WHEN** the orchestration call is made once with those weights and once with different ones
- **THEN** both calls succeed without restarting the process
- **AND** neither call mutates the settings object

#### Scenario: Zero weights restore the previous ordering
- **GIVEN** every business weight is set to zero
- **WHEN** the retrieval runs
- **THEN** the order is the one the fusion and the typed-constraint blocks alone produce

### Requirement: Business weights are calibrated against an operational metric with a relevance guardrail
A business weight MUST NOT be adopted on the basis of a ranking metric computed over labelled relevance alone, because the annotation criterion of the golden set judges what a piece **is** and never what the shop **has**, so such a metric is at best orthogonal to availability and at worst adversarial to it.

The objective MUST be an operational metric whose gain function is a declared function of the labelled grade and the availability signal, published together with the pure-relevance reading. Where the measurement shows the ordering to be invariant to a weight's **value** — as it is for a signal with two states — the report MUST say so and MUST present the adopted figure as a declared unit rather than as a fitted one, because publishing an invariant number as a calibrated result claims evidence that was never produced. The pure-relevance reading MUST act as a **guardrail**: a weight configuration that improves the operational metric while degrading pure relevance by more than the agreed margin MUST NOT be adopted. No measured category may degrade by more than that margin either.

The gain function MUST be declared before the measurement is executed, and the recorded judgements MUST NOT be modified by it.

#### Scenario: The operational gain is a declared function of grade and availability
- **GIVEN** a judged document whose availability bucket reports zero stock
- **WHEN** the operational metric is computed
- **THEN** its effective gain is the one the declared function yields for that grade and bucket
- **AND** the judgement file is unchanged

#### Scenario: Both readings are published side by side
- **WHEN** a calibration report completes
- **THEN** it contains the operational metric and the pure-relevance metric for every configuration
- **AND** the gain function is stated once and applies to all of them

#### Scenario: A weight that costs more relevance than the margin is rejected
- **GIVEN** a weight configuration that improves the operational metric
- **AND** degrades the pure-relevance metric by more than the agreed margin
- **WHEN** the decision rule is applied
- **THEN** the configuration is not adopted
- **AND** the report records the measured difference and the decision not to act on it

#### Scenario: A degraded category blocks adoption
- **GIVEN** a weight configuration that improves the aggregate
- **AND** degrades one measured category by more than the agreed margin
- **WHEN** the decision rule is applied
- **THEN** the configuration is not adopted

### Requirement: The weight sweep re-scores persisted candidate windows and is exactly reproducible
Because business signals reorder the candidates the branches produced and never change which candidates are produced, the calibration sweep SHALL run in two phases: a **capture** phase that retrieves each query once under a frozen fusion configuration and persists its candidate window together with the signals each candidate carries, and a **re-score** phase that explores the weight grid over those persisted windows.

The re-score phase MUST NOT call an embedding provider and MUST NOT query the database. Two re-score runs over the same persisted windows with the same grid MUST produce identical results.

Each persisted window MUST record the fusion configuration it was captured under, and the re-score phase MUST refuse windows whose recorded fusion configuration does not match the one being calibrated.

#### Scenario: The re-score phase reaches no provider and no database
- **GIVEN** candidate windows captured under a frozen fusion configuration
- **WHEN** the weight grid is explored
- **THEN** no embedding provider call is made
- **AND** no database query is made

#### Scenario: Two sweeps over the same windows agree exactly
- **GIVEN** the same persisted windows and the same weight grid
- **WHEN** the sweep is run twice
- **THEN** the two runs produce identical metrics and identical orderings

#### Scenario: A window captured under a different fusion is refused
- **GIVEN** persisted windows recorded under one fusion configuration
- **WHEN** a re-score is attempted for a different fusion configuration
- **THEN** the run is refused
- **AND** the mismatch is reported rather than silently re-scored

### Requirement: The ranking stage is observable and its signals are logged without exact quantities
The stage that applies business signals MUST log, with the request trace identifier, the weights in force, whether a reading scope was applied, how many candidates it reordered, and how many candidates carried absent signals. It MUST NOT log an exact stock quantity and MUST NOT log any embedding vector.

#### Scenario: The ranking stage logs its weights and its effect
- **WHEN** the business-signals stage runs
- **THEN** it logs the weights in force and the number of candidates it reordered
- **AND** the entry carries the request trace identifier

#### Scenario: No quantity and no vector reaches the logs
- **WHEN** the business-signals stage logs
- **THEN** no exact stock quantity appears in the entry
- **AND** no embedding vector appears in the entry

### Requirement: Ranking tests run offline
Tests for this capability MUST run without calling an embedding provider, a language model provider or a remote database, and MUST NOT read schema `public` by SQL. Database-backed tests MUST use an ephemeral PostgreSQL with pgvector and skip when it is unreachable.

#### Scenario: The offline suite makes no external call
- **GIVEN** the ranking test suite
- **WHEN** it runs without credentials configured
- **THEN** it passes
- **AND** no provider call, no network call and no query against schema `public` is made
