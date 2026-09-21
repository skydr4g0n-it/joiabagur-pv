"""Driving the agent loop offline. C32b.

Same shape and same reason as `support/assist_pitch.py` and `support/assist_router.py`: **the
fake goes in at the provider's door and not above it.** `scripted_agent` builds the real
`LiteLlmAgentClient` over a scripted `complete`, so every test exercises the real timeout, the
real usage extraction, the real argument parsing and — the property that matters most here —
the real discarding of the model's prose at the adapter boundary. A stand-in for the whole
client would be testing the test, and it would be testing away the one thing under test.

The last entry of a script repeats, exactly as the two sibling doubles do. That is deliberate:
a test asserting a **ceiling** on iterations or on tool calls must assert something the fake
would happily exceed, not something the fake enforces on its behalf.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from jbg_ai.assist.agent_llm import LiteLlmAgentClient, RawStep
from jbg_ai.assist.llm import TokenUsage

#: What one scripted turn reports unless a test says otherwise. Of the order of the real
#: thing for a loop turn — a system message, a transcript, the six schemas and the
#: observations so far — so a cost assertion reads like a cost.
DEFAULT_AGENT_USAGE = TokenUsage(
    prompt_tokens=3000, completion_tokens=60, total_tokens=3060, calls=1
)


def wants(
    *calls: tuple[str, Mapping[str, Any]] | tuple[str, Mapping[str, Any], str],
    text: str | None = None,
) -> RawStep:
    """A turn that asks for tools. `("buscar_catalogo", {"consulta": "anillo"})`.

    `text` is the prose the model wrote alongside the calls, which the adapter must throw
    away: a test passes it precisely in order to assert that it is nowhere afterwards.
    """
    import json

    prepared: list[tuple[str, str, str]] = []
    for position, item in enumerate(calls, start=1):
        name, arguments = item[0], item[1]
        # A third element is a **raw** argument blob, for the test that drives a model
        # emitting something that is not a JSON object at all.
        blob = item[2] if len(item) > 2 else json.dumps(arguments, ensure_ascii=False)
        prepared.append((f"call-{position}", name, blob))
    return RawStep(
        tool_calls=tuple(prepared),
        text=text,
        usage=DEFAULT_AGENT_USAGE,
        finish_reason="tool_calls",
    )


def finishes(text: str | None = None) -> RawStep:
    """A turn that asks for nothing: the model has what it needs."""
    return RawStep(
        tool_calls=(), text=text, usage=DEFAULT_AGENT_USAGE, finish_reason="stop"
    )


class ScriptedAgent:
    """One scripted `complete`: it records what it was handed and answers in order."""

    def __init__(
        self,
        script: Sequence[RawStep | BaseException],
        *,
        delay: float = 0.0,
    ) -> None:
        self._script = list(script)
        self._delay = delay
        self.calls: list[list[dict[str, Any]]] = []
        self.tools_offered: list[list[dict[str, Any]]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def system_of(self, index: int) -> str:
        return str(self.calls[index][0]["content"])

    def user_of(self, index: int) -> str:
        return str(self.calls[index][1]["content"])

    def messages_of(self, index: int) -> list[dict[str, Any]]:
        return self.calls[index]

    async def __call__(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> RawStep:
        self.calls.append([dict(message) for message in messages])
        self.tools_offered.append([dict(tool) for tool in tools])
        if self._delay:
            await asyncio.sleep(self._delay)
        reply = self._script[min(len(self.calls) - 1, len(self._script) - 1)]
        if isinstance(reply, BaseException):
            raise reply
        return reply


def scripted_agent(
    *script: RawStep | BaseException,
    delay: float = 0.0,
    timeout: float | None = None,
) -> tuple[LiteLlmAgentClient, ScriptedAgent]:
    """The real agent client over a scripted provider. Returns both, so calls can be counted."""
    provider = ScriptedAgent(script, delay=delay)
    kwargs: dict[str, Any] = {
        "api_key": "sk-test",
        "model": "fake/agent-model",
        "complete": provider,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    return LiteLlmAgentClient(**kwargs), provider


class RefusingAgent:
    """A `complete` that fails the test if it is ever called.

    **This is how «the guardrail refused before the loop started» is asserted structurally.** A
    test reading a call counter would pass if the call happened and the counter were read at
    the wrong moment; a provider that raises makes the request fail loudly the instant the loop
    is reached.
    """

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> RawStep:
        self.calls += 1
        raise AssertionError("no agent provider call may be made on this path")


def refusing_agent() -> tuple[LiteLlmAgentClient, RefusingAgent]:
    provider = RefusingAgent()
    return (
        LiteLlmAgentClient(
            api_key="sk-test", model="fake/agent-model", complete=provider
        ),
        provider,
    )
