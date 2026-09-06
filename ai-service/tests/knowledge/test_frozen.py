"""Guards on what C23 promised not to touch. Delivered by C23.

`indexing/embeddings.py` says it in its own docstring — *«C23 reuses this module and must
not edit it»* — and a docstring is not a check. The hash is.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from support.paths import AI_SERVICE_ROOT, OPENAPI_SNAPSHOT

#: SHA-256 of `indexing/embeddings.py` as C11 left it and C22 last touched it, over the
#: text with newlines normalised — the file is checked out with CRLF on Windows and LF on
#: Linux, and a guard that failed on the checkout would be noise rather than a guard.
#:
#: **If this test fails, do not update the constant to make it pass.** It means an edit
#: reached a module this change declared frozen. Updating the number belongs to a change
#: that owns that module and says so in its proposal.
EMBEDDINGS_SHA256 = "ee6484c6281539a62158a81e3b902ee52951449ab33ac3f4d419516346101c05"

FROZEN_BY_DECLARATION = (
    "src/jbg_ai/indexing/embeddings.py",
    "src/jbg_ai/enrichment/vocabularies.yaml",
    "src/jbg_ai/retrieval/orchestrator.py",
    "src/jbg_ai/retrieval/search.py",
)


def _normalised(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_embeddings_module_is_untouched() -> None:
    digest = hashlib.sha256(
        _normalised(AI_SERVICE_ROOT / "src/jbg_ai/indexing/embeddings.py").encode("utf-8")
    ).hexdigest()
    assert digest == EMBEDDINGS_SHA256, (
        "indexing/embeddings.py has been edited. C11 froze it and its docstring names C23 "
        "as a consumer that must not modify it; reuse it instead."
    )


def test_the_frozen_files_still_exist_where_the_guard_looks() -> None:
    """A guard that silently stops guarding is worse than no guard."""
    for relative in FROZEN_BY_DECLARATION:
        assert (AI_SERVICE_ROOT / relative).is_file(), relative


def test_knowledge_opens_no_http_surface() -> None:
    """The `/v1` surface is frozen by a MUST that enumerates ten routes."""
    snapshot = _normalised(OPENAPI_SNAPSHOT)
    assert "knowledge" not in snapshot.casefold()


def test_the_knowledge_package_contains_no_ddl() -> None:
    """Zero migrations: everything a field would need lives in `metadata jsonb`."""
    forbidden = ("create table", "alter table", "drop table", "create index", "add column")
    for path in (AI_SERVICE_ROOT / "src/jbg_ai/knowledge").rglob("*.py"):
        lowered = _normalised(path).casefold()
        for statement in forbidden:
            assert statement not in lowered, f"{path.name} contains `{statement}`"
