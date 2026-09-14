"""The generative port and its LiteLLM adapter. Delivered by C30b.

**The seam of C09 is replicated and its class is not reused**, and that is a measurement rather
than a preference: `LiteLlmEnrichClient.extract()` returns the parsed model and drops
`response.usage`, so `enrichment/pipeline.py` builds `Usage(model=…)` with zero tokens. C09
never needed them. This layer needs them in three places at once — the `usage` field of the
contract, the log line, and the cost column of the ablation table — so the client returns the
parsed object **and** what it cost.

What is replicated: temperature zero, `num_retries: 0` so two retry layers do not stack,
`response_format` pinned to the output schema, and `complete` injectable through the
constructor so every test drives a fake and no test opens a socket.

**What is deliberately not replicated: the transient-retry loop with its backoff.** C09 waits
`ENRICH_BACKOFF_BASE_SECONDS` — two seconds — before its first retry, and this layer's whole
budget for one call is four. A backoff that consumes half the budget before the
retried call starts is not a resilience mechanism at a counter; degrading to the structured
response is, and it is free. The consequence is that `MAX_PITCH_PROVIDER_CALLS` is literal:
two calls means two calls, which is what makes the ceiling a testable property instead of an
intention.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from pydantic import ValidationError

from jbg_ai.assist.constants import DEFAULT_ASSIST_MODEL, PITCH_TIMEOUT_SECONDS
from jbg_ai.assist.errors import PitchProviderError
from jbg_ai.assist.schema import AssistPitch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenUsage:
    """Model usage that **adds**, which is the whole reason it is a type and not a tuple.

    A repair that replaced the usage instead of adding to it would understate the cost exactly
    on the requests that cost the most — the ones a cost measurement exists to find. `calls`
    travels with it so the two-call ceiling is observable from the same object.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str | None = None
    calls: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            # The model of whichever call reported one. Two different models for one request
            # cannot happen here: the client is built once and the repair is the same client.
            model=other.model or self.model,
            calls=self.calls + other.calls,
        )

    def with_model(self, model: str | None) -> "TokenUsage":
        return replace(self, model=model)


@dataclass(frozen=True)
class ProviderReply:
    """What one completion returned: the raw content, and what it cost."""

    content: str
    usage: TokenUsage


@dataclass(frozen=True)
class PitchCompletion:
    """One generation: the parsed object, its cost, and the raw text of the reply.

    The raw text is kept because the repair is a **turn** and not a second prompt: the model is
    shown its own previous output next to the violations it has to fix.
    """

    pitch: AssistPitch
    usage: TokenUsage
    raw: str


CompleteFn = Callable[[Sequence[Mapping[str, str]]], Awaitable[ProviderReply]]


class AssistLlm(Protocol):
    """The port the orchestrator is handed. It receives a client; it never builds one."""

    model_id: str

    async def generate(
        self, messages: Sequence[Mapping[str, str]]
    ) -> PitchCompletion: ...


class LiteLlmAssistClient:
    """LiteLLM adapter: temperature zero, structured output, one call per call, explicit timeout.

    A completion that does not parse is treated as a **provider failure and not as a violation
    to repair**: there is no argument to repair, and spending the second call of the budget on
    a reply that produced no object would trade the repair that fixes a real violation for one
    that fixes a transport accident. The response degrades instead, which is what it would do
    anyway one step later.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_ASSIST_MODEL,
        base_url: str | None = None,
        complete: CompleteFn | None = None,
        timeout: float = PITCH_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._complete_fn = complete
        self._timeout = timeout
        self.model_id = model

    async def generate(
        self, messages: Sequence[Mapping[str, str]]
    ) -> PitchCompletion:
        try:
            reply = await asyncio.wait_for(self._complete(messages), self._timeout)
        except TimeoutError as exc:
            raise PitchProviderError(
                f"the provider exceeded {self._timeout} s", cause="timeout"
            ) from exc
        except PitchProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 — every provider fault degrades alike
            raise PitchProviderError(str(exc), cause=type(exc).__name__) from exc

        try:
            parsed = AssistPitch.model_validate_json(reply.content)
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            raise PitchProviderError(
                "the completion did not parse as the declared output schema",
                cause="parse",
            ) from exc
        return PitchCompletion(
            pitch=parsed,
            usage=reply.usage.with_model(reply.usage.model or self.model_id),
            raw=reply.content,
        )

    async def _complete(
        self, messages: Sequence[Mapping[str, str]]
    ) -> ProviderReply:
        if self._complete_fn is not None:
            return await self._complete_fn(messages)

        # Imported inside the call, exactly as `enrichment/llm.py` does it: the package must
        # stay importable — and the suite offline — without the provider library being reached
        # at import time. `test_the_assist_package_imports_no_provider_client` reads that.
        from litellm import acompletion

        kwargs: dict[str, object] = {
            "model": self._model,
            "messages": list(messages),
            "temperature": 0,
            "response_format": AssistPitch,
            "api_key": self._api_key,
            "num_retries": 0,
            "timeout": self._timeout,
        }
        if self._base_url:
            kwargs["api_base"] = self._base_url
        response = await acompletion(**kwargs)
        content = response.choices[0].message.content
        if not content:
            raise PitchProviderError("the provider returned an empty completion", cause="empty")
        usage = getattr(response, "usage", None)
        return ProviderReply(
            content=str(content),
            usage=TokenUsage(
                prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
                model=self.model_id,
                calls=1,
            ),
        )
