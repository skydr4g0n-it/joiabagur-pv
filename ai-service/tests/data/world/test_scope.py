"""World suite stays offline and does not import data from api.main."""

from __future__ import annotations

from pathlib import Path

from jbg_ai.api import main as api_main
from support.paths import AI_SERVICE_ROOT


def test_unit_suite_makes_no_provider_calls(forbid_network: None) -> None:
    _ = forbid_network
    source = Path(api_main.__file__).read_text(encoding="utf-8")
    assert "jbg_ai.data" not in source
    assert not (AI_SERVICE_ROOT / "src" / "jbg_ai" / "api" / "main.py").read_text(
        encoding="utf-8"
    ).__contains__("jbg_ai.data")
