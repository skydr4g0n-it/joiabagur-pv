## MODIFIED Requirements

### Requirement: Inventory, enrichment and index contracts are frozen
`POST /v1/inventory/propose` MUST return a prioritized list of proposals. `POST /v1/enrich/products` MUST accept a batch of products and return proposed profiles in which **every proposed value carries both its confidence and its provenance**, stated as `rule` when the value comes from a deterministic normalization and `inferred` when a model produced it. The proposed profile MUST carry `piece_type`, `stone_type` and `size_label` as individually proposed values, and MUST carry commercial tags split into `color_tags`, `style_tags` and `occasion_tags` rather than as a single flat list, matching the columns the vector index already declares. `materials` MUST be returned as a list. The response MUST report the prompt version that produced the batch. `POST /v1/index/sync` MUST accept a `since` cursor and return upsert counters. `GET /v1/index/status` MUST return `drift_count` and `last_full_sync_at`.

Provenance is not decoration: the consuming capability routes a sensitive field to human review when it is inferred and exempts it when it comes from a rule, so a contract without it makes that policy unimplementable.

#### Scenario: Inventory proposals are prioritized
- **WHEN** an authenticated client calls `POST /v1/inventory/propose` with a valid body in stub mode
- **THEN** the response validates against the inventory response model
- **AND** it contains a prioritized list of proposals

#### Scenario: Enrichment returns per-field confidence and provenance
- **WHEN** an authenticated client calls `POST /v1/enrich/products` with a batch of products in stub mode
- **THEN** the response returns one proposed profile per requested product
- **AND** each proposed field carries a confidence value
- **AND** each proposed field states whether its value is `rule` or `inferred`
- **AND** `materials` is returned as a list

#### Scenario: Enrichment returns the sensitive fields the review policy needs
- **WHEN** the same call is made
- **THEN** each proposed profile exposes `piece_type`, `stone_type` and `size_label` as proposed values, each nullable
- **AND** it exposes `color_tags`, `style_tags` and `occasion_tags` as separate lists
- **AND** it exposes no single flat `tags` list

#### Scenario: Enrichment reports the prompt version
- **WHEN** the same call is made
- **THEN** the response reports the version of the prompt that produced the batch

#### Scenario: Stub proposals exercise both provenances
- **WHEN** the enrichment stub answers a batch large enough to cover its fixture cycle
- **THEN** at least one sensitive field is returned as `inferred`
- **AND** at least one sensitive field is returned as `rule`
- **AND** the response remains deterministic for the same request

#### Scenario: Index sync and status expose counters and drift
- **WHEN** an authenticated client calls `POST /v1/index/sync` with a `since` cursor in stub mode
- **THEN** the response returns upsert counters
- **WHEN** the same client calls `GET /v1/index/status`
- **THEN** the response returns `drift_count` and `last_full_sync_at`
