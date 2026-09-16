"""The router and the guardrails wired into the orchestrator. C31.

Offline: both clients are the real ones over scripted providers, the knowledge index is the
real 32-document corpus in memory, and the product side is the fake the suite already uses.

**Every "no call is made" assertion here uses a provider that fails loudly**, never a counter
read afterwards. A guard that stopped guarding would otherwise pass in silence, which is the
one failure mode a test of a guard must not have.
"""

from __future__ import annotations

import logging

import pytest

from jbg_ai.api.schemas.assist import AssistRequest
from jbg_ai.assist.constants import (
    INTENT_IN_DOMAIN,
    INTENT_NOT_IN_CATALOGUE,
    INTENT_OUT_OF_DOMAIN,
    INTENT_PRODUCT_PITCH,
    INTENT_UNCLASSIFIED,
    MAX_PROVIDER_CALLS,
    PROMPT_VERSION,
    WARNING_KNOWLEDGE_NOT_COVERED,
    WARNING_QUERY_NOT_IN_CATALOGUE,
    WARNING_QUERY_OUT_OF_DOMAIN,
)
from jbg_ai.assist.orchestrator import assist_sale
from jbg_ai.assist.prompt import TASK_SECTIONS, PitchTask
from jbg_ai.assist.routing import CLARIFICATION_TEMPLATES
from jbg_ai.knowledge.offline import InMemoryKnowledgeIndex, LocalEmbeddingClient
from support.assist_pitch import (
    citing_what_was_offered,
    data_block,
    pitch,
    refusing_client,
    scripted_client,
)
from support.assist_router import decision, refusing_router, scripted_router
from support.assist_world import PIECE, indexed_row, run
from support.fake_product_search import FakeProductSearch
from support.settings import build_settings

SETTINGS = dict(stub_mode=False, jpv_retrieval_distance_threshold=0.65)

CARE = "material-plata#cuidados-y-limpieza-en-casa"


def serve(search, knowledge, principal, *, payload, client=None, router=None, **kwargs):
    return run(
        assist_sale(
            AssistRequest(**payload),
            principal,
            settings=kwargs.pop("settings", None) or build_settings(**SETTINGS),
            embed=kwargs.pop("embed", None) or LocalEmbeddingClient(),
            search=search,
            knowledge=knowledge,
            pitch_client=client,
            router_client=router,
            **kwargs,
        )
    )


def _refusing_search() -> FakeProductSearch:
    """An index that fails the test if it is searched. For the two refusals and the clarification.

    The *point* of the guardrail is that it cuts **before** `retrieve_products`, so asserting it
    with a search that raises is asserting the property itself rather than a count read later.

    **Every method the retrieval orchestrator actually calls is covered, by name.** The first
    version of this double overrode `lexical_search`, which does not exist — the port calls
    `search_lexical` — so half the guard was a no-op nothing would have reported. A double that
    fails to fail is worse than no double at all.
    """

    class RefusingSearch(FakeProductSearch):
        async def search(self, *args, **kwargs):  # type: ignore[override]
            raise AssertionError("no product retrieval may run on this path")

        async def search_lexical(self, *args, **kwargs):  # type: ignore[override]
            raise AssertionError("no product retrieval may run on this path")

    return RefusingSearch([indexed_row()])


def _flat_family(count: int) -> FakeProductSearch:
    """`count` candidates at an identical distance: the flat profile the rule abstains on."""
    from uuid import UUID

    return FakeProductSearch(
        [
            indexed_row(
                product_id=UUID(f"aaaaaaaa-aaaa-4aaa-8aaa-{index:012d}"),
                sku=f"JBG-{index:04d}",
                distance=0.4,
                family_id=None,
                family_name=None,
            )
            for index in range(count)
        ]
    )


def _refusing_knowledge() -> InMemoryKnowledgeIndex:
    """A corpus index that fails the test if it is searched.

    **`search_knowledge` never calls a method named `search`.** It calls `vector_search`,
    `lexical_search` and `fetch_chunks`, and the first version of this double overrode only
    `search` — so the assertion «no knowledge search is executed» was **vacuous**: the double
    could not fire, and the index was empty anyway, so the test passed for the wrong reason.
    Found by the verification pass, which is exactly what it is for.
    """

    class RefusingKnowledge(InMemoryKnowledgeIndex):
        async def vector_search(self, *args, **kwargs):  # type: ignore[override]
            raise AssertionError("no knowledge search may run on this path")

        async def lexical_search(self, *args, **kwargs):  # type: ignore[override]
            raise AssertionError("no knowledge search may run on this path")

        async def fetch_chunks(self, *args, **kwargs):  # type: ignore[override]
            raise AssertionError("no knowledge search may run on this path")

    return RefusingKnowledge(chunks=())


def test_the_refusing_doubles_actually_refuse() -> None:
    """**The guard on the guards.** A double that cannot fire makes every test that uses it pass
    for the wrong reason, which is how the first version of `_refusing_knowledge` went unnoticed:
    it overrode a method `search_knowledge` never calls.

    This drives each double through the very call the production code makes and requires it to
    raise. If a port method is ever renamed, this fails here instead of silently disarming four
    guardrail tests somewhere else.
    """
    from uuid import uuid4

    search = _refusing_search()
    knowledge = _refusing_knowledge()

    for call in (
        lambda: search.search(
            embedding=[0.0] * 8, pos_id=uuid4(), top_k=5, distance_threshold=0.65
        ),
        lambda: search.search_lexical(groups=[], pos_id=uuid4(), top_k=5),
        lambda: knowledge.vector_search(embedding=[0.0] * 8, top_k=5),
        lambda: knowledge.lexical_search(groups=[], top_k=5),
        lambda: knowledge.fetch_chunks([]),
    ):
        with pytest.raises(AssertionError, match="may run on this path"):
            run(call())


# --- HU escenarios 1 and 2 · the two refusals, before any retrieval -------------------------


def test_an_out_of_domain_query_is_refused_before_anything_is_retrieved(principal) -> None:
    """HU escenario 1. 200, no groups, the verdict in `intent`, the code in `warnings[]`.

    The retrieval and the knowledge index both raise if reached, so "no retrieval was executed"
    is the property under test and not a claim about it.
    """
    router, provider = scripted_router(
        decision(served="out_of_domain", index=None, missing_axis=None)
    )
    client, pitch_provider = refusing_client()

    response = serve(
        _refusing_search(),
        _refusing_knowledge(),
        principal,
        payload={"query": "¿cuál es la capital de Australia?"},
        client=client,
        router=router,
    )

    assert provider.call_count == 1
    assert pitch_provider.calls == 0
    assert response.groups == []
    assert response.intent == INTENT_OUT_OF_DOMAIN
    assert response.warnings == [WARNING_QUERY_OUT_OF_DOMAIN]
    assert response.pitch == ""
    assert response.prompt_version is None
    assert response.abstained is False


def test_a_neighbouring_trade_request_is_refused_with_its_own_distinct_code(
    principal,
) -> None:
    """HU escenario 2. Jewellery-adjacent and this catalogue does not stock it.

    The code **differs** from the out-of-domain one, which is D1 as an assertion: a trade the
    shop does not practise and a piece it does not carry are two different things to say.
    """
    router, _ = scripted_router(
        decision(served="not_in_catalogue", index=None, missing_axis=None)
    )
    client, pitch_provider = refusing_client()

    response = serve(
        _refusing_search(),
        _refusing_knowledge(),
        principal,
        payload={"query": "un salero de plata"},
        client=client,
        router=router,
    )

    assert response.groups == []
    assert response.intent == INTENT_NOT_IN_CATALOGUE
    assert response.warnings == [WARNING_QUERY_NOT_IN_CATALOGUE]
    assert WARNING_QUERY_NOT_IN_CATALOGUE != WARNING_QUERY_OUT_OF_DOMAIN
    assert pitch_provider.calls == 0
    assert response.abstained is False


# --- HU escenario 14 · a refusal is never dressed as an abstention ---------------------------


@pytest.mark.parametrize("verdict", ["out_of_domain", "not_in_catalogue"])
def test_a_refused_request_does_not_claim_to_have_abstained(principal, verdict) -> None:
    """HU escenario 14 and D5. Two mechanisms, two fields, and the whole reason C31 exists is
    being able to publish the two rates as two numbers."""
    router, _ = scripted_router(decision(served=verdict, index=None))
    client, _ = refusing_client()

    response = serve(
        _refusing_search(),
        _refusing_knowledge(),
        principal,
        payload={"query": "algo"},
        client=client,
        router=router,
    )

    assert response.abstained is False
    assert response.intent != INTENT_UNCLASSIFIED
    assert len(response.warnings) == 1


def test_an_abstained_request_still_declares_its_abstention(
    knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    """The other half of D5: the abstention rule is untouched and still fires, **behind** the
    new gate. A query the router admits and the distance profile then distrusts is an
    abstention exactly as it was, with no refusal code beside it."""
    router, provider = scripted_router(decision(index="catalog"))
    client, pitch_provider = refusing_client()

    response = serve(
        _flat_family(20),
        knowledge,
        principal,
        payload={"query": "anillo de plata"},
        client=client,
        router=router,
    )

    assert provider.call_count == 1
    assert response.abstained is True
    assert response.groups == []
    assert response.intent == INTENT_IN_DOMAIN
    assert not set(response.warnings) & {
        WARNING_QUERY_OUT_OF_DOMAIN,
        WARNING_QUERY_NOT_IN_CATALOGUE,
    }
    assert pitch_provider.calls == 0


# --- HU escenarios 5 and 6 · the clarification question --------------------------------------


def test_an_ambiguous_query_is_answered_with_a_question_and_no_candidates(
    principal,
) -> None:
    """HU escenario 5. `clarification_question` non-null, in Spanish, no groups, no generation."""
    router, _ = scripted_router(decision(index="catalog", missing_axis="piece_type"))
    client, pitch_provider = refusing_client()

    response = serve(
        _refusing_search(),
        _refusing_knowledge(),
        principal,
        payload={"query": "algo bonito"},
        client=client,
        router=router,
    )

    assert response.clarification_question == CLARIFICATION_TEMPLATES["piece_type"]
    assert response.groups == []
    assert pitch_provider.calls == 0
    assert response.pitch == ""
    assert response.prompt_version is None
    assert response.abstained is False
    # The query was admitted: it is not a refusal, it is a request for one more fact.
    assert response.intent == INTENT_IN_DOMAIN
    assert response.warnings == []


@pytest.mark.parametrize("axis", sorted(CLARIFICATION_TEMPLATES))
def test_the_same_query_always_yields_the_same_clarification_text(principal, axis) -> None:
    """HU escenario 6. Two executions, identical text, and the template matches the axis."""
    texts = set()
    for _ in range(2):
        router, _ = scripted_router(decision(index="catalog", missing_axis=axis))
        client, _ = refusing_client()
        response = serve(
            _refusing_search(),
            _refusing_knowledge(),
            principal,
            payload={"query": "un regalo"},
            client=client,
            router=router,
        )
        texts.add(response.clarification_question)

    assert len(texts) == 1
    assert texts.pop() == CLARIFICATION_TEMPLATES[axis]


def test_an_admitted_and_sufficient_query_carries_no_clarification(
    search, knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    router, _ = scripted_router(decision(index="catalog"))
    client, _ = scripted_client(pitch("Es una pieza de plata que se lleva a diario."))

    response = serve(
        search,
        knowledge,
        principal,
        payload={"query": "un anillo de plata"},
        client=client,
        router=router,
    )

    assert response.clarification_question is None


# --- HU escenarios 7 and 8 · the anchored modes pay no classifier ----------------------------


def test_a_piece_with_no_question_makes_no_classifier_call(
    search, knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    """HU escenario 7. There is no query to classify, and the intent stays the one C30a fixed.

    The classifier raises if it is reached, so this is introspection over the control flow and
    not a reading of the code.
    """
    router, router_provider = refusing_router()
    client, provider = scripted_client(pitch("Es una pieza de plata muy llevadera."))

    response = serve(
        search,
        knowledge,
        principal,
        payload={"product_id": str(PIECE)},
        client=client,
        router=router,
    )

    assert router_provider.calls == 0
    assert response.intent == INTENT_PRODUCT_PITCH
    assert response.pitch
    assert response.prompt_version == PROMPT_VERSION
    assert provider.call_count == 1


def test_an_anchored_question_consults_both_indexes_and_makes_no_classifier_call(
    search, knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    """HU escenario 8. `both` by construction — the piece is the catalogue side and the question
    the corpus side — so refusing there would refuse a piece the caller named explicitly.

    The total provider calls for that request stay within the generation ceiling of two.
    """
    router, router_provider = refusing_router()
    client, provider = scripted_client(
        citing_what_was_offered(
            "La plata de ley aguanta bien el agua, aunque conviene secarla después.",
            "aguanta bien el agua",
        )
    )

    response = serve(
        search,
        knowledge,
        principal,
        payload={"product_id": str(PIECE), "query": "¿se puede mojar?"},
        client=client,
        router=router,
        knowledge_distance_threshold=0.99,
    )

    assert router_provider.calls == 0
    assert provider.call_count <= 2
    assert response.usage.total_tokens > 0
    assert response.groups
    assert response.citations
    assert response.intent == INTENT_UNCLASSIFIED


# --- HU escenario 9 · the free guardrail of the anchored question ----------------------------


def test_an_uncovered_anchored_question_is_declared_and_costs_no_extra_call(
    search, principal
) -> None:
    """HU escenario 9. Zero citations after the threshold already MEANS the corpus cannot
    answer: C23 measured the separation when it calibrated `0,51`. This reads the result that
    was already computed — no second search, no provider call — and publishes it as a code.

    The degraded task is what the model is handed, so the argument describes the piece instead
    of pretending to have answered.
    """
    empty = InMemoryKnowledgeIndex(chunks=())
    router, router_provider = refusing_router()
    client, provider = scripted_client(
        pitch("Es un anillo de plata de ley, cómodo para llevar a diario.")
    )

    response = serve(
        search,
        empty,
        principal,
        payload={"product_id": str(PIECE), "query": "¿esto sirve para bucear?"},
        client=client,
        router=router,
    )

    assert response.citations == []
    assert WARNING_KNOWLEDGE_NOT_COVERED in response.warnings
    assert router_provider.calls == 0
    # One generation call and nothing else: the guardrail is read off a computed result.
    assert provider.call_count == 1
    # The degraded task section, and not the one that answers a question.
    task_text = provider.user_of(0)
    assert TASK_SECTIONS[PitchTask.PIECE_AND_QUERY_UNCOVERED] not in task_text
    # The phrase wraps across a line in the prompt file, so match the half that does not.
    assert "no finjas haber" in task_text.casefold()
    assert "no traen ningún fragmento del corpus" in task_text.casefold()


def test_a_covered_anchored_question_raises_no_coverage_warning(
    search, knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    router, _ = refusing_router()
    client, _ = scripted_client(
        citing_what_was_offered("La plata se limpia en casa con un paño suave.", "paño suave")
    )

    response = serve(
        search,
        knowledge,
        principal,
        payload={"product_id": str(PIECE), "query": "¿cómo se limpia la plata?"},
        client=client,
        router=router,
        knowledge_distance_threshold=0.99,
    )

    assert response.citations
    assert WARNING_KNOWLEDGE_NOT_COVERED not in response.warnings


# --- HU escenarios 4 and 10 · the route decides what runs and what is written ----------------


def test_a_knowledge_question_is_routed_to_the_corpus_and_shows_no_pieces(
    knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    """HU escenario 4. Showing five pieces beside an answer about cleaning is noise, not help.

    The product index raises if it is reached, which is what makes "no catalogue candidates
    were retrieved" the property rather than an observation about an empty list.
    """
    router, _ = scripted_router(decision(index="knowledge"))
    client, provider = scripted_client(
        citing_what_was_offered(
            "La plata se empaña con el aire y se limpia en casa con un paño suave.",
            "se limpia en casa con un paño suave",
        )
    )

    response = serve(
        _refusing_search(),
        knowledge,
        principal,
        payload={"query": "¿por qué se pone negra la plata?"},
        client=client,
        router=router,
        knowledge_distance_threshold=0.99,
    )

    assert response.groups == []
    assert response.citations
    assert response.intent == INTENT_IN_DOMAIN
    assert response.pitch
    assert response.prompt_version == PROMPT_VERSION
    assert "no recomiendes ninguna pieza" in provider.user_of(0).casefold()


def test_a_catalogue_query_receives_an_argument_written_over_the_candidates(
    search, knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    """HU escenario 10. The free-query mode writes, and it writes with the task of its route."""
    router, _ = scripted_router(decision(index="catalog"))
    client, provider = scripted_client(
        pitch("Son piezas de plata de la misma familia, con dos tallas para elegir.")
    )

    response = serve(
        search,
        knowledge,
        principal,
        payload={"query": "un anillo de plata"},
        client=client,
        router=router,
    )

    assert response.groups
    assert response.pitch.startswith("Son piezas de plata")
    assert response.prompt_version == PROMPT_VERSION
    assert response.intent == INTENT_IN_DOMAIN
    assert "agrupadas por familia" in provider.user_of(0).casefold()


def test_the_both_route_consults_the_two_indexes_and_uses_its_own_task(
    search, knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    router, _ = scripted_router(decision(index="both"))
    client, provider = scripted_client(
        citing_what_was_offered(
            "La plata de ley se limpia en casa con un paño suave, y estas piezas son de plata.",
            "se limpia en casa con un paño suave",
        )
    )

    response = serve(
        search,
        knowledge,
        principal,
        payload={"query": "un anillo de plata que no se ponga negro"},
        client=client,
        router=router,
        knowledge_distance_threshold=0.99,
    )

    assert response.groups
    assert response.citations
    assert "piezas y fragmentos del corpus" in provider.user_of(0).casefold()


# --- HU escenario 11 · the numeric whitelist of the free-query mode --------------------------


def test_the_free_query_material_carries_no_internal_identifier_and_no_score(
    search, knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    """HU escenario 11, last clause. Every candidate widens the whitelist, so what is NOT in the
    payload is the containment: identifiers whose digits are arbitrary, and retrieval scores."""
    router, _ = scripted_router(decision(index="catalog"))
    client, provider = scripted_client(pitch("Son dos piezas de plata de la misma familia."))

    serve(
        search,
        knowledge,
        principal,
        payload={"query": "un anillo de plata"},
        client=client,
        router=router,
    )

    data = data_block(provider.user_of(0))
    rendered = provider.user_of(0)

    assert "candidatas" in data
    assert data["candidatas"]
    for group in data["candidatas"]:
        assert set(group) == {"familia", "piezas"}
        for piece in group["piezas"]:
            assert set(piece) == {"sku", "tipo", "materiales", "talla", "variante"}
            assert "product_id" not in piece
            assert "score" not in piece
    assert str(PIECE) not in rendered
    assert "family_id" not in rendered


def test_an_invented_figure_is_refused_in_the_free_query_mode_too(
    search, knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    """HU escenario 11. The same gate that governs the anchored modes, over the second shape.

    The repair is scripted to fail the same way, so what is asserted is the policy: a figure the
    material does not carry costs the whole argument.
    """
    invented = pitch("Estas piezas cuestan 47 euros y quedan 9 unidades.")
    router, _ = scripted_router(decision(index="catalog"))
    client, provider = scripted_client(invented, invented)

    response = serve(
        search,
        knowledge,
        principal,
        payload={"query": "un anillo de plata"},
        client=client,
        router=router,
    )

    assert provider.call_count == 2  # one generation and its single repair
    assert response.pitch == ""
    assert response.prompt_version == PROMPT_VERSION


def test_a_figure_present_in_the_free_query_material_is_admitted(
    knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    """The gate is a whitelist and not a blacklist: a size the candidates declare is writable."""
    router, _ = scripted_router(decision(index="catalog"))
    client, _ = scripted_client(
        pitch("Hay dos variantes de la misma pieza, la de 18 mm y la de 20 mm.")
    )
    from support.assist_world import SIBLING

    search = FakeProductSearch(
        [
            indexed_row(),
            indexed_row(product_id=SIBLING, sku="JBG-0002", variant_label="20 mm"),
        ]
    )

    response = serve(
        search,
        knowledge,
        principal,
        payload={"query": "un anillo de plata"},
        client=client,
        router=router,
    )

    assert "18 mm" in response.pitch


# --- HU escenarios 12 and 13 · the fail-open and the ceiling ---------------------------------


@pytest.mark.parametrize(
    "script",
    ["no soy json", '{"served": "inventada", "index": null, "missing_axis": null}'],
)
def test_a_classifier_fault_serves_the_answer_the_capability_served_before_it_routed(
    search, knowledge: InMemoryKnowledgeIndex, principal, script
) -> None:
    """HU escenario 12. **The worst case of a bad classifier is the behaviour of yesterday.**

    Both indexes are consulted, the abstention rule still applies, the intent is the honest
    unclassified one, and nothing is generated — which is exactly what this mode did before.
    """
    router, provider = scripted_router(script)
    client, pitch_provider = refusing_client()

    response = serve(
        search,
        knowledge,
        principal,
        payload={"query": "un anillo de plata"},
        client=client,
        router=router,
        knowledge_distance_threshold=0.99,
    )

    assert provider.call_count == 1
    assert response.intent == INTENT_UNCLASSIFIED
    assert response.groups
    assert response.citations
    assert response.abstained is False
    assert response.warnings == [] or set(response.warnings) <= {
        "family_has_variants",
        "size_label_missing",
    }
    assert pitch_provider.calls == 0
    assert response.pitch == ""
    assert response.prompt_version is None


def test_no_classifier_credential_is_a_valid_deployment_state(
    search, knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    """HU escenario 17, last clause. No client is not a failure: it is the rollback."""
    client, pitch_provider = refusing_client()

    response = serve(
        search,
        knowledge,
        principal,
        payload={"query": "un anillo de plata"},
        client=client,
        router=None,
        knowledge_distance_threshold=0.99,
    )

    assert response.intent == INTENT_UNCLASSIFIED
    assert response.groups
    assert response.citations
    assert pitch_provider.calls == 0
    assert response.usage.total_tokens == 0
    assert response.usage.model is None


def test_the_degradation_and_its_cause_reach_the_request_log(
    search, knowledge: InMemoryKnowledgeIndex, principal, caplog
) -> None:
    """HU escenario 12, last clause, at the orchestrator's own line."""
    router, _ = scripted_router("no soy json")

    with caplog.at_level(logging.INFO):
        serve(
            search,
            knowledge,
            principal,
            payload={"query": "un anillo de plata"},
            router=router,
        )

    emitted = "\n".join(record.getMessage() for record in caplog.records)
    assert "router_degraded=True" in emitted
    assert "router_cause=parse" in emitted
    assert "un anillo de plata" not in emitted


def test_a_routed_generated_and_repaired_request_makes_exactly_three_calls(
    search, knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    """HU escenario 13. **The ceiling is literal and observable from the usage object.**

    One classification, one generation that violates the gate, one repair that fixes it: three,
    and never more. `usage` accumulates all three, which is what makes the ceiling a property a
    consumer can read rather than an intention stated in a document.
    """
    good = pitch("Son piezas de plata, cómodas de llevar a diario.")
    bad = pitch("Estas piezas cuestan 47 euros.")
    router, router_provider = scripted_router(decision(index="catalog"))
    client, provider = scripted_client(bad, good)

    response = serve(
        search,
        knowledge,
        principal,
        payload={"query": "un anillo de plata"},
        client=client,
        router=router,
    )

    assert router_provider.call_count == 1
    assert provider.call_count == 2
    assert response.usage.total_tokens > 0
    assert response.pitch.startswith("Son piezas de plata")

    # The observable side of the ceiling: the accumulated call count of the whole request.
    from jbg_ai.assist.llm import TokenUsage

    assert MAX_PROVIDER_CALLS == 3
    accumulated = TokenUsage(calls=1) + TokenUsage(calls=1) + TokenUsage(calls=1)
    assert accumulated.calls == MAX_PROVIDER_CALLS


def test_the_usage_of_a_routed_request_accumulates_the_classifier_too(
    search, knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    """A usage that left the classifier out would report two calls on a request that made three,
    and would understate the cost of exactly the requests that cost the most."""
    router, _ = scripted_router(decision(index="catalog"))
    client, _ = scripted_client(pitch("Son piezas de plata, cómodas de llevar a diario."))

    routed = serve(
        search,
        knowledge,
        principal,
        payload={"query": "un anillo de plata"},
        client=client,
        router=router,
    )

    client_only, _ = scripted_client(pitch("Es una pieza de plata muy llevadera."))
    anchored = serve(
        search,
        knowledge,
        principal,
        payload={"product_id": str(PIECE)},
        client=client_only,
        router=None,
    )

    # The routed request paid the classifier on top of the generation; the anchored one did not.
    assert routed.usage.total_tokens > anchored.usage.total_tokens
    assert routed.usage.prompt_tokens >= 1500 + 700


# --- los dos escenarios que la pasada de verificación encontró sin cobertura literal --------


def test_an_unknown_label_never_appears_anywhere_in_the_response(
    search, knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    """Spec: «A label outside the vocabulary never reaches the response».

    La mitad «degrada a `unclassified`» ya estaba cubierta; **la mitad «la etiqueta desconocida
    no aparece en la respuesta» no lo estaba**, y es la que importa: un valor que no parsea pero
    se filtra a un campo cualquiera sería exactamente el fallo que el `Literal` existe para
    impedir. Se comprueba sobre el **volcado entero** de la respuesta, no sobre `intent`.
    """
    router, _ = scripted_router(
        '{"served": "inventada", "index": "inventado", "missing_axis": "inventado"}'
    )

    response = serve(
        search,
        knowledge,
        principal,
        payload={"query": "un anillo de plata"},
        router=router,
        knowledge_distance_threshold=0.99,
    )

    assert response.intent == INTENT_UNCLASSIFIED
    assert "inventad" not in response.model_dump_json()


def test_the_reported_intent_always_belongs_to_the_closed_vocabulary(
    search, knowledge: InMemoryKnowledgeIndex, principal
) -> None:
    """Spec: «The reported value MUST belong to a closed vocabulary declared by this capability».

    Recorrido sobre **los tres veredictos, la repregunta, el fail-open y los dos modos
    anclados**: siete caminos, y ninguno puede emitir un valor de fuera del vocabulario.
    """
    from jbg_ai.assist.constants import ASSIST_INTENTS

    casos = [
        (decision(index="catalog"), {"query": "un anillo de plata"}),
        (decision(index="knowledge"), {"query": "¿cómo se limpia la plata?"}),
        (decision(index="both"), {"query": "un anillo de plata que no se ponga negro"}),
        (decision(index="catalog", missing_axis="piece_type"), {"query": "algo bonito"}),
        (decision(served="out_of_domain", index=None), {"query": "la capital de Australia"}),
        (decision(served="not_in_catalogue", index=None), {"query": "un salero de plata"}),
        ("no soy json", {"query": "un anillo de plata"}),
    ]
    vistos = set()
    for guion, payload in casos:
        router, _ = scripted_router(guion)
        response = serve(
            search,
            knowledge,
            principal,
            payload=payload,
            router=router,
            knowledge_distance_threshold=0.99,
        )
        assert response.intent in ASSIST_INTENTS, (payload, response.intent)
        vistos.add(response.intent)

    for payload in ({"product_id": str(PIECE)}, {"product_id": str(PIECE), "query": "¿se moja?"}):
        router, router_provider = refusing_router()
        response = serve(
            search,
            knowledge,
            principal,
            payload=payload,
            router=router,
            knowledge_distance_threshold=0.99,
        )
        assert router_provider.calls == 0
        assert response.intent in ASSIST_INTENTS
        vistos.add(response.intent)

    # Los cinco valores del vocabulario son alcanzables: ninguno es decorativo.
    assert vistos == set(ASSIST_INTENTS)
