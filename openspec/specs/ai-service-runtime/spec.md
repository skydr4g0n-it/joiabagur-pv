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
On startup, `jbg-ai` MUST load settings via pydantic-settings. `APP_ENV` and `SERVICE_VERSION` MUST be required. If either is missing or empty, the process MUST fail immediately with a clear error and MUST NOT continue serving requests. `LOG_LEVEL` MAY default to `INFO`.

#### Scenario: Missing required env aborts startup
- **WHEN** `APP_ENV` or `SERVICE_VERSION` is missing
- **AND** settings are loaded (application boot or settings factory)
- **THEN** loading fails with an error identifying the missing setting
- **AND** the service does not remain listening in a half-started state

#### Scenario: Valid minimal env allows boot
- **WHEN** `APP_ENV` and `SERVICE_VERSION` are set
- **AND** optional `LOG_LEVEL` is omitted
- **THEN** settings load successfully
- **AND** the service can serve `GET /health`

### Requirement: Structured logging includes trace_id
Each HTTP request MUST be associated with a `trace_id`. If the request includes header `X-Trace-Id`, that value MUST be used; otherwise the service MUST generate a UUID. Structured logs for that request MUST include `trace_id`. The service SHOULD return the `trace_id` on the response (e.g. `X-Trace-Id` header).

#### Scenario: Incoming trace id is preserved
- **WHEN** a client calls an endpoint with `X-Trace-Id` set to a known value
- **THEN** structured logs for that request include the same `trace_id`
- **AND** the response includes that `trace_id` (header or documented field)

#### Scenario: Missing trace id is generated
- **WHEN** a client calls an endpoint without `X-Trace-Id`
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
