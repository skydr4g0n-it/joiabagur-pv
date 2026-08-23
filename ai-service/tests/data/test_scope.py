"""Scope guards: no HTTP import, no provider sockets. Delivered by C06b."""

from __future__ import annotations

import ast
from pathlib import Path

from jbg_ai.api import main as api_main
from jbg_ai.data.paths import PROMPT_MARKDOWN
from support.paths import AI_SERVICE_ROOT


def test_api_main_does_not_import_jbg_ai_data() -> None:
    source = Path(api_main.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("jbg_ai.data")
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("jbg_ai.data")


def test_unit_suite_makes_no_provider_calls(forbid_network: None) -> None:
    """Autouse fixture in this folder already patches sockets; this names the gate."""
    _ = forbid_network
    assert PROMPT_MARKDOWN.exists()
    assert not (AI_SERVICE_ROOT / "src" / "jbg_ai" / "api" / "main.py").read_text(
        encoding="utf-8"
    ).__contains__("jbg_ai.data")
