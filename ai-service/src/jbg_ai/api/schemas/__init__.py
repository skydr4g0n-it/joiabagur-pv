"""Frozen request/response contracts for the `/v1` surface (C02).

Any change here breaks `ai-service/openapi.json` on purpose: the snapshot test
turns contract drift into an explicit negotiation with the .NET side.
"""

from jbg_ai.api.schemas.assist import (
    AssistContext,
    AssistGroup,
    AssistGroupMember,
    AssistRequest,
    AssistResponse,
    Citation,
)
from jbg_ai.api.schemas.common import (
    PRICE_PLACEHOLDER,
    STOCK_PLACEHOLDER,
    DebugInfo,
    ScopedResponse,
    TracedResponse,
    Usage,
)
from jbg_ai.api.schemas.enrich import (
    EnrichProductInput,
    EnrichRequest,
    EnrichResponse,
    ProposedList,
    ProposedProfile,
    ProposedText,
)
from jbg_ai.api.schemas.evals import EvalMetric, EvalRun, EvalRunsResponse
from jbg_ai.api.schemas.index import (
    IndexStatusResponse,
    IndexSyncRequest,
    IndexSyncResponse,
)
from jbg_ai.api.schemas.inventory import (
    InventoryFilters,
    InventoryProposal,
    InventoryProposeRequest,
    InventoryProposeResponse,
)
from jbg_ai.api.schemas.retrieval import (
    RetrievalFilters,
    RetrievalMode,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
    SimilaritySignals,
    SubstituteResult,
    SubstitutesRequest,
    SubstitutesResponse,
)

__all__ = [
    "PRICE_PLACEHOLDER",
    "STOCK_PLACEHOLDER",
    "AssistContext",
    "AssistGroup",
    "AssistGroupMember",
    "AssistRequest",
    "AssistResponse",
    "Citation",
    "DebugInfo",
    "EnrichProductInput",
    "EnrichRequest",
    "EnrichResponse",
    "EvalMetric",
    "EvalRun",
    "EvalRunsResponse",
    "IndexStatusResponse",
    "IndexSyncRequest",
    "IndexSyncResponse",
    "InventoryFilters",
    "InventoryProposal",
    "InventoryProposeRequest",
    "InventoryProposeResponse",
    "ProposedList",
    "ProposedProfile",
    "ProposedText",
    "RetrievalFilters",
    "RetrievalMode",
    "RetrievalRequest",
    "RetrievalResponse",
    "RetrievalResult",
    "ScopedResponse",
    "SimilaritySignals",
    "SubstituteResult",
    "SubstitutesRequest",
    "SubstitutesResponse",
    "TracedResponse",
    "Usage",
]
