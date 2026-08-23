"""Filesystem anchors for the C06b CLI.

Resolved from this file so callers do not count parent directories.
"""

from __future__ import annotations

from pathlib import Path

from jbg_ai.data.constants import JSONL_FILENAME, META_FILENAME, PROMPT_VERSION

#: `ai-service/src/jbg_ai/data/paths.py` → ai-service/
AI_SERVICE_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = AI_SERVICE_ROOT.parent

PROMPTS_DIR = AI_SERVICE_ROOT / "prompts"
PROMPT_MARKDOWN = PROMPTS_DIR / "catalog-synth" / "v3.md"
PROMPT_SCHEMA = PROMPTS_DIR / "catalog-synth" / "v3.schema.json"

REAL_JSONL = REPO_ROOT / "data" / "catalog" / "real" / "generated" / "catalog-real-enriched.jsonl"
SYNTHETIC_DIR = REPO_ROOT / "data" / "catalog" / "synthetic" / "generated"


def default_output_paths(directory: Path | None = None) -> tuple[Path, Path]:
    target = directory or SYNTHETIC_DIR
    return target / JSONL_FILENAME, target / META_FILENAME


def prompt_version_label() -> str:
    return PROMPT_VERSION
