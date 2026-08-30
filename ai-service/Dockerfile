# jbg-ai — Python FastAPI service (C01, hardened by C17)
#
# Three properties are deliberate, and each one prevents a failure that has a
# name:
#
#   * **Multi-stage.** The dependency installer and the build backend never
#     reach the runtime image, so nothing that resolved the lock file is
#     available to anything that later runs in the container.
#   * **Pinned installer.** `ghcr.io/astral-sh/uv:latest` used to sit here, and
#     a moving tag means the same commit builds a different image depending on
#     the day. Bump this deliberately, in a commit, like any other dependency.
#   * **Non-root.** The process that holds the embedding provider credential
#     does not need to be able to write to its own image.
#
# Context: `ai-service/` (not the repository root). The root `.dockerignore`
# does not apply here; this directory has its own.

# ─── Stage 1: Resolve the locked dependency tree ─────────────────────────────
FROM python:3.11-slim-bookworm AS build

# Pinned on purpose. See the header: a moving tag is a reproducibility defect,
# not a convenience.
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# `--no-editable` installs jbg_ai into the virtual environment, so `src/` does
# not have to travel to the runtime stage.
RUN uv sync --frozen --no-dev --no-editable

# ─── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS final

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Created before the copies so every artefact lands already owned by the user
# that will run the process.
RUN groupadd --system appuser && useradd --system --gid appuser --home-dir /app appuser

COPY --from=build --chown=appuser:appuser /app/.venv ./.venv

# Migrations ship with the image so the deployment can run `alembic upgrade head`
# from the container itself (C17). Copied after the virtual environment on
# purpose: editing a revision must not invalidate the dependency layer.
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser migrations ./migrations
COPY --chown=appuser:appuser prompts ./prompts

USER appuser

EXPOSE 8000

# The interpreter is already in the image; installing an HTTP client just to
# probe a local port would add a package, a layer and an attack surface for a
# single GET. `/health` is public and cheap by contract, and it never calls the
# embedding or LLM provider, so a third-party outage cannot mark this container
# unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"]

CMD ["uvicorn", "jbg_ai.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
