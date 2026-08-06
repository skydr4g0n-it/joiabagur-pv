## MODIFIED Requirements

### Requirement: Settings fail fast on missing required environment
On startup, `jbg-ai` MUST load settings via pydantic-settings. `APP_ENV`, `SERVICE_VERSION` and `JWT_SECRET` MUST be required. If any of them is missing or empty, the process MUST fail immediately with a clear error identifying the missing setting and MUST NOT continue serving requests. `LOG_LEVEL` MAY default to `INFO`. `JWT_TTL_SECONDS` MAY default to `300`. `STUB_MODE` MAY default to `true`. `ENABLE_DEV_ENDPOINTS` MAY default from `APP_ENV`, resolving to false under a production profile.

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
