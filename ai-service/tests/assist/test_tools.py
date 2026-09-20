"""The sale assistant's tool registry and its invariants. C32a.

Offline like the rest of this suite: no chat provider, no embedding provider, no database.
The ports go in through the constructor seam `build_registry` already requires, which is what
makes the two structural properties — the frozen set and the read-only invariant — testable at
all rather than asserted in a document.

The nine acceptance scenarios of HU-AIENG-032a are traced from here; each test that carries one
names it in its docstring so the mapping survives a rename.
"""

from __future__ import annotations

import dataclasses
from uuid import UUID

import pytest

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.main import create_app
from jbg_ai.assist import constants
from jbg_ai.assist.constants import (
    AVAILABILITY_LABEL_BY_BUCKET,
    AVAILABILITY_LABELS,
    AVAILABILITY_NO_SCOPE,
    AVAILABILITY_OUT_OF_STOCK,
    TOOL_CAUSE_DEPENDENCY_UNAVAILABLE,
    TOOL_CAUSE_INVALID_ARGUMENT,
    TOOL_CAUSE_UNKNOWN_REFERENCE,
    TOOL_CAUSE_UNUSABLE_REFERENCE,
    TOOL_FAILURE_CAUSES,
    TOOL_NAMES,
    TOOL_TOP_K_MAX,
    TOOL_TOP_K_MIN,
    WITHDRAWN_TOOL_NAMES,
)
from jbg_ai.assist.routing import CLARIFICATION_TEMPLATES, clarification_axes
from jbg_ai.assist.tools import (
    CountingEmbeddings,
    ToolRegistry,
    ToolRegistryError,
    build_registry,
    captured_collaborators,
    http_write_verbs_of,
    write_methods_of,
)
from jbg_ai.indexing.feed import QTY_BUCKETS
from jbg_ai.knowledge.offline import InMemoryKnowledgeIndex
from jbg_ai.retrieval.errors import RetrievalDependencyError
from support.assist_world import FAMILY, LONER, PIECE, indexed_row, run
from support.fake_embedding_client import FakeEmbeddingClient
from support.fake_product_search import FakeAssignment, FakeProductSearch
from support.settings import TOKEN_POS_ID, TOKEN_TRACE_ID, build_settings

#: Every tool, with arguments that are valid for it against the world the fixtures describe.
#: Held as data rather than repeated per test, so "exercise the whole registry" is a loop and
#: a seventh tool cannot be added without appearing here.
EVERY_TOOL: tuple[tuple[str, dict[str, object]], ...] = (
    ("buscar_catalogo", {"consulta": "anillo de plata"}),
    ("buscar_sustitutos", {"sku": "JBG-0001"}),
    ("listar_familia", {"sku": "JBG-0001"}),
    ("consultar_conocimiento", {"pregunta": "¿como limpio la plata?", "sku": "JBG-0001"}),
    ("consultar_disponibilidad", {"sku": "JBG-0001"}),
    ("pedir_aclaracion", {"eje": "material"}),
)


def make_registry(
    *,
    search: FakeProductSearch,
    knowledge: InMemoryKnowledgeIndex,
    principal: ServicePrincipal,
    embed: FakeEmbeddingClient | None = None,
) -> ToolRegistry:
    """One registry over injected fakes. No port is constructed and no socket is opened."""
    return build_registry(
        principal=principal,
        settings=build_settings(),
        embed=embed or FakeEmbeddingClient(),
        search=search,
        knowledge=knowledge,
    )


@pytest.fixture
def registry(
    search: FakeProductSearch,
    knowledge: InMemoryKnowledgeIndex,
    principal: ServicePrincipal,
) -> ToolRegistry:
    return make_registry(search=search, knowledge=knowledge, principal=principal)


# --- escenario 1 · el conjunto congelado ------------------------------------------------------


def test_the_registry_holds_exactly_the_six_frozen_tools(registry: ToolRegistry) -> None:
    """HU escenario 1. Six entries, the declared names, and neither of the two withdrawn."""
    assert len(registry) == 6
    assert set(registry.names()) == set(TOOL_NAMES)
    for withdrawn in WITHDRAWN_TOOL_NAMES:
        assert withdrawn not in registry


def test_every_registered_tool_publishes_a_schema_and_a_spanish_description(
    registry: ToolRegistry,
) -> None:
    """HU escenario 1, second half: a valid parameter schema and a description for a reader."""
    for spec in registry.specs():
        schema = spec.schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == spec.name
        parameters = schema["function"]["parameters"]
        assert parameters["type"] == "object"
        assert parameters["additionalProperties"] is False
        assert isinstance(parameters.get("properties"), dict) and parameters["properties"]
        # The description is the interface the model reads to choose, so an empty one is a
        # tool that cannot be chosen for the right reason.
        assert len(spec.description) > 40


def test_a_tool_outside_the_frozen_set_is_refused_at_construction(
    registry: ToolRegistry,
) -> None:
    """A seventh tool fails the build rather than being silently accepted."""
    seventh = dataclasses.replace(registry.get("listar_familia"), name="perfil_punto_venta")
    with pytest.raises(ToolRegistryError, match="frozen"):
        ToolRegistry(
            (*registry.specs(), seventh),
            embeddings=CountingEmbeddings(FakeEmbeddingClient()),
        )


def test_a_registry_missing_one_of_the_six_is_refused_at_construction(
    registry: ToolRegistry,
) -> None:
    """The frozen set is an equality and not a ceiling: five tools is as wrong as seven."""
    with pytest.raises(ToolRegistryError, match="frozen"):
        ToolRegistry(
            registry.specs()[:-1],
            embeddings=CountingEmbeddings(FakeEmbeddingClient()),
        )


# --- escenario 2 · el invariante de solo lectura ------------------------------------------------


def test_no_collaborator_captured_by_a_tool_exposes_a_write_method(
    registry: ToolRegistry,
) -> None:
    """HU escenario 2. The first axis, over the object graph the registry actually holds."""
    for spec in registry.specs():
        for collaborator in captured_collaborators(spec):
            assert write_methods_of(collaborator) == [], (
                f"{spec.name} captures {type(collaborator).__name__}"
            )


def test_no_collaborator_captured_by_a_tool_can_issue_a_write_http_verb(
    registry: ToolRegistry,
) -> None:
    """HU escenario 2, third axis: what a registered client CAN issue, not what it does."""
    for spec in registry.specs():
        for collaborator in captured_collaborators(spec):
            assert http_write_verbs_of(collaborator) == []


def test_the_read_only_check_reaches_every_port_the_registry_was_handed(
    registry: ToolRegistry,
) -> None:
    """A check that found nothing to inspect would pass vacuously, which is worse than failing.

    Pins the seam rather than the count: every tool that consults an index must be seen to
    capture it, or the two assertions above are green over an empty list.

    `InMemoryKnowledgeIndex` is named here for a reason that cost a verification pass. It is a
    dataclass, and an earlier form of `_is_collaborator` excluded dataclasses wholesale, so the
    knowledge port — the only real collaborator `consultar_conocimiento` has — fell out of all
    three axes while every assertion stayed green. A port is inspected whatever it is built
    from; this line is what keeps that true.
    """
    captured = {
        spec.name: sorted(type(item).__name__ for item in captured_collaborators(spec))
        for spec in registry.specs()
    }
    assert "FakeProductSearch" in captured["buscar_catalogo"]
    assert "FakeProductSearch" in captured["consultar_disponibilidad"]
    assert "CountingEmbeddings" in captured["consultar_conocimiento"]
    assert "InMemoryKnowledgeIndex" in captured["consultar_conocimiento"]
    # The clarification tool resolves a template from a closed catalogue and consults nothing.
    assert captured["pedir_aclaracion"] == []


class _WritingProjectionPort:
    """A port that can write. Registered by the test below and by nothing else.

    It mirrors the shape a future point-of-sale writer would plausibly have — the very thing
    the published limitation says does not exist — so the check is exercised against the case
    it was built for instead of against a synthetic name.
    """

    async def availability_bucket(self, product_id: UUID, *, pos_id: UUID) -> str | None:
        return "3+"

    async def save_availability(self, product_id: UUID, *, pos_id: UUID, bucket: str) -> None:
        raise AssertionError("never called: construction must refuse this port first")


def test_a_tool_capturing_a_writing_port_is_refused_however_it_describes_itself(
    registry: ToolRegistry,
) -> None:
    """HU escenario 2, last clause. The descriptor's own claims change nothing."""
    writer = _WritingProjectionPort()

    async def _run(_args: object) -> dict[str, object]:
        # Captures the writing port in its closure, which is what the check inspects.
        return {"bucket": await writer.availability_bucket(PIECE, pos_id=PIECE)}

    original = registry.get("consultar_disponibilidad")
    tampered = dataclasses.replace(
        original,
        description=original.description + " Esta herramienta no escribe nada en absoluto.",
        run=_run,
    )
    specs = tuple(
        tampered if spec.name == "consultar_disponibilidad" else spec
        for spec in registry.specs()
    )
    with pytest.raises(ToolRegistryError, match="write methods"):
        ToolRegistry(specs, embeddings=CountingEmbeddings(FakeEmbeddingClient()))


def test_the_write_vocabulary_catches_every_natural_spelling_of_a_write() -> None:
    """Token equality, and what it does and does not catch, pinned as behaviour.

    `projection_synced_at` and `synced_at` are reads of a checkpoint that a substring match on
    `sync` would flag, which is why the matching rule is token equality — and why that rule is
    pinned here rather than left to be rediscovered.
    """

    class _Surface:
        def save_profile(self) -> None: ...
        def bulk_insert(self) -> None: ...
        def upsert_projection(self) -> None: ...
        def delete_row(self) -> None: ...
        def sync_now(self) -> None: ...
        def apply_changes(self) -> None: ...
        def projection_synced_at(self) -> None: ...
        def synced_at(self) -> None: ...
        def count_scope(self) -> None: ...
        def availability_bucket(self) -> None: ...

    assert write_methods_of(_Surface()) == [
        "apply_changes",
        "bulk_insert",
        "delete_row",
        "save_profile",
        "sync_now",
        "upsert_projection",
    ]


# --- escenario 3 · un fallo de dependencia vuelve como observación -------------------------------


class _FailingSearch(FakeProductSearch):
    """A port whose reads all fail, the way an unreachable database fails."""

    async def document_by_sku(self, sku: str):  # type: ignore[override]
        raise RetrievalDependencyError("database query failed: connection refused")

    async def availability_bucket(self, product_id: UUID, *, pos_id: UUID):  # type: ignore[override]
        raise RetrievalDependencyError("database query failed: connection refused")


def test_a_dependency_failure_comes_back_as_a_failed_observation_and_not_an_exception(
    knowledge: InMemoryKnowledgeIndex, principal: ServicePrincipal
) -> None:
    """HU escenario 3. No exception reaches the caller and the cause says what happened."""
    registry = make_registry(
        search=_FailingSearch([indexed_row()]), knowledge=knowledge, principal=principal
    )
    observation = run(registry.invoke("consultar_disponibilidad", {"sku": "JBG-0001"}))

    assert observation.ok is False
    assert observation.cause == TOOL_CAUSE_DEPENDENCY_UNAVAILABLE
    assert observation.cause in TOOL_FAILURE_CAUSES


def test_a_failure_cause_is_always_a_code_of_the_closed_vocabulary(
    knowledge: InMemoryKnowledgeIndex, principal: ServicePrincipal
) -> None:
    """Never prose: the consumer branches on the cause, so an unbounded string is useless."""
    registry = make_registry(
        search=_FailingSearch([indexed_row()]), knowledge=knowledge, principal=principal
    )
    for name, arguments in EVERY_TOOL:
        observation = run(registry.invoke(name, arguments))
        if not observation.ok:
            assert observation.cause in TOOL_FAILURE_CAUSES, name


def test_an_unknown_tool_name_is_an_observation_and_not_an_exception(
    registry: ToolRegistry,
) -> None:
    """A model that invents a tool name must cost the loop a turn, never kill it."""
    observation = run(registry.invoke("herramienta_inventada", {}))

    assert observation.ok is False
    assert observation.cause == TOOL_CAUSE_UNKNOWN_REFERENCE


# --- escenario 4 · la disponibilidad se responde con etiqueta y nunca con cifra ------------------


def test_no_availability_label_contains_a_digit() -> None:
    """HU escenario 4. The vocabulary itself, before any tool runs."""
    for label in AVAILABILITY_LABELS:
        assert not any(character.isdigit() for character in label), label


def test_every_bucket_the_feed_can_store_has_a_label() -> None:
    """The map covers the feed's whole vocabulary, compared against the feed's own constant.

    `constants.py` imports nothing, so the keys are written out there; this is where that
    duplication is made to fail loudly if the feed ever gains a fourth bucket.
    """
    assert set(AVAILABILITY_LABEL_BY_BUCKET) == set(QTY_BUCKETS)
    # No label is a bucket value: the whole point of the mapping is that the numerals stop here.
    assert not set(AVAILABILITY_LABEL_BY_BUCKET.values()) & set(QTY_BUCKETS)
    # «Sin ámbito» is never derived from a bucket; it is the absence of one.
    assert AVAILABILITY_NO_SCOPE not in AVAILABILITY_LABEL_BY_BUCKET.values()


@pytest.mark.parametrize(
    ("bucket", "expected"),
    [("0", "sin_existencias"), ("1-2", "ultimas_unidades"), ("3+", "disponible")],
)
def test_availability_answers_with_the_label_of_the_stored_bucket(
    bucket: str,
    expected: str,
    knowledge: InMemoryKnowledgeIndex,
    principal: ServicePrincipal,
) -> None:
    """HU escenario 4. Each stored bucket reaches its band, and the band is what travels."""
    search = FakeProductSearch(
        [indexed_row()],
        assignments=[
            FakeAssignment(
                pos_id=UUID(TOKEN_POS_ID), product_id=PIECE, qty_bucket=bucket
            )
        ],
    )
    registry = make_registry(search=search, knowledge=knowledge, principal=principal)
    observation = run(registry.invoke("consultar_disponibilidad", {"sku": "JBG-0001"}))

    assert observation.ok is True
    assert observation.content["disponibilidad"] == expected


def test_the_availability_observation_carries_no_stock_quantity_anywhere(
    registry: ToolRegistry,
) -> None:
    """HU escenario 4. Not only the label: no bucket value appears anywhere in the observation."""
    observation = run(registry.invoke("consultar_disponibilidad", {"sku": "JBG-0001"}))

    label = observation.content["disponibilidad"]
    assert label in AVAILABILITY_LABELS
    assert not any(character.isdigit() for character in str(label))
    # The buckets are numerals; none of them may appear as a value ANYWHERE in the observation.
    # Walked with `_rows_of` rather than over the top-level values, so the assertion still holds
    # if this observation ever grows a nested row — the shape is not what the rule is about.
    emitted = {
        str(value) for row in _rows_of(observation.content) for value in row.values()
    }
    assert not emitted & set(QTY_BUCKETS)


def test_the_availability_observation_declares_the_age_of_the_projection(
    registry: ToolRegistry,
) -> None:
    """HU escenario 4. Freshness travels with the label, taken from the drain checkpoint."""
    observation = run(registry.invoke("consultar_disponibilidad", {"sku": "JBG-0001"}))

    age = observation.content["antiguedad_proyeccion_segundos"]
    assert isinstance(age, float)
    assert age >= 0.0


def test_a_stale_projection_still_answers_and_carries_its_age(
    knowledge: InMemoryKnowledgeIndex, principal: ServicePrincipal
) -> None:
    """Degrade, never remove: an old reading is reported with its age and does not fail."""
    from datetime import UTC, datetime, timedelta

    stale = datetime.now(tz=UTC) - timedelta(hours=9)
    search = FakeProductSearch([indexed_row()], synced_at=stale)
    registry = make_registry(search=search, knowledge=knowledge, principal=principal)
    observation = run(registry.invoke("consultar_disponibilidad", {"sku": "JBG-0001"}))

    assert observation.ok is True
    assert observation.content["disponibilidad"] in AVAILABILITY_LABELS
    assert observation.content["antiguedad_proyeccion_segundos"] > 3600.0


# --- escenario 5 · «sin ámbito» no es «agotado» -------------------------------------------------


def test_a_principal_with_no_point_of_sale_gets_the_unscoped_value(
    search: FakeProductSearch, knowledge: InMemoryKnowledgeIndex
) -> None:
    """HU escenario 5. No reading scope is stated as such and never as an absence of stock."""
    unscoped = ServicePrincipal(
        user_id="u-1", role="Operator", trace_id=TOKEN_TRACE_ID, pos_id=None
    )
    registry = make_registry(search=search, knowledge=knowledge, principal=unscoped)
    observation = run(registry.invoke("consultar_disponibilidad", {"sku": "JBG-0001"}))

    assert observation.ok is True
    assert observation.content["disponibilidad"] == AVAILABILITY_NO_SCOPE
    assert observation.content["disponibilidad"] != AVAILABILITY_OUT_OF_STOCK


def test_a_piece_the_point_of_sale_does_not_carry_is_not_reported_as_out_of_stock(
    knowledge: InMemoryKnowledgeIndex, principal: ServicePrincipal
) -> None:
    """HU escenario 5. Absence of a projection row is not a bucket of zero."""
    carried = FakeProductSearch(
        [indexed_row()],
        assignments=[
            FakeAssignment(pos_id=UUID(TOKEN_POS_ID), product_id=PIECE, qty_bucket="0")
        ],
    )
    not_carried = FakeProductSearch([indexed_row()], assignments=[])

    genuinely_empty = run(
        make_registry(
            search=carried, knowledge=knowledge, principal=principal
        ).invoke("consultar_disponibilidad", {"sku": "JBG-0001"})
    )
    absent_row = run(
        make_registry(
            search=not_carried, knowledge=knowledge, principal=principal
        ).invoke("consultar_disponibilidad", {"sku": "JBG-0001"})
    )

    assert genuinely_empty.content["disponibilidad"] == AVAILABILITY_OUT_OF_STOCK
    assert absent_row.content["disponibilidad"] == AVAILABILITY_NO_SCOPE
    # Distinguishable by their consumer, which is the whole requirement.
    assert (
        absent_row.content["disponibilidad"] != genuinely_empty.content["disponibilidad"]
    )


# --- escenario 6 · la repregunta elige eje y el castellano lo escribe el código -------------------


def test_the_same_axis_always_produces_the_same_question(registry: ToolRegistry) -> None:
    """HU escenario 6. Two invocations, one text, taken from the closed catalogue verbatim."""
    for axis in clarification_axes():
        first = run(registry.invoke("pedir_aclaracion", {"eje": axis}))
        second = run(registry.invoke("pedir_aclaracion", {"eje": axis}))

        assert first.ok is True
        assert first.content["pregunta"] == CLARIFICATION_TEMPLATES[axis]
        assert second.content["pregunta"] == first.content["pregunta"]


def test_an_axis_outside_the_closed_set_is_rejected_before_execution(
    registry: ToolRegistry,
) -> None:
    """HU escenario 6. The validation refuses it and no question text is produced."""
    observation = run(registry.invoke("pedir_aclaracion", {"eje": "color_favorito"}))

    assert observation.ok is False
    assert observation.cause == TOOL_CAUSE_INVALID_ARGUMENT
    assert observation.content == {}


def test_the_clarification_schema_publishes_the_axes_of_the_closed_catalogue(
    registry: ToolRegistry,
) -> None:
    """The enum a model reads and the catalogue the answer resolves from are one source."""
    parameters = registry.get("pedir_aclaracion").schema()["function"]["parameters"]

    assert parameters["properties"]["eje"]["enum"] == list(clarification_axes())


# --- escenario 7 · direccionamiento por SKU ------------------------------------------------------


def test_a_piece_anchored_tool_resolves_the_piece_from_its_sku(
    registry: ToolRegistry, search: FakeProductSearch
) -> None:
    """HU escenario 7. The SKU is the address, and the read goes through the SKU door."""
    observation = run(registry.invoke("listar_familia", {"sku": "JBG-0001"}))

    assert observation.ok is True
    assert observation.content["pieza"] == "JBG-0001"
    assert search.document_by_sku_calls == ["JBG-0001"]
    assert [member["sku"] for member in observation.content["miembros"]] == [
        "JBG-0001",
        "JBG-0002",
    ]


def test_an_unknown_sku_is_a_failed_observation_with_its_cause(
    registry: ToolRegistry,
) -> None:
    """HU escenario 7. Unknown reference, no exception, and a cause that says which."""
    for name in ("listar_familia", "consultar_disponibilidad", "buscar_sustitutos"):
        observation = run(registry.invoke(name, {"sku": "JBG-NO-EXISTE"}))

        assert observation.ok is False, name
        assert observation.cause == TOOL_CAUSE_UNKNOWN_REFERENCE, name


def test_a_discontinued_piece_is_told_apart_from_an_unknown_one(
    knowledge: InMemoryKnowledgeIndex, principal: ServicePrincipal
) -> None:
    """Two different next moves for the consumer, so two different codes."""
    search = FakeProductSearch([indexed_row(is_active=False)])
    registry = make_registry(search=search, knowledge=knowledge, principal=principal)
    observation = run(registry.invoke("listar_familia", {"sku": "JBG-0001"}))

    assert observation.ok is False
    assert observation.cause == TOOL_CAUSE_UNUSABLE_REFERENCE


def test_no_tool_schema_declares_an_internal_product_identifier(
    registry: ToolRegistry,
) -> None:
    """HU escenario 7, last clause. An internal identifier is never a parameter."""
    forbidden = {"product_id", "producto_id", "id_producto", "uuid", "id"}
    for spec in registry.specs():
        properties = spec.schema()["function"]["parameters"]["properties"]
        assert not set(properties) & forbidden, spec.name


def test_no_observation_carries_a_raw_score_or_an_internal_identifier(
    registry: ToolRegistry,
) -> None:
    """Bounded observations: ordering travels as a position, never as a comparable number."""
    banned_keys = {"score", "distance", "distancia", "similarity", "product_id", "id"}
    for name, arguments in EVERY_TOOL:
        observation = run(registry.invoke(name, arguments))
        assert observation.ok is True, name
        for row in _rows_of(observation.content):
            assert not set(row) & banned_keys, (name, sorted(row))
        assert str(PIECE) not in repr(observation.content), name


def test_ordering_travels_as_a_position(registry: ToolRegistry) -> None:
    """Where several candidates are returned, the order is stated and is not inferred."""
    observation = run(registry.invoke("buscar_catalogo", {"consulta": "anillo de plata"}))
    candidates = observation.content["candidatos"]

    assert len(candidates) >= 2
    assert [item["posicion"] for item in candidates] == list(
        range(1, len(candidates) + 1)
    )


def _rows_of(content: object) -> list[dict[str, object]]:
    """Every mapping inside an observation, so a check can walk it without knowing its shape."""
    rows: list[dict[str, object]] = []
    if isinstance(content, dict):
        rows.append(content)
        for value in content.values():
            rows.extend(_rows_of(value))
    elif isinstance(content, (list, tuple)):
        for value in content:
            rows.extend(_rows_of(value))
    return rows


# --- escenario 8 · la mitad sin proveedor --------------------------------------------------------


def test_every_tool_produces_its_observation_with_no_chat_provider_configured(
    search: FakeProductSearch,
    knowledge: InMemoryKnowledgeIndex,
    principal: ServicePrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HU escenario 8. No credential anywhere, and all six still answer."""
    for variable in (
        "JPV_ASSIST_LLM_API_KEY",
        "JPV_RAG_LLM_API_KEY",
        "JPV_ROUTER_LLM_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(variable, raising=False)

    registry = make_registry(search=search, knowledge=knowledge, principal=principal)
    for name, arguments in EVERY_TOOL:
        observation = run(registry.invoke(name, arguments))
        assert observation.ok is True, f"{name} did not produce an observation"


def test_no_tool_calls_a_chat_provider(
    search: FakeProductSearch,
    knowledge: InMemoryKnowledgeIndex,
    principal: ServicePrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HU escenario 8. Any completion attempt is a failure, and none is attempted."""
    import litellm

    def _forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a tool called a chat completion provider")

    monkeypatch.setattr(litellm, "acompletion", _forbidden, raising=False)
    monkeypatch.setattr(litellm, "completion", _forbidden, raising=False)

    registry = make_registry(search=search, knowledge=knowledge, principal=principal)
    for name, arguments in EVERY_TOOL:
        assert run(registry.invoke(name, arguments)).ok is True, name


def test_embedding_calls_are_counted_in_a_counter_of_their_own(
    search: FakeProductSearch,
    knowledge: InMemoryKnowledgeIndex,
    principal: ServicePrincipal,
) -> None:
    """HU escenario 8. Visible, and kept apart from the chat-call figure of the assist layer."""
    embed = FakeEmbeddingClient()
    registry = make_registry(
        search=search, knowledge=knowledge, principal=principal, embed=embed
    )
    assert registry.embedding_calls == 0

    run(registry.invoke("buscar_catalogo", {"consulta": "anillo de plata"}))
    assert registry.embedding_calls >= 1

    # The tools that consult no index pay no embedding at all, which is what makes this a
    # counter of embeddings rather than a counter of invocations.
    before = registry.embedding_calls
    run(registry.invoke("pedir_aclaracion", {"eje": "price"}))
    run(registry.invoke("consultar_disponibilidad", {"sku": "JBG-0001"}))
    assert registry.embedding_calls == before


def test_the_assistance_layer_provider_call_figure_is_untouched_by_this_capability() -> None:
    """The published `usage.calls` still means chat calls of one request, and its ceiling holds."""
    assert constants.MAX_PITCH_PROVIDER_CALLS == 2
    assert constants.MAX_ROUTER_PROVIDER_CALLS == 1
    # Nothing in the tool vocabulary redefines either figure.
    assert not hasattr(constants, "MAX_TOOL_PROVIDER_CALLS")


# --- escenario 9 · fuera de alcance explícito: aquí no hay bucle ----------------------------------


def test_the_registry_publishes_no_route_and_declares_no_iteration_budget() -> None:
    """HU escenario 9. No agent route exists and no budget of turns is declared anywhere."""
    # Read from the generated document rather than from `app.routes`, because the document is
    # the thing the frozen snapshot is compared against.
    paths = set(create_app(build_settings()).openapi()["paths"])
    assert "/v1/assist/agent" not in paths
    assert not [path for path in paths if "agent" in path]

    from jbg_ai.assist import tools

    budgets = [
        name
        for name in dir(tools)
        if any(word in name.upper() for word in ("MAX_ITERATION", "BUDGET", "MAX_TURNS"))
    ]
    assert budgets == []


def test_the_sale_assistance_response_shape_is_the_one_the_router_change_left() -> None:
    """HU escenario 9. No field added to the published contract and none changed."""
    from jbg_ai.api.schemas.assist import AssistResponse

    assert set(AssistResponse.model_fields) == {
        "trace_id",
        "effective_pos_id",
        "intent",
        "groups",
        "warnings",
        "citations",
        "abstained",
        "pitch",
        "prompt_version",
        "clarification_question",
        "usage",
    }


# --- los tests corren sin red ----------------------------------------------------------------------


def test_the_whole_registry_runs_with_no_socket_available(
    search: FakeProductSearch,
    knowledge: InMemoryKnowledgeIndex,
    principal: ServicePrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every tool answers with the socket module refusing to connect at all.

    The loop is built **before** the guard goes up, and that ordering is the whole subtlety:
    on Windows the proactor loop opens a loopback `socketpair` for its own wake-up pipe, so a
    guard installed first fails the test on asyncio's plumbing rather than on a tool reaching
    out. `tests/api/test_health_report.py` records the same ordering rule for the same reason.
    """
    import asyncio
    import socket

    loop = asyncio.new_event_loop()
    try:

        def _fail(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("a tool opened a network connection")

        monkeypatch.setattr(socket.socket, "connect", _fail)
        monkeypatch.setattr(socket, "create_connection", _fail)

        registry = make_registry(search=search, knowledge=knowledge, principal=principal)
        for name, arguments in EVERY_TOOL:
            assert loop.run_until_complete(registry.invoke(name, arguments)).ok is True, name
    finally:
        loop.close()


# --- la validación de argumentos ocurre antes de tocar un puerto -------------------------------------


def test_an_invalid_argument_is_refused_before_any_port_is_touched(
    registry: ToolRegistry, search: FakeProductSearch
) -> None:
    """A schema violation costs a round trip to nothing, never a query."""
    observation = run(registry.invoke("buscar_catalogo", {"consulta": "aro", "top_k": 99}))

    assert observation.ok is False
    assert observation.cause == TOOL_CAUSE_INVALID_ARGUMENT
    assert search.search_calls == []
    assert search.lexical_calls == []
    assert search.document_by_sku_calls == []


def test_an_undeclared_argument_is_refused_rather_than_ignored(
    registry: ToolRegistry, search: FakeProductSearch
) -> None:
    """A model that invented a parameter has misunderstood the tool; serving it hides that."""
    observation = run(
        registry.invoke("consultar_disponibilidad", {"sku": "JBG-0001", "pos_id": "x"})
    )

    assert observation.ok is False
    assert observation.cause == TOOL_CAUSE_INVALID_ARGUMENT
    assert search.availability_calls == []


def test_the_catalogue_search_bounds_its_result_size(registry: ToolRegistry) -> None:
    """An explicit minimum and maximum, because an uncapped top_k is re-sent every turn."""
    properties = registry.get("buscar_catalogo").schema()["function"]["parameters"][
        "properties"
    ]

    assert properties["top_k"]["minimum"] == TOOL_TOP_K_MIN
    assert properties["top_k"]["maximum"] == TOOL_TOP_K_MAX


# --- las tools que envuelven código ya probado -------------------------------------------------------


def test_the_knowledge_tool_scopes_the_corpus_to_the_piece_when_one_is_given(
    registry: ToolRegistry,
) -> None:
    """The C30a slug filter applies when the question is anchored, and the citations resolve."""
    anchored = run(
        registry.invoke(
            "consultar_conocimiento",
            {"pregunta": "¿como limpio la plata?", "sku": "JBG-0001"},
        )
    )

    assert anchored.ok is True
    assert anchored.content["pieza"] == "JBG-0001"
    for fragment in anchored.content["fragmentos"]:
        assert fragment["citation_id"]
        assert fragment["claim_scope"]


def test_the_knowledge_tool_answers_unanchored_when_no_piece_is_given(
    registry: ToolRegistry,
) -> None:
    """With nothing to scope to, the honest behaviour is the unfiltered corpus."""
    observation = run(
        registry.invoke("consultar_conocimiento", {"pregunta": "¿como limpio la plata?"})
    )

    assert observation.ok is True
    assert observation.content["pieza"] is None


def test_a_piece_that_belongs_to_no_family_reports_an_empty_roster_and_not_a_failure(
    knowledge: InMemoryKnowledgeIndex, principal: ServicePrincipal
) -> None:
    """Belonging to no family is an answer; the consumer's next move is to stop asking."""
    search = FakeProductSearch(
        [indexed_row(product_id=LONER, sku="JBG-0009", family_id=None, family_name=None)]
    )
    registry = make_registry(search=search, knowledge=knowledge, principal=principal)
    observation = run(registry.invoke("listar_familia", {"sku": "JBG-0009"}))

    assert observation.ok is True
    assert observation.content["familia"] is None
    assert observation.content["miembros"] == []


def test_the_substitutes_tool_is_anchored_by_sku_and_reports_its_reasons(
    registry: ToolRegistry,
) -> None:
    """Alternatives come back by SKU with the reason they resemble, and with no similarity figure."""
    observation = run(registry.invoke("buscar_sustitutos", {"sku": "JBG-0001"}))

    assert observation.ok is True
    assert observation.content["pieza"] == "JBG-0001"
    for alternative in observation.content["alternativas"]:
        assert alternative["sku"] != "JBG-0001"
        assert "similarity_signals" not in alternative
        assert isinstance(alternative["motivos"], list)


def test_a_piece_indexed_without_an_embedding_cannot_anchor_substitutes(
    knowledge: InMemoryKnowledgeIndex, principal: ServicePrincipal
) -> None:
    """The third unusable case, kept apart from unknown as the substitutes path already does."""
    search = FakeProductSearch([indexed_row(has_embedding=False)])
    registry = make_registry(search=search, knowledge=knowledge, principal=principal)
    observation = run(registry.invoke("buscar_sustitutos", {"sku": "JBG-0001"}))

    assert observation.ok is False
    assert observation.cause == TOOL_CAUSE_UNUSABLE_REFERENCE


def test_the_family_tool_reads_the_roster_under_its_declared_cap(
    registry: ToolRegistry, search: FakeProductSearch
) -> None:
    """The cap is the declared ceiling and travels with the read, not an incidental limit."""
    run(registry.invoke("listar_familia", {"sku": "JBG-0001"}))

    assert search.family_roster_calls == [(FAMILY, constants.FAMILY_ROSTER_CAP)]


def test_the_availability_tool_reads_one_piece_and_never_the_whole_assortment(
    registry: ToolRegistry, search: FakeProductSearch
) -> None:
    """Per piece and not `scope_buckets`: a dump would spend a connection on rows nobody reads."""
    run(registry.invoke("consultar_disponibilidad", {"sku": "JBG-0001"}))

    assert search.availability_calls == [(PIECE, UUID(TOKEN_POS_ID))]


def test_the_tool_arguments_are_never_written_to_a_log(
    registry: ToolRegistry, caplog: pytest.LogCaptureFixture
) -> None:
    """The operator's query is not logged, by the rule the generation layer already holds."""
    with caplog.at_level("DEBUG", logger="jbg_ai.assist.tools"):
        run(registry.invoke("buscar_catalogo", {"consulta": "un anillo para mi madre"}))

    written = "\n".join(record.getMessage() for record in caplog.records)
    assert "un anillo para mi madre" not in written
    assert "tool=buscar_catalogo" in written


def test_the_catalogue_search_reports_abstention_and_not_the_consensus_flag(
    knowledge: InMemoryKnowledgeIndex, principal: ServicePrincipal
) -> None:
    """An abstention is a decision about the query; `low_confidence` measures something else.

    Both empty the candidate list, so the observation has to say which happened or the
    consumer cannot tell "reformulate" from "there is nothing". The retrieval path records
    that the two are not interchangeable — `low_confidence` carries cross-branch consensus,
    which on the judged set moves the *opposite* way — and offers the seam this tool uses.
    """
    search = FakeProductSearch([indexed_row()])
    registry = make_registry(search=search, knowledge=knowledge, principal=principal)
    observation = run(registry.invoke("buscar_catalogo", {"consulta": "anillo de plata"}))

    assert observation.ok is True
    assert "abstenido" in observation.content
    assert observation.content["abstenido"] is False, "the premise: this query is answerable"
    assert observation.content["candidatos"], "and it returns candidates"
    # The consensus flag is deliberately not re-exported under another name: a consumer that
    # read it as an abstention would report the opposite of the truth.
    assert "confianza_baja" not in observation.content
    assert "low_confidence" not in observation.content


def test_the_catalogue_search_reports_an_abstention_when_the_retriever_abstains(
    knowledge: InMemoryKnowledgeIndex, principal: ServicePrincipal
) -> None:
    """The positive direction of `abstenido`, which is the one the field exists for.

    The test above drives only the answerable case, and every assertion it makes would stay
    green over a field hardcoded to `False` — which is precisely the failure mode that made
    re-exporting `low_confidence` survive its first review. So the abstention has to be driven
    for real: a flat distance profile is the shape of a query the catalogue cannot answer, and
    the relative rule of C25 abstains on it.
    """
    flat = [
        indexed_row(
            product_id=UUID(int=index),
            sku=f"JBG-{index:04d}",
            distance=0.500 + 0.0005 * index,
        )
        for index in range(1, 21)
    ]
    registry = make_registry(
        search=FakeProductSearch(flat), knowledge=knowledge, principal=principal
    )
    observation = run(registry.invoke("buscar_catalogo", {"consulta": "anillo de plata"}))

    assert observation.ok is True
    assert observation.content["abstenido"] is True
    # An abstention is a decision about the WHOLE query, so it empties the candidate list. The
    # flag is the only thing that tells the consumer to reformulate rather than conclude that
    # the catalogue holds nothing — the two empty lists look identical without it.
    assert observation.content["candidatos"] == []
