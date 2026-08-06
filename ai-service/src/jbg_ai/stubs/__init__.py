"""Deterministic fixtures served while `STUB_MODE` is enabled.

Every builder is a pure function of its input: no clock, no randomness, no I/O.
The .NET client builds its mapping tests against these responses, so the same
request must always produce the same body.
"""

from jbg_ai.stubs.responses import (
    OVER_RETRIEVAL_CAP,
    OVER_RETRIEVAL_FACTOR,
    assist_sale_stub,
    enrich_products_stub,
    evals_runs_stub,
    index_status_stub,
    index_sync_stub,
    inventory_propose_stub,
    over_retrieval_count,
    retrieval_products_stub,
    retrieval_substitutes_stub,
)

__all__ = [
    "OVER_RETRIEVAL_CAP",
    "OVER_RETRIEVAL_FACTOR",
    "assist_sale_stub",
    "enrich_products_stub",
    "evals_runs_stub",
    "index_status_stub",
    "index_sync_stub",
    "inventory_propose_stub",
    "over_retrieval_count",
    "retrieval_products_stub",
    "retrieval_substitutes_stub",
]
