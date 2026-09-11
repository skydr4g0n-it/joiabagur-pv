## MODIFIED Requirements

### Requirement: Availability demotes a candidate and never removes it

A candidate whose projection row reports `qty_bucket` of `0` MUST be ordered after otherwise comparable candidates and MUST remain inside the over-retrieval window. The demotion MUST rank below every block produced by a constraint read from the query text, so a constraint the operator expressed outranks a signal they did not ask for.

**The demotion is applied as a weighted score within the last block of the ordering, not as a component of the lexicographic key.** The weight MUST be configuration and MUST be calibrated against the golden set under the operational metric and the relevance guardrail that the business-signals ranking capability defines; setting it to zero MUST reproduce the order that the fusion and the typed-constraint blocks alone produce. A candidate whose projection row is absent — because the query ran without a reading scope, or because that point of sale does not carry the product — MUST NOT be demoted, since an absent signal is not evidence of zero stock.

The distinction MUST remain binary between `0` and any other bucket; `1-2` and `3+` MUST NOT be ordered against each other. **That is now a measured conclusion rather than a deferral:** under the operational metric neither non-zero bucket loses gain, so no objective function can order them, and the two business readings of the distinction point in opposite directions. The report MUST publish the distribution of the two non-zero buckets so the decision rests on a figure.

No stock value may reach the response as an exact quantity.

#### Scenario: An out-of-stock product is demoted, not removed

- **GIVEN** a point of sale holding both in-stock and zero-stock assigned products that match a query
- **WHEN** a product retrieval is served
- **THEN** the zero-stock products are still present among the results
- **AND** they are ordered after comparable in-stock products
- **AND** removing them from the response never occurs

#### Scenario: A typed constraint outranks the stock signal

- **GIVEN** a query expressing a price ceiling and results that differ in both price and stock
- **WHEN** the candidates are ordered
- **THEN** candidates within the ceiling precede candidates above it regardless of their stock
- **AND** stock decides the order only between candidates that the typed constraints rank equally

#### Scenario: The two non-zero buckets are not ordered against each other

- **GIVEN** two candidates whose buckets are `1-2` and `3+` and which the other blocks rank equally
- **WHEN** the candidates are ordered
- **THEN** their relative order is the one the fusion produced

#### Scenario: The distribution of the two non-zero buckets is published

- **WHEN** the calibration report completes
- **THEN** it states how many assigned pairs carry `1-2` and how many carry `3+`
- **AND** cites that figure as the reason the distinction stays binary

#### Scenario: The availability weight is configuration and zero restores the previous order

- **WHEN** the availability weight is set to zero
- **THEN** the order is the one the fusion and the typed-constraint blocks alone produce
- **AND** no weight value is written into the ordering module

#### Scenario: An absent projection row does not demote

- **GIVEN** a candidate for which no projection row is read, because the query ran without a reading scope
- **WHEN** the candidates are ordered
- **THEN** that candidate is not demoted on availability grounds
- **AND** the absence is not treated as a bucket of zero

### Requirement: Sales aggregates are stored by this capability and read by none of it

The projection SHALL persist `sales_30d`, `sales_90d`, `last_sale_at` and the reference instant reported by the feed. The reference instant MUST be stored **on each row** so a later consumer can tell what clock produced that row's figures. Storing it once per synchronisation instead is insufficient, because the feed is incremental: a pair the feed does not re-emit keeps the figures the run that wrote it computed, so one projection can hold rows counted against different instants.

**`sales_30d` MAY now be read by the ranking that this capability feeds**, as the last ordering key and under a declared weight, as the business-signals ranking capability defines. When it is read, it MUST be read against the reference instant recorded on that row and never against the wall clock, so that the same configuration yields the same order on different days. `sales_90d` and `last_sale_at` remain persisted and unread: no ordering rule may consume them.

This capability itself MUST NOT use any of these figures to order, filter or score candidates; the ordering that consumes `sales_30d` belongs to the ranking capability, not to the drain.

#### Scenario: Sales figures are persisted with their reference instant

- **GIVEN** the drain writes a projection row
- **WHEN** the row is inspected
- **THEN** it carries its sales windows, its last sale instant and the reference instant the feed reported

#### Scenario: The unread figures stay unread

- **GIVEN** two assigned candidates identical except for their `sales_90d` and `last_sale_at`
- **WHEN** a product retrieval is served
- **THEN** their relative order is the one produced by fusion, the demotion blocks and `sales_30d`
- **AND** no ordering rule consumed `sales_90d` or `last_sale_at`

#### Scenario: The drain does not order anything

- **WHEN** the drain runs
- **THEN** it writes the projection and computes no ranking
- **AND** no ordering decision is taken inside this capability

#### Scenario: The sales window is read against the row's reference instant

- **GIVEN** a projection whose rows carry a reference instant earlier than today
- **WHEN** the ranking reads `sales_30d`
- **THEN** the window is counted against that instant
- **AND** the figure is unchanged when the same configuration runs on a later day
