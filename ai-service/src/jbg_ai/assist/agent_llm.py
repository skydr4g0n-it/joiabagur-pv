"""The agent's function-calling port and its LiteLLM adapter. C32b.

**This is the third client of this layer and it is a replica, not a subclass**, exactly as the
classifier's was a replica of the argument's. The reason is structural rather than stylistic:
`LiteLlmAssistClient` pins `response_format` to `AssistPitch` and `LiteLlmRouterClient` pins it
to `RouteDecision`, and this one **must not be able to pin anything at all**. A loop asks for
tool calls over an open `tools` list, which is the opposite shape; inheriting from either would
mean a client that can be asked for the wrong thing.

What is replicated, point for point: temperature zero, `num_retries: 0` so two retry layers do
not stack, `complete` injectable through the constructor so every test drives a fake and no
test opens a socket, the provider library imported **inside** the call so the package stays
importable without it, and an explicit per-call timeout.

**What is new here, and it is the whole point of the module: the return type has nowhere to put
prose.**

    Opción 1   AgentStep(tool_calls, text, usage)      el invariante es DISCIPLINA
    Opción 2   AgentStep(tool_calls, usage, finish)    el invariante es el TIPO      ← ésta

«The textual content of a loop turn is discarded» stops being a rule somebody has to respect
and becomes a fact about the object. It is the same choice this layer already made when it
verified the read-only invariant by **introspecting the object graph** instead of trusting a
boolean on the descriptor: a field a caller must not read is a field a caller will read.

**The cost is declared and it is real.** The model's own reasoning — which is genuinely useful
when debugging why a loop chose what it chose — is not available. The mitigation is the one
C30b already applies to the argument it refuses to log: the adapter records **how long the
discarded text was and a digest of it**, so two turns are comparable and neither is
re-derivable. The text is dropped at the boundary, in `_step_from`, and never lands in a local
that outlives the call.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from jbg_ai.assist.constants import AGENT_TIMEOUT_SECONDS, DEFAULT_AGENT_MODEL
from jbg_ai.assist.errors import AgentProviderError
from jbg_ai.assist.llm import TokenUsage

logger = logging.getLogger(__name__)

STAGE = "agent_llm"


@dataclass(frozen=True)
class AgentToolCall:
    """One tool call a turn requested: which tool, with what, under which identifier.

    `call_id` is the provider's own identifier for the call and it is carried rather than
    regenerated, because it is what pairs an observation with the call that produced it when a
    turn requests several at once — and a turn requesting several at once is the case the
    design warns appears with the first complex conversation.

    `arguments` is `None` — and **only** `None` — when the provider's argument blob did not
    parse as a JSON object. That is a real case and it is not the same as empty arguments: a
    tool whose every field is optional would accept `{}` and run on defaults for a call the
    model meant differently. The loop turns `None` into an invalid-argument observation
    **without touching a port**, so the distinction costs nothing and cannot be lost.
    """

    call_id: str
    name: str
    arguments: Mapping[str, Any] | None


@dataclass(frozen=True)
class AgentStep:
    """What one turn of the loop produced. **There is no field here that can carry prose.**

    That absence is the specification, not an omission to be corrected later: see the module
    docstring. `finish_reason` is the provider's own short code — `tool_calls`, `stop`,
    `length` — which is a token of a closed set chosen by the provider and never a sentence the
    model wrote.

    `discarded_chars` and `discarded_digest` describe the text that was thrown away without
    being it: a length and sixteen hex characters. They exist so a run can tell «the model said
    nothing» from «the model wrote three paragraphs nobody will ever read», which is a real
    signal about a prompt, and they are the same mitigation C30b applies to the argument.
    """

    tool_calls: tuple[AgentToolCall, ...] = ()
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str | None = None
    discarded_chars: int = 0
    discarded_digest: str | None = None

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


CompleteToolsFn = Callable[
    [Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]]], Awaitable["RawStep"]
]


@dataclass(frozen=True)
class RawStep:
    """What a provider call returned, before the text is dropped. **Never leaves the adapter.**

    It exists so the fake goes in at the provider's door rather than above it — the rule
    `support/assist_pitch.py` already records — which means a test drives the real discarding,
    the real digest and the real argument parsing instead of a stand-in for them. A test that
    replaced the whole client would be testing the test, and here that would be worse than
    usual: the property under test is precisely that the text does not survive this boundary.
    """

    tool_calls: tuple[tuple[str, str, str], ...] = ()
    text: str | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str | None = None


class AgentLlm(Protocol):
    """The port the loop is handed. It receives a client; it never builds one."""

    model_id: str

    async def decide(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> AgentStep: ...


class LiteLlmAgentClient:
    """LiteLLM adapter for function calling: temperature zero, **no `response_format`**.

    The absence of `response_format` is as deliberate as its presence is in the two sibling
    clients. A turn of this loop is not asked for an object; it is asked which tools to run,
    and pinning a schema would force it to answer in prose-shaped JSON that the loop would then
    have to interpret — which is the failure mode the typed port exists to remove.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_AGENT_MODEL,
        base_url: str | None = None,
        complete: CompleteToolsFn | None = None,
        timeout: float = AGENT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._complete_fn = complete
        self._timeout = timeout
        self.model_id = model

    async def decide(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> AgentStep:
        try:
            raw = await asyncio.wait_for(self._complete(messages, tools), self._timeout)
        except TimeoutError as exc:
            raise AgentProviderError(
                f"the agent provider exceeded {self._timeout} s", cause="timeout"
            ) from exc
        except AgentProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 — every provider fault degrades alike
            raise AgentProviderError(str(exc), cause=type(exc).__name__) from exc
        return self._step_from(raw)

    def _step_from(self, raw: RawStep) -> AgentStep:
        """**The boundary where the prose dies.** Everything after this line is typed without it.

        The text is measured and hashed and then goes out of scope with `raw`; nothing that
        survives this method can be used to reconstruct a word of it. The log line carries the
        length and the digest, never the text, and never a tool argument either — an argument
        is the operator's question as the model reformulated it, and the rule this project holds
        keeps that out of durable storage.
        """
        text = raw.text or ""
        digest = (
            hashlib.sha256(text.encode("utf-8")).hexdigest()[:16] if text else None
        )
        calls = tuple(
            AgentToolCall(
                call_id=call_id, name=name, arguments=_parsed_arguments(blob)
            )
            for call_id, name, blob in raw.tool_calls
        )
        logger.info(
            "stage=%s model=%s finish=%s tool_calls=%s tools=%s "
            "discarded_chars=%s discarded_sha256=%s prompt_tokens=%s "
            "completion_tokens=%s total_tokens=%s",
            STAGE,
            self.model_id,
            raw.finish_reason or "none",
            len(calls),
            # The NAMES and never the arguments: a name is what the evaluation needs in order
            # to compare tools invoked against tools expected, and an argument is the query.
            ",".join(call.name for call in calls) or "none",
            len(text),
            digest or "none",
            raw.usage.prompt_tokens,
            raw.usage.completion_tokens,
            raw.usage.total_tokens,
        )
        return AgentStep(
            tool_calls=calls,
            usage=raw.usage.with_model(raw.usage.model or self.model_id),
            finish_reason=raw.finish_reason,
            discarded_chars=len(text),
            discarded_digest=digest,
        )

    async def _complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> RawStep:
        if self._complete_fn is not None:
            return await self._complete_fn(messages, tools)

        # Imported inside the call, exactly as the two sibling clients and `enrichment/llm.py`
        # do it: the package must stay importable — and the suite offline — without the
        # provider library being reached at import time.
        from litellm import acompletion

        kwargs: dict[str, object] = {
            "model": self._model,
            "messages": list(messages),
            "tools": list(tools),
            "tool_choice": "auto",
            "temperature": 0,
            "api_key": self._api_key,
            "num_retries": 0,
            "timeout": self._timeout,
        }
        if self._base_url:
            kwargs["api_base"] = self._base_url
        response = await acompletion(**kwargs)
        choice = response.choices[0]
        message = choice.message
        usage = getattr(response, "usage", None)
        return RawStep(
            tool_calls=tuple(
                (
                    str(getattr(call, "id", "") or ""),
                    str(getattr(getattr(call, "function", None), "name", "") or ""),
                    str(getattr(getattr(call, "function", None), "arguments", "") or ""),
                )
                for call in (getattr(message, "tool_calls", None) or ())
            ),
            text=getattr(message, "content", None),
            usage=TokenUsage(
                prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
                model=self.model_id,
                calls=1,
            ),
            finish_reason=getattr(choice, "finish_reason", None),
        )


def _parsed_arguments(blob: str) -> Mapping[str, Any] | None:
    """The argument object, or `None` when the provider's blob is not one.

    Not an exception: a malformed argument blob is a thing the model did, which the loop reports
    back to it as a failed observation so that it can correct itself on the next turn. Raising
    would cost the whole request for a mistake that costs one call.
    """
    if not blob:
        # A tool with no arguments at all is legitimate; an empty blob is an empty object.
        return {}
    try:
        parsed = json.loads(blob)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None
