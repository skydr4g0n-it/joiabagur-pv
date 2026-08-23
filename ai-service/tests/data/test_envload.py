"""Local env file discovery. Delivered by C06b."""

from __future__ import annotations

from jbg_ai.data.envload import local_env_paths
from jbg_ai.data.paths import REPO_ROOT


def test_local_env_prefers_backend_dotenv_next_to_compose() -> None:
    paths = local_env_paths()
    assert paths[0] == REPO_ROOT / "backend" / ".env"
    example = REPO_ROOT / "backend" / ".env.example"
    assert example.is_file()
    text = example.read_text(encoding="utf-8")
    assert "JPV_CATALOG_LLM_API_KEY" in text
    assert "JPV_RAG_LLM_API_KEY" in text
    assert "JPV_PGHOST" in text
