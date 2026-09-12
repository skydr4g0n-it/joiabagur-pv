## MODIFIED Requirements

### Requirement: Real product retrieval replaces the stub when stub mode is off
When `STUB_MODE` is disabled, `POST /v1/retrieval/products` MUST run the vector retrieval pipeline and MUST return a body that validates against the frozen `RetrievalResponse` model. It MUST NOT return HTTP 501 naming a later change and MUST NOT return the C02 fixture cycle. When `STUB_MODE` is enabled, the existing C02 stub MUST remain the handler so committed contract tests stay green. `POST /v1/retrieval/substitutes` MUST NOT return 501 when stubs are off either; its behaviour is owned by `substitutes-retrieval`. The OpenAPI snapshot MUST NOT be regenerated. The products handler MUST be asynchronous.

#### Scenario: Stub mode keeps the C02 fixtures
- **GIVEN** `STUB_MODE` is enabled
- **WHEN** an authenticated client with `pos_id` calls `POST /v1/retrieval/products` with a valid body
- **THEN** the response is produced by the existing retrieval stub
- **AND** no embedding provider is called
- **AND** no database session is opened

#### Scenario: Real mode is not 501
- **GIVEN** `STUB_MODE` is disabled and retrieval dependencies are available
- **WHEN** an authenticated client with `pos_id` calls `POST /v1/retrieval/products` with a valid body
- **THEN** the response status is 200 or 503 according to index and dependency state
- **AND** the status is not 501 claiming the implementation has not arrived
- **AND** a 200 body validates against `RetrievalResponse`

#### Scenario: No retrieval route is left answering 501
- **GIVEN** `STUB_MODE` is disabled
- **WHEN** an authenticated client with `pos_id` calls `POST /v1/retrieval/substitutes`
- **THEN** the response status is not 501
- **AND** no message claims the implementation is delivered in a later change

#### Scenario: OpenAPI snapshot stays frozen
- **WHEN** `test_openapi_snapshot_is_stable` runs against this change
- **THEN** the live schema equals the committed `ai-service/openapi.json`
- **AND** the snapshot file has not been regenerated
