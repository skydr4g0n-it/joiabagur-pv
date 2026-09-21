"""One generated argument: the call, the checks, the single repair, the two policies. C30b.

The whole flow, and the ceiling is part of it:

    generar ──► verificar ──┬── sin violaciones ─────────────► argumentario + citas usadas
                            │
                            └── con violaciones ──► UNA reparación (todas juntas)
                                                        │
                                                        ▼
                                                    verificar
                                                        │
                              ┌── sobrevive una DURA ───┴── sobrevive correspondencia ──┐
                              ▼                                                          ▼
                    sin argumentario                                    argumentario, ESA cita retirada

**Two policies and not one.** A citation that does not resolve, or a figure the context does
not carry, costs the argument: the first is a source that was never there and the second is the
failure the layer exists to prevent. A declared span that does not occur in the prose costs
**that citation** and nothing else — the fragment exists and was in the context, and what
failed is the model's own account of having used it, so withdrawing the citation and publishing
the prose is the proportionate answer and the same *erring towards less* that `pitch_addresses`
already practises with a material the vocabulary cannot resolve.

**One repair, not one per check.** The two gates fail for the same underlying reason: a model
that invents a price is the model that hangs a citation. Repairing each separately would put
the ceiling at four provider calls against the 128,6 ms the whole retrieval costs today.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass

from jbg_ai.assist.constants import MAX_PITCH_PROVIDER_CALLS, PROMPT_VERSION
from jbg_ai.assist.llm import AssistLlm, TokenUsage
from jbg_ai.assist.modes import AssistMode
from jbg_ai.assist.errors import PitchProviderError
from jbg_ai.assist.prompt import AgentPitchTask, PitchContext, PitchTask, build_messages
from jbg_ai.assist.schema import AssistPitch
from jbg_ai.assist.verification import Violation, repair_message, verify

logger = logging.getLogger(__name__)

#: What the argument is when it is withheld. Empty and never a placeholder sentence: a
#: placeholder is something a client can ship by accident.
EMPTY_PITCH = ""


@dataclass(frozen=True)
class PitchOutcome:
    """What the generation layer produced, including when it produced no prose.

    `generated` is the **complete** object of the last call — the argument plus every declared
    citation with its supporting span. The serving path must never persist or log it; the
    evaluation harness is the declared exception, and it wants the whole object rather than the
    text alone, because with the spans C38 has claim↔citation pairs already aligned and can
    measure faithfulness per claim instead of over the whole answer.
    """

    pitch: str
    used_citation_ids: tuple[str, ...]
    usage: TokenUsage
    prompt_version: str
    violations: tuple[Violation, ...] = ()
    withdrawn_citation_ids: tuple[str, ...] = ()
    provider_error: str | None = None
    elapsed_ms: float = 0.0
    generated: AssistPitch | None = None
    #: What the **first** attempt violated, before any repair. The serving path does not act on
    #: it; the sweep does, because the rate that says whether the gate works is the rate at
    #: which generations arrive broken, and the rate after a repair confounds the two.
    initial_violations: tuple[Violation, ...] = ()
    initial_generated: AssistPitch | None = None
    #: How long each provider call took, in order. **Per call and not per request**, because the
    #: timeout is per call: measuring a two-call request against a one-call limit is how a five
    #: per cent cut reads as seventy.
    call_latencies_ms: tuple[float, ...] = ()

    @property
    def withheld(self) -> bool:
        return not self.pitch

    @property
    def digest(self) -> str:
        """A short hash of the argument. What the log carries **instead of** the text: it makes
        two responses comparable and one re-derivable by nobody."""
        return hashlib.sha256(self.pitch.encode("utf-8")).hexdigest()[:16]

    def causes(self) -> tuple[str, ...]:
        return tuple(item.cause for item in self.violations)


def _published_ids(
    generated: AssistPitch, withdrawn: Sequence[str]
) -> tuple[str, ...]:
    """The citations to publish: declared, verified, deduplicated, in declaration order."""
    refused = set(withdrawn)
    seen: list[str] = []
    for item in generated.used:
        if item.citation_id in refused or item.citation_id in seen:
            continue
        seen.append(item.citation_id)
    return tuple(seen)


async def generate_pitch(
    payload: PitchContext,
    task: PitchTask | AgentPitchTask | AssistMode,
    *,
    client: AssistLlm,
    prompt_text: str | None = None,
    prompt_version: str = PROMPT_VERSION,
) -> PitchOutcome:
    """Generate, verify, repair at most once, and apply the policy of what survives.

    Never raises on a provider fault: it returns an outcome with no argument and the cause
    recorded. A five-hundred for a timeout would throw away the half of the response that is
    already computed and works.

    `prompt_version` travels **beside** `prompt_text` because the two are one fact seen twice:
    a caller that supplies another version's text and lets the reported version default would
    stamp the response with a prompt that never reached the model — the failure `enrichment/`
    already paid for once, and the reason the path is derived from the constant rather than
    written next to it. The default is the deterministic route's, so that route is unchanged.
    """
    started = time.perf_counter()
    usage = TokenUsage()

    def elapsed() -> float:
        return (time.perf_counter() - started) * 1000.0

    latencies: list[float] = []

    async def timed(messages):
        call_started = time.perf_counter()
        try:
            return await client.generate(messages)
        finally:
            latencies.append((time.perf_counter() - call_started) * 1000.0)

    messages = build_messages(payload, task, prompt_text=prompt_text)
    try:
        completion = await timed(messages)
    except PitchProviderError as exc:
        return PitchOutcome(
            pitch=EMPTY_PITCH,
            used_citation_ids=(),
            usage=usage,
            prompt_version=prompt_version,
            provider_error=exc.cause,
            elapsed_ms=elapsed(),
            call_latencies_ms=tuple(latencies),
        )

    usage = usage + completion.usage
    generated = completion.pitch
    violations = verify(generated, payload)
    initial = violations
    initial_generated = generated

    if violations:
        repair = build_messages(
            payload,
            task,
            prompt_text=prompt_text,
            repair=repair_message(violations),
            previous=completion.raw,
        )
        try:
            repaired = await timed(repair)
        except PitchProviderError as exc:
            # The repair never happened, so the violations of the first call are the ones that
            # survive. Nothing is retried: the budget is spent and the policy below decides.
            return _decide(
                generated,
                violations,
                usage=usage,
                elapsed_ms=elapsed(),
                provider_error=exc.cause,
                prompt_version=prompt_version,
                initial=initial,
                initial_generated=initial_generated,
                latencies=tuple(latencies),
            )
        usage = usage + repaired.usage
        generated = repaired.pitch
        violations = verify(generated, payload)

    if usage.calls > MAX_PITCH_PROVIDER_CALLS:  # pragma: no cover — structurally impossible
        raise AssertionError(
            f"the provider was called {usage.calls} times for one request; "
            f"the ceiling is {MAX_PITCH_PROVIDER_CALLS}"
        )
    return _decide(
        generated,
        violations,
        usage=usage,
        elapsed_ms=elapsed(),
        prompt_version=prompt_version,
        initial=initial,
        initial_generated=initial_generated,
        latencies=tuple(latencies),
    )


def _decide(
    generated: AssistPitch,
    violations: Sequence[Violation],
    *,
    usage: TokenUsage,
    elapsed_ms: float,
    prompt_version: str = PROMPT_VERSION,
    provider_error: str | None = None,
    initial: Sequence[Violation] = (),
    initial_generated: AssistPitch | None = None,
    latencies: tuple[float, ...] = (),
) -> PitchOutcome:
    """The two policies, applied to what survived the repair."""
    hard = tuple(item for item in violations if item.is_hard)
    if hard:
        # Nothing of the prose is served and no declared identifier leaves the service — a
        # dangling citation is never ignored. The citations of the response become the ones
        # that grounded it, which the orchestrator supplies: degrading must not leave the
        # response poorer than the structured layer's own.
        return PitchOutcome(
            pitch=EMPTY_PITCH,
            used_citation_ids=(),
            usage=usage,
            prompt_version=prompt_version,
            violations=tuple(violations),
            provider_error=provider_error,
            elapsed_ms=elapsed_ms,
            generated=generated,
            initial_violations=tuple(initial),
            initial_generated=initial_generated,
            call_latencies_ms=latencies,
        )

    withdrawn = tuple(
        item.citation_id for item in violations if item.citation_id is not None
    )
    return PitchOutcome(
        pitch=generated.pitch,
        used_citation_ids=_published_ids(generated, withdrawn),
        usage=usage,
        prompt_version=prompt_version,
        violations=tuple(violations),
        withdrawn_citation_ids=withdrawn,
        provider_error=provider_error,
        elapsed_ms=elapsed_ms,
        generated=generated,
        initial_violations=tuple(initial),
        initial_generated=initial_generated,
        call_latencies_ms=latencies,
    )
