# ai-service-runtime Specification

## MODIFIED Requirements

### Requirement: Service exposes public health with version

The `jbg-ai` service SHALL expose `GET /health` without authentication. The response MUST be HTTP 200 when the process is running and MUST include an OK status indicator and the configured service version (`SERVICE_VERSION`).

The response MUST additionally report database reachability, the state of the vector index, and whether the embedding provider credential is configured. The endpoint MUST NOT call the embedding or LLM provider: the provider field reports **configuration presence only**, never provider reachability. A third-party outage MUST NOT be able to make this endpoint fail.

The reported state MUST be cached for a short window so that repeated probing does not consume the capped database connection pool.

The handler's return annotation MUST remain an open mapping and no new route may be introduced by this requirement, so that the versioned OpenAPI snapshot is unaffected.

#### Scenario: Health returns OK with version

- **WHEN** the service is running with required configuration present
- **AND** a client calls `GET /health`
- **THEN** the response status is 200
- **AND** the body indicates OK status
- **AND** the body includes the configured service version

#### Scenario: Health does not require authentication

- **WHEN** a client calls `GET /health` without any auth token
- **THEN** the request is accepted (not rejected for missing credentials)

#### Scenario: Health reports database, index and provider configuration

- **GIVEN** the service is configured with a database and an embedding provider credential
- **WHEN** a client calls `GET /health`
- **THEN** the body reports the database as reachable
- **AND** the body reports the number of indexed documents
- **AND** the body reports the provider credential as configured

#### Scenario: Health reports a missing provider credential without failing

- **GIVEN** no embedding provider credential is configured
- **WHEN** a client calls `GET /health`
- **THEN** the response status is 200
- **AND** the body reports the provider credential as missing

#### Scenario: Health never calls the provider

- **GIVEN** the embedding provider is unreachable or returning errors
- **WHEN** a client calls `GET /health`
- **THEN** the response status is 200
- **AND** no request is issued to the embedding or LLM provider
- **AND** the provider field still reports whether the credential is configured

#### Scenario: Health degrades when the database is unreachable

- **GIVEN** the database cannot be reached
- **WHEN** a client calls `GET /health`
- **THEN** the body reports the database as unavailable
- **AND** the overall status indicates degradation
- **AND** the endpoint still responds rather than raising

#### Scenario: Health state is cached between probes

- **GIVEN** a client calls `GET /health` twice within the cache window
- **WHEN** the second call is served
- **THEN** the database is not probed a second time
- **AND** the vector index is not queried a second time

#### Scenario: Enriched health does not move the frozen contract

- **WHEN** the versioned OpenAPI snapshot is regenerated from the canonical settings profile
- **THEN** it is byte-identical to the committed snapshot
- **AND** the `/health` operation still declares an open object response

## ADDED Requirements

### Requirement: Health detects a configured embedding model that disagrees with the index

The `jbg-ai` service SHALL compare the configured embedding model against the model recorded on the rows of the vector index, and report a mismatch state when they differ. Querying with a model other than the one that produced the indexed vectors compares two different vector spaces and returns meaningless results with no error, so this condition MUST be surfaced explicitly rather than inferred.

The comparison MUST use the model already persisted per row by the indexer; it MUST NOT require new schema.

#### Scenario: Matching model reports a healthy index

- **GIVEN** the vector index was populated with a given embedding model
- **AND** the service is configured with that same model
- **WHEN** a client calls `GET /health`
- **THEN** the index state is reported as consistent
- **AND** the reported index model equals the configured model

#### Scenario: Mismatched model is reported explicitly

- **GIVEN** the vector index was populated with one embedding model
- **AND** the service is configured with a different embedding model
- **WHEN** a client calls `GET /health`
- **THEN** the index state is reported as a model mismatch
- **AND** the body names both the indexed model and the configured model
- **AND** the overall status indicates degradation

#### Scenario: An empty index is not reported as a mismatch

- **GIVEN** the vector index contains no documents
- **WHEN** a client calls `GET /health`
- **THEN** the reported document count is zero
- **AND** the index state is not reported as a model mismatch
