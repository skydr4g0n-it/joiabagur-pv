# ai-service-dev-compose Specification

## Purpose
Local Docker Compose wiring for `jbg-ai` on `jpv-network`, pgvector-ready Postgres 15 image, and developer runs that stay off production RDS.
## Requirements
### Requirement: jbg-ai service is defined on the local Compose network
`backend/docker-compose.yml` MUST define a `jbg-ai` service built from `ai-service/` (Dockerfile), attached to `jpv-network`. For local development, a host port MAY be published so `/health` is reachable from the host. Production nginx exposure is out of scope for this capability.

#### Scenario: Compose service joins shared network
- **WHEN** a developer runs Compose with the updated file
- **THEN** the `jbg-ai` container starts on `jpv-network`
- **AND** it can resolve other Compose services on that network by service name

#### Scenario: Local health reachable from host
- **WHEN** `jbg-ai` is up with published local port mapping
- **AND** a client calls `GET /health` via that host port
- **THEN** the response is HTTP 200 with OK status and version

### Requirement: Local Postgres image provides pgvector extension availability
The Compose Postgres service MUST use a PostgreSQL 15 image that ships the pgvector extension so that extension name `vector` appears in `pg_available_extensions` (or equivalent). This change MUST NOT require creating schema `ai` or executing `CREATE EXTENSION vector` as part of bringing Compose up.

#### Scenario: vector extension is available locally
- **WHEN** the Compose Postgres container is running on the pgvector-enabled image
- **AND** a SQL client queries available extensions for name `vector`
- **THEN** a matching row is returned
- **AND** schema `ai` need not exist yet

#### Scenario: Extension is not auto-created by this change
- **WHEN** Compose is started after this change alone
- **THEN** the stack MUST NOT depend on `ai.*` tables existing
- **AND** application boot of `jbg-ai` MUST NOT require a database connection

### Requirement: Developers can run without production RDS
Local development and automated tests for this change MUST use Compose/local process configuration only. Connection strings MUST NOT point developer laptops at production RDS as the default path.

#### Scenario: Default local config stays off production
- **WHEN** a developer follows the `ai-service` README for local run
- **THEN** documented `DATABASE_URL` / DB hosts refer to local Compose (or are omitted until a later change)
- **AND** production RDS is not required to start `jbg-ai` or pass C01 tests

### Requirement: Compose supplies the internal service credentials for local runs
The `jbg-ai` service in `backend/docker-compose.yml` MUST provide every environment variable the service requires to boot, including `JWT_SECRET` and `STUB_MODE`, so the container starts locally without extra manual setup. The Compose secret is a development-only placeholder and MUST NOT be reused in production, where the value is supplied by the parameter store. `STUB_MODE` MUST be enabled for local runs so no external AI provider or database is needed. The `ai-service` README MUST document the required environment variables and their defaults.

#### Scenario: Local container boots with Compose-provided environment
- **WHEN** a developer runs Compose with the updated file and no extra environment overrides
- **THEN** the `jbg-ai` container starts without failing settings validation
- **AND** `GET /health` answers HTTP 200 through the published local port

#### Scenario: Missing secret fails fast rather than serving half-configured
- **WHEN** the `jbg-ai` Compose service is started without `JWT_SECRET`
- **THEN** the container exits with an error naming the missing variable
- **AND** it does not serve authenticated routes

#### Scenario: Local runs need no AI provider or database
- **WHEN** the Compose stack is started with the documented local environment
- **THEN** `jbg-ai` serves its `/v1` routes from stubs
- **AND** no LLM provider credentials or database connection are required
