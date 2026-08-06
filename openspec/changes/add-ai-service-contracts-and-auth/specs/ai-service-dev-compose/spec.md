## ADDED Requirements

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
