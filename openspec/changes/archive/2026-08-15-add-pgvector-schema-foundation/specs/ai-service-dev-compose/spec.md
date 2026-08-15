## MODIFIED Requirements

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
