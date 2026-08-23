"""Load the shared local `.env` next to docker-compose (never print values)."""

from __future__ import annotations

from pathlib import Path

from jbg_ai.data.paths import AI_SERVICE_ROOT, REPO_ROOT

# Same file Compose uses for ${VAR} interpolation when run from backend/.
_CANDIDATES = (
    REPO_ROOT / "backend" / ".env",
    REPO_ROOT / ".env",
    AI_SERVICE_ROOT / ".env",
)


def local_env_paths() -> tuple[Path, ...]:
    return _CANDIDATES


def load_local_env() -> Path | None:
    """Load the first existing local env file. Existing process env wins."""
    from dotenv import load_dotenv

    for path in _CANDIDATES:
        if path.is_file():
            load_dotenv(path, override=False)
            return path
    return None
