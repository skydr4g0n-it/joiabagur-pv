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
The Compose Postgres service MUST use a PostgreSQL 15 image that ships the pgvector extension so that extension name `vector` appears in `pg_available_extensions` (or equivalent). Bringing Compose up MUST NOT by itself create schema `ai` nor execute `CREATE EXTENSION vector`: provisioning the extension, the schema and the dedicated role is a privileged one-off step run by a developer or an administrator, and creating the tables is the job of the migrations. Starting the Compose stack MUST remain possible, and `jbg-ai` MUST remain able to boot, on a database where none of that provisioning has been done.

#### Scenario: vector extension is available locally
- **WHEN** the Compose Postgres container is running on the pgvector-enabled image
- **AND** a SQL client queries available extensions for name `vector`
- **THEN** a matching row is returned
- **AND** schema `ai` need not exist yet

#### Scenario: Compose start does not provision the extension or the schema
- **WHEN** the Compose stack is started against a fresh database volume and no provisioning step has been run
- **THEN** the extension is not installed and schema `ai` does not exist
- **AND** the stack MUST NOT depend on `ai.*` tables existing
- **AND** application boot of `jbg-ai` MUST NOT require a database connection

### Requirement: Developers can run without production RDS
Local development and automated tests MUST use Compose or local process configuration only. Connection strings MUST NOT point developer laptops at production RDS as the default path. The `jbg-ai` Compose service MUST supply a `DATABASE_URL` that resolves the Compose Postgres service by its network name and internal port, never a published host port and never a production host. Because the database connection is opened on demand, the presence of that variable MUST NOT make the container's start depend on the database being ready or provisioned. The `ai-service` README MUST document the one-off provisioning step and how to apply migrations locally.

#### Scenario: Default local config stays off production
- **WHEN** a developer follows the `ai-service` README for local run
- **THEN** documented `DATABASE_URL` and database hosts refer to local Compose
- **AND** production RDS is not required to start `jbg-ai` or to run the test suite

#### Scenario: Compose supplies a local database URL
- **WHEN** the `jbg-ai` Compose service is started with no extra environment overrides
- **THEN** `DATABASE_URL` is present and targets the Compose Postgres service by network name and internal port
- **AND** the container starts even if the database has not been provisioned yet
- **AND** `GET /health` answers HTTP 200 through the published local port

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
