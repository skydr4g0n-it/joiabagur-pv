"""Domain routers for the frozen `/v1` surface."""

from jbg_ai.api.routers import assist, enrich, evals, index, inventory, retrieval

#: Mounted on every profile. `evals` is added separately, development only.
DOMAIN_ROUTERS = (
    retrieval.router,
    assist.router,
    inventory.router,
    enrich.router,
    index.router,
)

__all__ = ["DOMAIN_ROUTERS", "assist", "enrich", "evals", "index", "inventory", "retrieval"]
