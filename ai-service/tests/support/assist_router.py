"""Driving the intent classifier offline. Delivered by C31.

Same shape and same reason as `support/assist_pitch.py`: **the fake goes in at the provider's
door and not above it.** `scripted_router` builds the real `LiteLlmRouterClient` with a
scripted `complete`, so every test still exercises the real parsing, the real closed-vocabulary
validation, the real timeout and the real usage extraction — only the socket is replaced. A
stand-in for the whole client would have tested the test, and here that would be worse than
usual: the property under test is precisely that a label outside the vocabulary fails to parse,
which is the client's own `model_validate_json` and not anything a test double would run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from jbg_ai.assist.llm import ProviderReply, TokenUsage
from jbg_ai.assist.router_llm import LiteLlmRouterClient
from jbg_ai.assist.schema import RouteDecision

#: What one scripted classification reports unless a test says otherwise. Of the order of the
#: real thing — a short prompt and **~30 output tokens**, which is the whole argument for the
#: classifier having its own model setting rather than inheriting the argument's.
DEFAULT_ROUTER_USAGE = TokenUsage(
    prompt_tokens=700, completion_tokens=30, total_tokens=730, calls=1
)


def decision(
    served: str = "in_domain",
    index: str | None = "catalog",
    missing_axis: str | None = None,
) -> RouteDecision:
    """A `RouteDecision` with the shape a served catalogue query has, by default."""
    return RouteDecision(served=served, index=index, missing_axis=missing_axis)


class ScriptedRouter:
    """One scripted `complete`: it records what it was handed and answers in order.

    The last entry repeats, exactly as `ScriptedProvider` does — which is what makes a test
    that asserts the classifier is called **once** assert something the fake would happily
    exceed, rather than something the fake enforces on its behalf.
    """

    def __init__(
        self,
        script: Sequence[RouteDecision | BaseException | str],
        *,
        usage: Sequence[TokenUsage] | None = None,
        delay: float = 0.0,
    ) -> None:
        self._script = list(script)
        self._usage = list(usage) if usage is not None else None
        self._delay = delay
        self.calls: list[list[dict[str, str]]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def system_of(self, index: int) -> str:
        return self.calls[index][0]["content"]

    def user_of(self, index: int) -> str:
        return self.calls[index][1]["content"]

    async def __call__(self, messages: Sequence[Mapping[str, str]]) -> ProviderReply:
        self.calls.append([dict(message) for message in messages])
        if self._delay:
            await asyncio.sleep(self._delay)
        reply = self._script[min(len(self.calls) - 1, len(self._script) - 1)]
        if isinstance(reply, BaseException):
            raise reply
        usage = (
            self._usage[min(len(self.calls) - 1, len(self._usage) - 1)]
            if self._usage
            else DEFAULT_ROUTER_USAGE
        )
        content = reply if isinstance(reply, str) else reply.model_dump_json()
        return ProviderReply(content=content, usage=usage)


def scripted_router(
    *script: RouteDecision | BaseException | str,
    usage: Sequence[TokenUsage] | None = None,
    delay: float = 0.0,
    timeout: float | None = None,
) -> tuple[LiteLlmRouterClient, ScriptedRouter]:
    """The real classifier client over a scripted provider. Returns both, so calls can be counted."""
    provider = ScriptedRouter(script, usage=usage, delay=delay)
    kwargs: dict[str, Any] = {
        "api_key": "sk-test",
        "model": "fake/router-model",
        "complete": provider,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    return LiteLlmRouterClient(**kwargs), provider


class RefusingRouter:
    """A `complete` that fails the test if it is ever called.

    **This is how "M2 and M3 make no classifier call" is asserted by introspection rather than
    by reading the code.** A test that merely checked a call counter would pass if the call
    happened and the counter were read at the wrong moment; a provider that raises makes the
    request fail loudly the instant the classifier is reached.
    """

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, messages: Sequence[Mapping[str, str]]) -> ProviderReply:
        self.calls += 1
        raise AssertionError("no classifier call may be made on this path")


def refusing_router() -> tuple[LiteLlmRouterClient, RefusingRouter]:
    provider = RefusingRouter()
    return (
        LiteLlmRouterClient(
            api_key="sk-test", model="fake/router-model", complete=provider
        ),
        provider,
    )
