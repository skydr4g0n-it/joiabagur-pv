# ai-service-runtime Specification

## Purpose
Runnable `jbg-ai` process behavior: fail-fast settings, public health with version, structured logging with `trace_id`, and in-process smoke tests without external AI or production DB.
## Requirements
### Requirement: Service exposes public health with version
The `jbg-ai` service SHALL expose `GET /health` without authentication. The response MUST be HTTP 200 when the process is running and MUST include an OK status indicator and the configured service version (`SERVICE_VERSION`).

#### Scenario: Health returns OK with version
- **WHEN** the service is running with required configuration present
- **AND** a client calls `GET /health`
- **THEN** the response status is 200
- **AND** the body indicates OK status
- **AND** the body includes the configured service version

#### Scenario: Health does not require authentication
- **WHEN** a client calls `GET /health` without any auth token
- **THEN** the request is accepted (not rejected for missing credentials)

### Requirement: Settings fail fast on missing required environment
On startup, `jbg-ai` MUST load settings via pydantic-settings. `APP_ENV`, `SERVICE_VERSION` and `JWT_SECRET` MUST be required. If any of them is missing or empty, the process MUST fail immediately with a clear error identifying the missing setting and MUST NOT continue serving requests. `LOG_LEVEL` MAY default to `INFO`. `JWT_TTL_SECONDS` MAY default to `300`. `STUB_MODE` MAY default to `true`. `ENABLE_DEV_ENDPOINTS` MAY default from `APP_ENV`, resolving to false under a production profile. `DATABASE_URL` MUST be optional and MUST have no default; `DB_POOL_SIZE` MUST be optional and MAY default to `5`. Their absence MUST NOT prevent the process from starting or from serving the routes that do not use the database.

#### Scenario: Missing required env aborts startup
- **WHEN** `APP_ENV`, `SERVICE_VERSION` or `JWT_SECRET` is missing
- **AND** settings are loaded (application boot or settings factory)
- **THEN** loading fails with an error identifying the missing setting
- **AND** the service does not remain listening in a half-started state

#### Scenario: Empty signing secret aborts startup
- **WHEN** `JWT_SECRET` is present but empty or blank
- **AND** settings are loaded
- **THEN** loading fails with an error identifying `JWT_SECRET`
- **AND** no authenticated route is served

#### Scenario: Valid minimal env allows boot
- **WHEN** `APP_ENV`, `SERVICE_VERSION` and `JWT_SECRET` are set
- **AND** optional `LOG_LEVEL`, `JWT_TTL_SECONDS`, `STUB_MODE` and `ENABLE_DEV_ENDPOINTS` are omitted
- **THEN** settings load successfully with `JWT_TTL_SECONDS` at `300` and `STUB_MODE` enabled
- **AND** the service can serve `GET /health`

#### Scenario: Absent database configuration does not block startup
- **WHEN** `DATABASE_URL` and `DB_POOL_SIZE` are omitted
- **AND** the required settings are present
- **THEN** settings load successfully with `DB_POOL_SIZE` at `5`
- **AND** the service starts and serves `GET /health`
- **AND** the `/v1` routes answer without opening a database connection

#### Scenario: Database configuration is accepted when supplied
- **WHEN** `DATABASE_URL` is set to a PostgreSQL connection string
- **AND** settings are loaded
- **THEN** the value is available to the database layer
- **AND** no connection is opened as a side effect of loading settings

### Requirement: Structured logging includes trace_id
Each HTTP request MUST be associated with a `trace_id`. When a validated internal service token carries a `trace_id` claim, that value MUST be used. Otherwise, if the request includes header `X-Trace-Id`, that value MUST be used; otherwise the service MUST generate a UUID. Structured logs for that request MUST include `trace_id`. The service SHOULD return the `trace_id` on the response (e.g. `X-Trace-Id` header).

#### Scenario: Token claim takes precedence over the header
- **WHEN** an authenticated request carries a `trace_id` claim and a different `X-Trace-Id` header value
- **THEN** structured logs for that request include the claim value
- **AND** the response reports that same value

#### Scenario: Incoming trace id is preserved
- **WHEN** a client calls an endpoint with `X-Trace-Id` set to a known value and no token trace claim applies
- **THEN** structured logs for that request include the same `trace_id`
- **AND** the response includes that `trace_id` (header or documented field)

#### Scenario: Missing trace id is generated
- **WHEN** a client calls an endpoint without `X-Trace-Id` and no token trace claim applies
- **THEN** the service generates a non-empty `trace_id`
- **AND** structured logs for that request include the generated `trace_id`

### Requirement: Automated smoke tests without external AI or production DB
The `ai-service` test suite MUST verify health and settings fail-fast using FastAPI `TestClient` (or equivalent in-process client). Tests MUST NOT call real LLM providers, embedding APIs, or production RDS.

#### Scenario: Health test passes in process
- **WHEN** `test_health_returns_ok_with_version` runs with required env provided to the test process
- **THEN** the assertion on OK status and version succeeds without network calls to LLM or RDS

#### Scenario: Settings fail-fast test passes
- **WHEN** `test_settings_fail_fast_when_required_env_missing` runs without a required env var
- **THEN** the test expects and observes settings load failure
