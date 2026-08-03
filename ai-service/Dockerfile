# jbg-ai — Python FastAPI skeleton (C01)
FROM python:3.11-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-editable

EXPOSE 8000

CMD ["uvicorn", "jbg_ai.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
