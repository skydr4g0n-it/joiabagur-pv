## MODIFIED Requirements

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
