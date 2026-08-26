"""EnrichLlm port and LiteLLM adapter. Does not import jbg_ai.data."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from pydantic import ValidationError

from jbg_ai.api.schemas.enrich import EnrichProductInput
from jbg_ai.enrichment.constants import (
    DEFAULT_RAG_LLM_MODEL,
    ENRICH_BACKOFF_BASE_SECONDS,
    MAX_ENRICH_PROVIDER_ATTEMPTS,
)
from jbg_ai.enrichment.errors import EnrichParseError
from jbg_ai.enrichment.schema import EnrichmentExtraction

logger = logging.getLogger(__name__)

CompleteFn = Callable[[EnrichProductInput, str], Awaitable[str]]
SleepFn = Callable[[float], Awaitable[None]]


class EnrichLlm(Protocol):
    """Runtime extraction port. Implementations must not call OpenAICatalogLlm."""

    model_id: str

    async def extract(self, product: EnrichProductInput, prompt: str) -> EnrichmentExtraction: ...


def _is_retryable(exc: BaseException) -> bool:
    """429 and transient provider faults. Parse errors are not retryable here."""
    if isinstance(exc, EnrichParseError):
        return False
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    if isinstance(status, int) and 500 <= status < 600:
        return True
    return type(exc).__name__ in {
        "RateLimitError",
        "ServiceUnavailableError",
        "InternalServerError",
        "Timeout",
        "APIConnectionError",
        "APITimeoutError",
    }


def _backoff_seconds(attempt: int) -> float:
    return ENRICH_BACKOFF_BASE_SECONDS * (2**attempt)


class LiteLlmEnrichClient:
    """LiteLLM adapter: temperature 0, one product per call, provider backoff, one parse retry."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_RAG_LLM_MODEL,
        base_url: str | None = None,
        complete: CompleteFn | None = None,
        sleep: SleepFn = asyncio.sleep,
        max_attempts: int = MAX_ENRICH_PROVIDER_ATTEMPTS,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._complete_fn = complete
        self._sleep = sleep
        self._max_attempts = max_attempts
        self.model_id = model

    async def extract(self, product: EnrichProductInput, prompt: str) -> EnrichmentExtraction:
        last_error: Exception | None = None
        for _attempt in range(2):
            raw = await self._complete_with_retry(product, prompt)
            try:
                return EnrichmentExtraction.model_validate_json(raw)
            except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
        raise EnrichParseError(
            f"enrichment JSON did not parse after retry for sku={product.sku}"
        ) from last_error

    async def _complete_with_retry(self, product: EnrichProductInput, prompt: str) -> str:
        last_error: BaseException | None = None
        for attempt in range(self._max_attempts):
            try:
                return await self._complete(product, prompt)
            except Exception as exc:
                last_error = exc
                if not _is_retryable(exc) or attempt == self._max_attempts - 1:
                    raise
                delay = _backoff_seconds(attempt)
                logger.info(
                    "enrichment retry sku=%s attempt=%s delay_s=%s model=%s",
                    product.sku,
                    attempt + 1,
                    delay,
                    self.model_id,
                )
                await self._sleep(delay)
        raise EnrichParseError(f"enrichment provider failed for sku={product.sku}") from last_error

    async def _complete(self, product: EnrichProductInput, prompt: str) -> str:
        if self._complete_fn is not None:
            return await self._complete_fn(product, prompt)

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
            # Own the retry loop. LiteLLM's default retries plus ours stacked TPM
            # on the AutoBulk run until the whole batch returned 500.
            "num_retries": 0,
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
