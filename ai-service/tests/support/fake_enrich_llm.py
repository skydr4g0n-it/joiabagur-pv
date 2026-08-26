"""Injectable enrichment LLM that never opens a socket. Delivered by C09."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from jbg_ai.api.schemas.enrich import EnrichProductInput
from jbg_ai.enrichment.schema import EnrichmentExtraction


class FakeEnrichLlm:
    model_id = "fake:c09"

    def __init__(
        self,
        responses: dict[str, EnrichmentExtraction] | None = None,
        default: EnrichmentExtraction | None = None,
        by_sku: Callable[[EnrichProductInput], EnrichmentExtraction] | None = None,
        delay: float = 0.0,
        errors: dict[str, Exception] | None = None,
    ) -> None:
        self.responses = responses or {}
        self.default = default or EnrichmentExtraction()
        self.by_sku = by_sku
        self.delay = delay
        self.errors = errors or {}
        self.calls: list[EnrichProductInput] = []
        self.in_flight = 0
        self.max_in_flight = 0
        self._lock = asyncio.Lock()

    async def extract(self, product: EnrichProductInput, prompt: str) -> EnrichmentExtraction:
        _ = prompt
        async with self._lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            self.calls.append(product)
        if self.delay:
            await asyncio.sleep(self.delay)
        try:
            if product.sku in self.errors:
                raise self.errors[product.sku]
            if self.by_sku is not None:
                return self.by_sku(product)
            return self.responses.get(product.sku, self.default)
        finally:
            async with self._lock:
                self.in_flight -= 1
