"""Valid sample requests and declared response models for the frozen `/v1` surface."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from jbg_ai.api.schemas.assist import AssistResponse
from jbg_ai.api.schemas.enrich import EnrichResponse
from jbg_ai.api.schemas.evals import EvalRunsResponse
from jbg_ai.api.schemas.index import IndexStatusResponse, IndexSyncResponse
from jbg_ai.api.schemas.inventory import InventoryProposeResponse
from jbg_ai.api.schemas.retrieval import RetrievalResponse, SubstitutesResponse

#: (method, path, body) for every frozen endpoint, in contract order.
V1_REQUESTS: list[tuple[str, str, dict[str, Any] | None]] = [
    ("POST", "/v1/retrieval/products", {"query": "anillo de plata", "top_k": 2}),
    ("POST", "/v1/retrieval/substitutes", {"product_id": "P-0001", "top_k": 2}),
    ("POST", "/v1/assist/sale", {"query": "regalo para mi madre", "top_k": 2}),
    ("POST", "/v1/inventory/propose", {"horizon_days": 30, "limit": 3}),
    (
        "POST",
        "/v1/enrich/products",
        {"products": [{"product_id": "P-0001", "sku": "JBG-0001", "name": "Anillo"}]},
    ),
    ("POST", "/v1/index/sync", {"full": True}),
    ("GET", "/v1/index/status", None),
    ("GET", "/v1/evals/runs", None),
]

RESPONSE_MODELS: dict[str, type[BaseModel]] = {
    "/v1/retrieval/products": RetrievalResponse,
    "/v1/retrieval/substitutes": SubstitutesResponse,
    "/v1/assist/sale": AssistResponse,
    "/v1/inventory/propose": InventoryProposeResponse,
    "/v1/enrich/products": EnrichResponse,
    "/v1/index/sync": IndexSyncResponse,
    "/v1/index/status": IndexStatusResponse,
    "/v1/evals/runs": EvalRunsResponse,
}
