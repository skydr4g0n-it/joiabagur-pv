"""Bounded LRU embedding cache for the retrieval singleton. Delivered by C21.

`openspec/DEFERRED_TASKS.md` describes making the retrieval embedding client a process
singleton as "roughly three lines in `main.py`". It is not, and the missing part is this file.

`indexing.embeddings.InMemoryEmbeddingCache` is a plain `dict` with **no ceiling and no TTL**.
Per request that is harmless — it is born empty and dies with the response, which is also why
retrieval never once got a cache hit. As a **process singleton** it becomes a lifetime leak
keyed by every distinct operator query, at roughly 13 KB per 1536-float vector, inside a
container capped at 512 MiB that already uses 232.

`indexing/embeddings.py` is frozen by C11 and is **not edited**: `LiteLlmEmbeddingClient`
already takes `cache` as a constructor field, so the bound is injected through the seam that
exists rather than by unfreezing the module. This class satisfies the same duck-typed
interface — `get(text, model, version)` and `put(text, model, version, vector)`.
"""

from __future__ import annotations

from collections import OrderedDict

from jbg_ai.indexing.source_text import hash_source_text

#: 512 entries is roughly 6,5 MiB of vectors — under 3 % of the container's 512 MiB cap, and
#: far more distinct queries than one point of sale types in a day. The ceiling exists to bound
#: the worst case, not to be tuned: an operator repeating a query within a session is what the
#: cache is for, and that working set is tiny.
DEFAULT_MAX_ENTRIES = 512


class BoundedEmbeddingCache:
    """Least-recently-used cache with a hard ceiling. Same interface as the C11 cache."""

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self.max_entries = max_entries
        self._store: OrderedDict[tuple[str, str, str], list[float]] = OrderedDict()

    def __len__(self) -> int:
        return len(self._store)

    def get(self, text: str, model: str, version: str) -> list[float] | None:
        key = (hash_source_text(text), model, version)
        vector = self._store.get(key)
        if vector is not None:
            self._store.move_to_end(key)
        return vector

    def put(self, text: str, model: str, version: str, vector: list[float]) -> None:
        key = (hash_source_text(text), model, version)
        self._store[key] = vector
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            # Evict rather than grow: a singleton that never forgets is the leak this exists
            # to prevent, and the cost of a miss is one provider round trip.
            self._store.popitem(last=False)
