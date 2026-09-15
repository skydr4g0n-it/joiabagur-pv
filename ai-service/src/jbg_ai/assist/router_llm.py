"""The classifier port and its LiteLLM adapter. Delivered by C31.

**The seam of `assist/llm.py` is replicated and its class is not reused**, and that is a
consequence of the shape rather than a preference: `LiteLlmAssistClient` pins `response_format`
to `AssistPitch`, so reusing it would mean either a second constructor argument that only one
caller ever sets, or a client that can be asked for the wrong object. Two clients with the same
seam and two pinned schemas is the cheaper shape, and it is what makes `JPV_ROUTER_LLM_MODEL` a
setting that can move without touching the argument's.

What is replicated, point for point: temperature zero, `num_retries: 0` so two retry layers do
not stack, `response_format` pinned to the output schema, `complete` injectable through the
constructor so every test drives a fake and no test opens a socket, and an explicit per-call
timeout.

**What is deliberately not replicated: even the single repair.** `assist/llm.py` sits under a
layer that spends a second call fixing a violated argument; there is nothing in a *label* to
repair. An unparseable reply here is a degradation, not a violation, and the caller fails open.
That is what makes `MAX_ROUTER_PROVIDER_CALLS = 1` literal, and with it the system ceiling of
three a property a test can witness rather than an intention.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from jbg_ai.assist.constants import DEFAULT_ROUTER_MODEL, ROUTER_TIMEOUT_SECONDS
from jbg_ai.assist.errors import RouterProviderError
from jbg_ai.assist.llm import ProviderReply, TokenUsage
from jbg_ai.assist.schema import RouteDecision

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouteCompletion:
    """One classification: the parsed decision and what it cost.

    The raw text is **not** kept, unlike `PitchCompletion`'s. It exists there because the repair
    is a turn that shows the model its own previous output; there is no repair here, so keeping
    it would be keeping the operator's query in an object that outlives the call for no purpose.
    """

    decision: RouteDecision
    usage: TokenUsage


CompleteFn = Callable[[Sequence[Mapping[str, str]]], Awaitable[ProviderReply]]


class RouterLlm(Protocol):
    """The port the orchestrator is handed. It receives a client; it never builds one."""

    model_id: str

    async def classify(
        self, messages: Sequence[Mapping[str, str]]
    ) -> RouteCompletion: ...


class LiteLlmRouterClient:
    """LiteLLM adapter: temperature zero, structured output, **one call**, explicit timeout.

    Every failure leaves through `RouterProviderError` with a `cause` the log can partition by:
    `timeout`, `empty`, `parse`, or the provider exception's own class name. A label outside the
    closed vocabulary arrives here as a Pydantic `ValidationError` and leaves as `parse` — an
    unknown value is an unparseable reply, and it never becomes a value that propagates.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_ROUTER_MODEL,
        base_url: str | None = None,
        complete: CompleteFn | None = None,
        timeout: float = ROUTER_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._complete_fn = complete
        self._timeout = timeout
        self.model_id = model

    async def classify(
        self, messages: Sequence[Mapping[str, str]]
    ) -> RouteCompletion:
        try:
            reply = await asyncio.wait_for(self._complete(messages), self._timeout)
        except TimeoutError as exc:
            raise RouterProviderError(
                f"the classifier exceeded {self._timeout} s", cause="timeout"
            ) from exc
        except RouterProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 — every provider fault degrades alike
            raise RouterProviderError(str(exc), cause=type(exc).__name__) from exc

        try:
            parsed = RouteDecision.model_validate_json(reply.content)
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            raise RouterProviderError(
                "the classification did not parse as the declared closed vocabulary",
                cause="parse",
            ) from exc
        return RouteCompletion(
            decision=parsed,
            usage=reply.usage.with_model(reply.usage.model or self.model_id),
        )

    async def _complete(
        self, messages: Sequence[Mapping[str, str]]
    ) -> ProviderReply:
        if self._complete_fn is not None:
            return await self._complete_fn(messages)

        # Imported inside the call, exactly as `assist/llm.py` and `enrichment/llm.py` do it:
        # the package must stay importable — and the suite offline — without the provider
        # library being reached at import time.
        from litellm import acompletion

        kwargs: dict[str, object] = {
            "model": self._model,
            "messages": list(messages),
            "temperature": 0,
            "response_format": RouteDecision,
            "api_key": self._api_key,
            "num_retries": 0,
            "timeout": self._timeout,
        }
        if self._base_url:
            kwargs["api_base"] = self._base_url
        response = await acompletion(**kwargs)
        content = response.choices[0].message.content
        if not content:
            raise RouterProviderError(
                "the classifier returned an empty completion", cause="empty"
            )
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
