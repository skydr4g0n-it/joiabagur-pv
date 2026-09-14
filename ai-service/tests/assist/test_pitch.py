"""One repair, two policies, an accumulated cost and a degradation. C30b.

Every test drives the **real** `LiteLlmAssistClient` over a scripted `complete`, so the parsing,
the timeout, the usage extraction and the accumulation are all under test. No socket is opened
and no model is called.
"""

from __future__ import annotations


from jbg_ai.assist.constants import (
    CAUSE_CLAIM_NOT_IN_PITCH,
    CAUSE_CURRENCY_ADJACENT,
    CAUSE_DANGLING_CITATION,
    CAUSE_FIGURE_NOT_IN_CONTEXT,
    MAX_PITCH_PROVIDER_CALLS,
    PROMPT_VERSION,
)
from jbg_ai.assist.llm import TokenUsage
from jbg_ai.assist.modes import AssistMode
from jbg_ai.assist.pitch import generate_pitch
from jbg_ai.assist.prompt import PitchCitation, payload_from
from support.assist_pitch import pitch, refusing_client, scripted_client
from support.assist_world import run

GOLD = "material-oro#que-significa-750-y-18k"
CARE = "material-oro#cuidados-y-limpieza-en-casa"

GOOD = pitch(
    "Es un anillo de oro de 750 milésimas, que es lo que marca el 18k. "
    "Se limpia en casa con un paño suave y agua templada. "
    "Cuesta {{price}} y ahora mismo tenemos {{stock}}.",
    (GOLD, "oro de 750 milésimas"),
    (CARE, "se limpia en casa con un paño suave"),
)


def _payload(**overrides):
    values = dict(
        sku="JBG-0001",
        piece_type="anillo",
        materials=["oro"],
        variant_label="18 mm",
        citations=[
            PitchCitation(
                GOLD,
                "El oro",
                "Qué significa 750 y 18k",
                "general",
                "El oro de 18 quilates son 750 milésimas y el de 14, 585.",
            ),
            PitchCitation(
                CARE,
                "El oro",
                "Cuidados y limpieza en casa",
                "general",
                "Se limpia en casa con un paño suave y agua templada.",
            ),
        ],
    )
    values.update(overrides)
    return payload_from(**values)


def _generate(*script, payload=None, mode=AssistMode.PIECE_ONLY, **kwargs):
    client, provider = scripted_client(*script, **kwargs)
    outcome = run(generate_pitch(payload or _payload(), mode, client=client))
    return outcome, provider


# --- the happy path ------------------------------------------------------------------------


def test_a_verified_argument_is_published_with_the_citations_it_declared() -> None:
    outcome, provider = _generate(GOOD)

    assert provider.call_count == 1
    assert outcome.pitch.startswith("Es un anillo de oro")
    assert outcome.used_citation_ids == (GOLD, CARE)
    assert outcome.violations == ()
    assert outcome.prompt_version == PROMPT_VERSION


def test_a_response_carrying_an_argument_publishes_only_the_citations_it_used() -> None:
    """Two fragments were handed over and the argument declared one. Emitting both would be
    the decoration the whole verification exists to refuse."""
    only_one = pitch(
        "Es un anillo de oro de 750 milésimas y envejece muy bien.",
        (GOLD, "oro de 750 milésimas"),
    )

    outcome, _ = _generate(only_one)

    assert outcome.used_citation_ids == (GOLD,)


def test_an_argument_citing_nothing_is_published_and_is_not_a_failure() -> None:
    """The piece's own metadata is not citable — the catalogue is never cited — so an argument
    resting only on what the piece declares legitimately cites nothing."""
    outcome, _ = _generate(pitch("Un anillo muy bonito que sienta de maravilla."))

    assert outcome.pitch
    assert outcome.used_citation_ids == ()
    assert outcome.violations == ()


# --- 7.1 · one repair, and a ceiling of two calls ------------------------------------------


def test_two_failed_checks_share_a_single_repair() -> None:
    """HU escenario 8. Both violations travel in one repair turn, and the provider is called
    twice at most — not once per failing check, which would put the ceiling at four."""
    broken = pitch(
        "Un anillo de 4 gramos que te llevas por 750 €.",
        ("material-plata#inventada", "un anillo de 4 gramos"),
    )

    outcome, provider = _generate(broken, GOOD)

    assert provider.call_count == 2
    assert provider.call_count <= MAX_PITCH_PROVIDER_CALLS
    repair_turn = provider.messages_of(1)[-1]["content"]
    for fragment in ("«4»", "«750»", "material-plata#inventada"):
        assert fragment in repair_turn
    assert outcome.pitch == GOOD.pitch
    assert outcome.violations == ()


def test_the_repair_shows_the_model_its_own_previous_output() -> None:
    """A repair is a turn and not a different prompt: the system message is the same text and
    the data the same object, so the reported version still names what produced the result."""
    outcome, provider = _generate(pitch("Pesa 4 gramos."), GOOD)

    first, second = provider.messages_of(0), provider.messages_of(1)
    assert second[0] == first[0]
    assert second[1] == first[1]
    assert second[2]["role"] == "assistant"
    assert "Pesa 4 gramos." in second[2]["content"]
    assert second[3]["role"] == "user"
    assert outcome.usage.calls == 2


def test_a_valid_first_attempt_costs_exactly_one_call() -> None:
    outcome, provider = _generate(GOOD)

    assert provider.call_count == 1
    assert outcome.usage.calls == 1


# --- 7.2 · the hard policy -----------------------------------------------------------------


def test_dangling_citation_triggers_single_repair_then_drops_the_pitch() -> None:
    """HU escenario 6. Repaired once; surviving, it costs the whole argument — and the dangling
    identifier never leaves the service."""
    dangling = pitch(
        "Un anillo de oro que envejece bien.",
        ("material-plata#inventada", "un anillo de oro"),
    )

    outcome, provider = _generate(dangling, dangling)

    assert provider.call_count == 2
    assert outcome.withheld and outcome.pitch == ""
    assert outcome.used_citation_ids == ()
    assert CAUSE_DANGLING_CITATION in outcome.causes()
    assert "material-plata#inventada" not in outcome.used_citation_ids


def test_a_surviving_invented_figure_drops_the_pitch() -> None:
    """HU escenario 4, second half."""
    invented = pitch("Pesa 4 gramos.", (GOLD, "pesa 4 gramos"))

    outcome, _ = _generate(invented, invented)

    assert outcome.withheld
    assert CAUSE_FIGURE_NOT_IN_CONTEXT in outcome.causes()


def test_a_surviving_currency_adjacent_figure_drops_the_pitch() -> None:
    """HU escenario 5, second half: the corpus's own `750`, next to a currency mark."""
    priced = pitch("Te lo llevas por 750 €.", (GOLD, "te lo llevas por 750"))

    outcome, _ = _generate(priced, priced)

    assert outcome.withheld
    assert CAUSE_CURRENCY_ADJACENT in outcome.causes()


def test_rejected_pitch_still_reports_its_prompt_version() -> None:
    """HU escenario 10. An empty argument alone cannot tell a deployment that does not generate
    from a generation that was refused, and that distinction is the only evidence a consumer
    has that the guard acted."""
    invented = pitch("Pesa 4 gramos.", (GOLD, "pesa 4 gramos"))

    outcome, _ = _generate(invented, invented)

    assert outcome.pitch == ""
    assert outcome.prompt_version == PROMPT_VERSION


# --- 7.3 · the proportionate policy --------------------------------------------------------


def test_unverifiable_claim_withdraws_its_citation_not_the_pitch() -> None:
    """HU escenario 7. The fragment exists and was in the context; what failed is the model's
    own account of having used it, so the proportionate answer is withdrawing that citation."""
    mismatched = pitch(
        "Es un anillo de oro de 750 milésimas y se limpia con un paño suave.",
        (GOLD, "oro de 750 milésimas"),
        (CARE, "resiste el agua del mar"),
    )

    outcome, _ = _generate(mismatched, mismatched)

    assert outcome.pitch.startswith("Es un anillo de oro")
    assert outcome.used_citation_ids == (GOLD,)
    assert outcome.withdrawn_citation_ids == (CARE,)
    assert outcome.causes() == (CAUSE_CLAIM_NOT_IN_PITCH,)


def test_a_correspondence_failure_repaired_on_the_second_call_publishes_both() -> None:
    mismatched = pitch(
        "Es un anillo de oro de 750 milésimas.",
        (GOLD, "oro de 750 milésimas"),
        (CARE, "no aparece en el texto"),
    )

    outcome, provider = _generate(mismatched, GOOD)

    assert provider.call_count == 2
    assert outcome.used_citation_ids == (GOLD, CARE)
    assert outcome.withdrawn_citation_ids == ()


def test_a_hard_violation_beside_a_soft_one_still_drops_the_whole_argument() -> None:
    """The policies are not averaged: one surviving hard violation governs the outcome."""
    both = pitch(
        "Pesa 4 gramos.",
        (GOLD, "pesa 4 gramos"),
        (CARE, "no aparece"),
    )

    outcome, _ = _generate(both, both)

    assert outcome.withheld
    assert outcome.used_citation_ids == ()


# --- 5.3 · the cost accumulates -------------------------------------------------------------


def test_usage_is_accumulated_across_the_repair() -> None:
    """HU escenario 18. Summed and not replaced: reporting the last call alone understates the
    cost precisely on the requests that cost the most, which are the ones a measurement exists
    to find."""
    first = TokenUsage(prompt_tokens=1500, completion_tokens=300, total_tokens=1800, calls=1)
    second = TokenUsage(prompt_tokens=1700, completion_tokens=260, total_tokens=1960, calls=1)

    outcome, provider = _generate(
        pitch("Pesa 4 gramos."), GOOD, usage=[first, second]
    )

    assert provider.call_count == 2
    assert outcome.usage.prompt_tokens == 3200
    assert outcome.usage.completion_tokens == 560
    assert outcome.usage.total_tokens == 3760
    assert outcome.usage.calls == 2
    assert outcome.usage.model == "fake/pitch-model"


def test_the_usage_type_adds_rather_than_replacing() -> None:
    """The accumulable type C32 needs for its own iteration budget, asserted on its own terms."""
    total = TokenUsage() + TokenUsage(prompt_tokens=10, total_tokens=10, calls=1)
    total = total + TokenUsage(prompt_tokens=5, completion_tokens=2, total_tokens=7, calls=1)

    assert (total.prompt_tokens, total.completion_tokens, total.total_tokens) == (15, 2, 17)
    assert total.calls == 2


# --- 8.3 · the provider fails, and the layer degrades ---------------------------------------


def test_provider_failure_degrades_to_structure_without_prose() -> None:
    """HU escenario 13. No exception escapes: a five-hundred for a provider fault would throw
    away the half of the response that is already computed and works."""
    outcome, provider = _generate(RuntimeError("the provider is down"))

    assert provider.call_count == 1
    assert outcome.withheld
    assert outcome.provider_error == "RuntimeError"
    assert outcome.prompt_version == PROMPT_VERSION
    assert outcome.usage.total_tokens == 0
    assert outcome.usage.model is None, "zero tokens beside a model id reads as a measured cost"


def test_a_timeout_degrades_and_is_recorded_as_a_timeout() -> None:
    """Three seconds in production; here the constant is overridden so the test takes none."""
    client, provider = scripted_client(GOOD, delay=0.05, timeout=0.01)

    outcome = run(generate_pitch(_payload(), AssistMode.PIECE_ONLY, client=client))

    assert outcome.withheld
    assert outcome.provider_error == "timeout"
    assert provider.call_count == 1


def test_a_completion_that_does_not_parse_degrades_rather_than_spending_the_repair() -> None:
    """There is no argument to repair, and spending the second call on a transport accident
    would trade away the repair that fixes a real violation."""
    outcome, provider = _generate("no soy json")

    assert provider.call_count == 1
    assert outcome.withheld
    assert outcome.provider_error == "parse"


def test_a_failing_repair_leaves_the_first_attempts_violations_surviving() -> None:
    """The repair never happened, so what it did not fix is what governs the policy."""
    outcome, provider = _generate(
        pitch("Pesa 4 gramos.", (GOLD, "pesa 4 gramos")),
        RuntimeError("the provider went away"),
    )

    assert provider.call_count == 2
    assert outcome.withheld
    assert CAUSE_FIGURE_NOT_IN_CONTEXT in outcome.causes()
    assert outcome.provider_error == "RuntimeError"
    assert outcome.usage.calls == 1, "only the call that returned counts as a cost"


def test_the_refusing_client_is_never_reached_by_a_mode_that_does_not_generate() -> None:
    """The fake that fails loudly, so a cut that stopped cutting cannot pass quietly."""
    client, provider = refusing_client()

    with_exception = run(
        generate_pitch(_payload(), AssistMode.PIECE_ONLY, client=client)
    )

    assert provider.calls == 1, "this path DOES generate; the guard belongs to the orchestrator"
    assert with_exception.withheld


# --- the generation object the harness inherits --------------------------------------------


def test_the_outcome_carries_the_whole_generation_object_for_the_harness() -> None:
    """C38 wants the argument **and** the declared spans: with them it has claim↔citation pairs
    already aligned and can measure faithfulness per claim. Costs nothing here, a session there.
    """
    outcome, _ = _generate(GOOD)

    assert outcome.generated is not None
    assert [item.supported_claim for item in outcome.generated.used] == [
        "oro de 750 milésimas",
        "se limpia en casa con un paño suave",
    ]


def test_the_digest_identifies_the_argument_without_carrying_it() -> None:
    one, _ = _generate(GOOD)
    same, _ = _generate(GOOD)
    other, _ = _generate(pitch("Otro argumentario distinto del anterior."))

    assert one.digest == same.digest
    assert one.digest != other.digest
    assert one.pitch[:20] not in one.digest


def test_a_transient_provider_fault_degrades_instead_of_being_retried() -> None:
    """No backoff loop underneath the ceiling, which is what makes "two calls" mean two calls.

    C09 waits `ENRICH_BACKOFF_BASE_SECONDS` — two seconds — before its first retry, and this
    layer's whole budget for one call is four. A backoff that spends half the budget
    before the retried call starts is not resilience at a counter; degrading is, and it is free.
    """
    outcome, provider = _generate(RuntimeError("429 rate limited"), GOOD)

    assert provider.call_count == 1, "a provider fault degrades; it is not retried"
    assert outcome.withheld
