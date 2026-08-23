"""EnrichLlm port and LiteLLM adapter. Does not import jbg_ai.data."""

from __future__ import annotations

import json
from typing import Protocol

from pydantic import ValidationError

from jbg_ai.api.schemas.enrich import EnrichProductInput
from jbg_ai.enrichment.constants import DEFAULT_RAG_LLM_MODEL
from jbg_ai.enrichment.errors import EnrichParseError
from jbg_ai.enrichment.schema import EnrichmentExtraction


class EnrichLlm(Protocol):
    """Runtime extraction port. Implementations must not call OpenAICatalogLlm."""

    model_id: str

    async def extract(self, product: EnrichProductInput, prompt: str) -> EnrichmentExtraction: ...


class LiteLlmEnrichClient:
    """LiteLLM adapter: temperature 0, one product per call, one parse retry."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_RAG_LLM_MODEL,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self.model_id = model

    async def extract(self, product: EnrichProductInput, prompt: str) -> EnrichmentExtraction:
        last_error: Exception | None = None
        for _attempt in range(2):
            raw = await self._complete(product, prompt)
            try:
                return EnrichmentExtraction.model_validate_json(raw)
            except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
        raise EnrichParseError(
            f"enrichment JSON did not parse after retry for sku={product.sku}"
        ) from last_error

    async def _complete(self, product: EnrichProductInput, prompt: str) -> str:
        from litellm import acompletion

        kwargs: dict[str, object] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": _user_payload(product)},
            ],
            "temperature": 0,
            "response_format": EnrichmentExtraction,
            "api_key": self._api_key,
        }
        if self._base_url:
            kwargs["api_base"] = self._base_url
        response = await acompletion(**kwargs)
        content = response.choices[0].message.content
        if not content:
            raise EnrichParseError(f"empty completion for sku={product.sku}")
        return str(content)


def _user_payload(product: EnrichProductInput) -> str:
    return (
        f"sku: {product.sku}\n"
        f"name: {product.name or ''}\n"
        f"description: {product.description or ''}"
    )
