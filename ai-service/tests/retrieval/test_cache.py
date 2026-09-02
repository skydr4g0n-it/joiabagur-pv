"""The bounded cache the singleton needs, and the C11 freeze it must not break. C21."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from jbg_ai.indexing.embeddings import InMemoryEmbeddingCache, LiteLlmEmbeddingClient
from jbg_ai.retrieval.cache import DEFAULT_MAX_ENTRIES, BoundedEmbeddingCache

MODEL = "openai/text-embedding-3-small"
VERSION = f"{MODEL}:1536:v1"

#: sha256 of `src/jbg_ai/indexing/embeddings.py`, read as text so line endings do not matter.
#: C11 froze that module and C13, C14, C18 and C23 all reuse it without editing it; C21 pays
#: the singleton debt through its existing `cache` constructor field instead. Updating this
#: constant is a deliberate act that means the freeze has been lifted on purpose — it is not
#: the way to make a failing test pass.
FROZEN_EMBEDDINGS_SHA256 = "ee6484c6281539a62158a81e3b902ee52951449ab33ac3f4d419516346101c05"


def _vector(seed: int) -> list[float]:
    return [float(seed)] * 4


def test_embedding_cache_is_bounded() -> None:
    """Inserting more entries than the ceiling evicts rather than grows."""
    cache = BoundedEmbeddingCache(max_entries=3)
    for index in range(10):
        cache.put(f"query-{index}", MODEL, VERSION, _vector(index))

    assert len(cache) == 3
    assert cache.get("query-0", MODEL, VERSION) is None
    assert cache.get("query-9", MODEL, VERSION) == _vector(9)


def test_the_least_recently_used_entry_is_the_one_evicted() -> None:
    cache = BoundedEmbeddingCache(max_entries=2)
    cache.put("a", MODEL, VERSION, _vector(1))
    cache.put("b", MODEL, VERSION, _vector(2))
    assert cache.get("a", MODEL, VERSION) == _vector(1)

    cache.put("c", MODEL, VERSION, _vector(3))

    assert cache.get("a", MODEL, VERSION) == _vector(1), "reading it kept it alive"
    assert cache.get("b", MODEL, VERSION) is None
    assert cache.get("c", MODEL, VERSION) == _vector(3)


def test_the_cache_is_keyed_by_text_model_and_version() -> None:
    cache = BoundedEmbeddingCache()
    cache.put("anillo", MODEL, VERSION, _vector(1))

    assert cache.get("anillo", MODEL, VERSION) == _vector(1)
    assert cache.get("anillo", "other/model", VERSION) is None
    assert cache.get("anillo", MODEL, "other:version") is None
    assert cache.get("collar", MODEL, VERSION) is None


def test_a_ceiling_below_one_is_refused() -> None:
    with pytest.raises(ValueError, match="max_entries"):
        BoundedEmbeddingCache(max_entries=0)


def test_the_default_ceiling_is_small_enough_for_a_512_mib_container() -> None:
    megabytes = DEFAULT_MAX_ENTRIES * 1536 * 8 / (1024 * 1024)

    assert DEFAULT_MAX_ENTRIES > 0
    assert megabytes < 32, "the whole point is that the singleton cannot grow without bound"


def test_the_bounded_cache_satisfies_the_c11_interface() -> None:
    """It is injected through the constructor seam, so the frozen module keeps a zero diff."""
    bounded = BoundedEmbeddingCache(max_entries=4)
    client = LiteLlmEmbeddingClient(api_key="sk-test", cache=bounded)

    assert client.cache is bounded
    for name in ("get", "put"):
        assert callable(getattr(bounded, name))
        assert callable(getattr(InMemoryEmbeddingCache(), name))


def test_embeddings_module_is_unchanged() -> None:
    """C11 froze `indexing/embeddings.py`; C21 injects a bound instead of editing it."""
    source = Path(__file__).resolve().parents[2] / "src" / "jbg_ai" / "indexing" / "embeddings.py"
    digest = hashlib.sha256(source.read_text(encoding="utf-8").encode("utf-8")).hexdigest()

    assert digest == FROZEN_EMBEDDINGS_SHA256, (
        "indexing/embeddings.py has been frozen since C11 and C21 must not edit it: the "
        "bounded cache belongs in retrieval/cache.py and travels through the existing "
        "`cache` constructor field. Update this hash only when the freeze is lifted on "
        "purpose, in a change that says so."
    )
    text = source.read_text(encoding="utf-8")
    assert "BoundedEmbeddingCache" not in text
    assert "max_entries" not in text
