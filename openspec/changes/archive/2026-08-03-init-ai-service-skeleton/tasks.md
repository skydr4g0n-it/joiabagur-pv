## 1. Python package scaffold

- [x] 1.1 Create `ai-service/` with `uv`/`pyproject.toml`, src-layout package `jbg_ai`, and runtime deps (FastAPI, pydantic-settings, uvicorn)
- [x] 1.2 Add `src/jbg_ai/config/settings.py` requiring `APP_ENV` and `SERVICE_VERSION`, with optional `LOG_LEVEL` defaulting to `INFO`
- [x] 1.3 Add `src/jbg_ai/api/main.py` FastAPI app factory wiring settings and `GET /health` (OK + version, no auth)

## 2. Observability

- [x] 2.1 Add request middleware that reads `X-Trace-Id` or generates a UUID and binds `trace_id` into structured logs
- [x] 2.2 Echo `trace_id` on the response (`X-Trace-Id` header)

## 3. Tests

- [x] 3.1 Add pytest + httpx/`TestClient` test deps and `tests/` layout
- [x] 3.2 Implement `test_health_returns_ok_with_version`
- [x] 3.3 Implement `test_settings_fail_fast_when_required_env_missing`
- [x] 3.4 Ensure tests set required env in-process and never call LLM/embeddings/RDS

## 4. Container and Compose

- [x] 4.1 Add `ai-service/Dockerfile` that installs deps with `uv` and runs the ASGI app
- [x] 4.2 Add `jbg-ai` service to `backend/docker-compose.yml` on `jpv-network` with required env and local port publish (e.g. `8001:8000`)
- [x] 4.3 Replace Compose Postgres image `postgres:15` with pgvector-enabled PG 15 image; do not create schema `ai` or run `CREATE EXTENSION`
- [x] 4.4 Document volume recreate caveat (`docker compose down -v`) if the image swap requires it

## 5. Documentation and verification

- [x] 5.1 Write `ai-service/README.md` covering `uv` run, Compose run, required env for C01, and explicit non-goals (no JWT, no DB client, no prod RDS)
- [x] 5.2 Run `uv run pytest` and confirm green; smoke `GET /health` via Compose when Docker is available
