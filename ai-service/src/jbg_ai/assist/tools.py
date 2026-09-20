"""The sale assistant's tool registry: six read-only tools and their invariants. C32a.

**This is a library and it is wired to no route.** Its only consumer is the agent loop, which
is a later change, so nothing here reaches `jbg_ai.api` and `ai-service/openapi.json` does not
move. Exposing a surface before there is a decision behind it would publish a contract nobody
consumes, and the cheapest moment to move a frozen contract is not before it has to.

Four properties are what this module is for, and each one is a test rather than a sentence:

**The set of six is frozen.** `TOOL_NAMES` is a declared constant and construction refuses
anything outside it, so a seventh tool is a deliberate act with a test behind it and the two
withdrawn before this registry existed cannot return by accident.

**Nothing here writes, and the check looks at the object graph.** Not at a `writes: bool` on
the descriptor, which is set by whoever registers the tool — precisely who could be wrong. The
published limitation that no agent writes is one of the three this project's README hands over,
so it is demonstrated or it is not declared. `verify_read_only` is the demonstration and it runs
at construction, which is what makes it useful in six months rather than today.

**A failure is data.** No exception leaves `invoke`: one escaping would kill the consuming loop
instead of costing it a single turn, and a generic `error` would leave the model blind where a
code lets it reformulate. Every failure carries a cause from a closed vocabulary.

**No tool calls a chat provider.** That is what makes this half measurable at no cost and the
ablation against it clean. The embedding calls two of the tools legitimately make are counted
in a counter of their own, because the provider-call figure the assistance layer already
publishes means *chat calls of one request* and has tests asserting its ceiling — widening its
meaning here would make a number that is already reported mean two different things.

**Addressed by SKU, never by internal identifier.** A SKU is stable, real and semantic, and it
is what lets a model chain one call into the next; an internal identifier is an arbitrary
string of digits nobody says at a counter, which is why the generation layer already excludes
it from everything a model is shown.
"""

from __future__ import annotations

import functools
import inspect
import logging
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.schemas.retrieval import RetrievalRequest, SubstitutesRequest
from jbg_ai.assist.constants import (
    AVAILABILITY_LABEL_BY_BUCKET,
    AVAILABILITY_NO_SCOPE,
    FAMILY_ROSTER_CAP,
    TOOL_CAUSE_DEPENDENCY_UNAVAILABLE,
    TOOL_CAUSE_INVALID_ARGUMENT,
    TOOL_CAUSE_UNKNOWN_REFERENCE,
    TOOL_CAUSE_UNUSABLE_REFERENCE,
    TOOL_CITATION_TOP_K,
    TOOL_NAMES,
    TOOL_TOP_K_DEFAULT,
    TOOL_TOP_K_MAX,
    TOOL_TOP_K_MIN,
    WRITE_HTTP_VERBS,
    WRITE_METHOD_VERBS,
)
from jbg_ai.assist.knowledge_scope import piece_scoped_exclusions
from jbg_ai.assist.routing import clarification_axes, clarification_for
from jbg_ai.config.settings import Settings
from jbg_ai.indexing.embeddings import EmbeddingClient, EmbedResult
from jbg_ai.knowledge.search import KnowledgeSearchIndex, search_knowledge
from jbg_ai.retrieval.errors import (
    InvalidPosIdError,
    RetrievalDependencyError,
    UnusableSourceProductError,
)
from jbg_ai.retrieval.orchestrator import retrieve_products
from jbg_ai.retrieval.ports import ProductSearchPort, SourceDocument
from jbg_ai.retrieval.projection import ProjectionFreshness, age_seconds, parse_pos_id
from jbg_ai.retrieval.substitutes import retrieve_substitutes

logger = logging.getLogger(__name__)


class ToolRegistryError(RuntimeError):
    """Construction refused the registry. Raised at build time and never at call time.

    It is deliberately not an `AssistError`: the assistance layer's errors describe a request
    that cannot be served, and this one describes a registry that must not exist at all. A
    consumer catching the layer must not accidentally catch a broken invariant.
    """


# --- the observation -------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolObservation:
    """What one tool execution produced. Bounded, and a failure is one of its shapes.

    `content` carries only what a consumer needs to decide the next step, because everything
    a tool returns is re-sent on **every** subsequent turn of the consuming loop and the
    accumulated context, not the number of steps, is what dominates the cost of an agent.

    Raw retrieval scores are absent by rule and not by omission. They are also not comparable
    across tools — a product distance and a substitute similarity do not measure the same
    thing — so placing them side by side would invite a comparison that means nothing. Where
    an ordering signal is needed it travels as `posicion`.
    """

    tool: str
    ok: bool
    content: Mapping[str, Any]
    #: A code from `TOOL_FAILURE_CAUSES`, and `None` on a successful observation. **Never
    #: prose**: the consumer branches on it, and the Spanish belongs to whoever presents it.
    cause: str | None = None

    @classmethod
    def success(cls, tool: str, content: Mapping[str, Any]) -> "ToolObservation":
        return cls(tool=tool, ok=True, content=dict(content), cause=None)

    @classmethod
    def failure(cls, tool: str, cause: str) -> "ToolObservation":
        return cls(tool=tool, ok=False, content={}, cause=cause)


class UnknownSkuError(LookupError):
    """The index holds no document for this SKU. Translated to a failed observation."""


class UnusableSkuError(LookupError):
    """The piece exists and cannot anchor this tool: discontinued, or without an embedding."""


# --- the descriptor and the registry ---------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    """One tool: what the model reads, what it may send, and what runs.

    `description` is **the interface**, not documentation of it: the model chooses a tool by
    reading it and nothing else, so it is a prompt and it is versioned with the code that
    serves it. It is written in Spanish for a reader who sees no code.

    `arguments` is a pydantic model and the schema is derived from it rather than written
    beside it, so a bound declared in one place cannot disagree with the bound published in
    the other. There is deliberately **no `writes` field**: see `verify_read_only`.
    """

    name: str
    description: str
    arguments: type[BaseModel]
    run: Callable[[BaseModel], Awaitable[Mapping[str, Any]]]

    def schema(self) -> dict[str, Any]:
        """The function-calling schema of this tool.

        **Not frozen in a versioned snapshot**, unlike `openapi.json`. That one is frozen
        because it is the boundary with .NET and moving it silently breaks a client that
        cannot be redeployed in the same step. This crosses no boundary at all, so its shape
        is pinned by a test of shape and a snapshot would only add a file to regenerate on
        every internal change.
        """
        parameters = self.arguments.model_json_schema()
        # `title` is pydantic's echo of the class name — `_BuscarCatalogoArgs` — which says
        # nothing to a model and leaks the private spelling of an implementation detail.
        parameters.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }


class ToolRegistry:
    """The six tools, resolvable by name, with both invariants checked at construction.

    Built **per request**, because a tool is bound to the principal whose scope it reads
    under. That costs nothing — no port is constructed here and no I/O happens — and it is
    what keeps the reading scope a property of the token rather than an argument a caller
    could pass.
    """

    def __init__(self, specs: Sequence[ToolSpec], *, embeddings: "CountingEmbeddings") -> None:
        names = tuple(spec.name for spec in specs)
        if len(set(names)) != len(names):
            raise ToolRegistryError(f"duplicate tool name in registry: {names}")
        if set(names) != set(TOOL_NAMES):
            unexpected = sorted(set(names) - set(TOOL_NAMES))
            missing = sorted(set(TOOL_NAMES) - set(names))
            raise ToolRegistryError(
                "the tool set is frozen: "
                f"unexpected={unexpected or 'none'} missing={missing or 'none'}"
            )
        self._specs: dict[str, ToolSpec] = {spec.name: spec for spec in specs}
        self._embeddings = embeddings
        verify_read_only(self)

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, name: object) -> bool:
        return name in self._specs

    def names(self) -> tuple[str, ...]:
        """In the frozen order, which is the order a model sees them declared in."""
        return tuple(name for name in TOOL_NAMES if name in self._specs)

    def specs(self) -> tuple[ToolSpec, ...]:
        return tuple(self._specs[name] for name in self.names())

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        """Every tool's function-calling schema, in the frozen order."""
        return [spec.schema() for spec in self.specs()]

    @property
    def embedding_calls(self) -> int:
        """Embedding requests this registry has made. **Its own counter, and separate.**

        The assistance layer's `usage.calls` counts *chat* calls of one request and has tests
        asserting its ceiling. Folding embeddings into it would make a figure that is already
        published mean two different things in two places.
        """
        return self._embeddings.calls

    async def invoke(
        self, name: str, arguments: Mapping[str, Any] | None = None
    ) -> ToolObservation:
        """Validate, execute, and return an observation. **Nothing raises out of here.**

        The arguments are validated against the tool's own schema **before any port is
        touched**, so an invalid call costs a round trip to nothing at all rather than a
        query, and the consumer learns it was the argument and not the catalogue.
        """
        spec = self._specs.get(name)
        if spec is None:
            # Unreachable through a model that was handed `schemas()`, and reachable through
            # one that hallucinated a name — which is exactly the case this must not raise on.
            return ToolObservation.failure(name, TOOL_CAUSE_UNKNOWN_REFERENCE)

        try:
            parsed = spec.arguments.model_validate(dict(arguments or {}))
        except ValidationError:
            logger.info(
                "tool=%s result=failed cause=%s elapsed_ms=0",
                spec.name,
                TOOL_CAUSE_INVALID_ARGUMENT,
            )
            return ToolObservation.failure(spec.name, TOOL_CAUSE_INVALID_ARGUMENT)

        started = time.perf_counter()
        try:
            content = await spec.run(parsed)
        except UnknownSkuError:
            return self._failed(spec, TOOL_CAUSE_UNKNOWN_REFERENCE, started)
        except (UnusableSkuError, UnusableSourceProductError):
            return self._failed(spec, TOOL_CAUSE_UNUSABLE_REFERENCE, started)
        except RetrievalDependencyError:
            return self._failed(spec, TOOL_CAUSE_DEPENDENCY_UNAVAILABLE, started)
        except Exception:  # noqa: BLE001 — see below
            # **The catch-all is the requirement and not laziness.** An exception escaping
            # here would kill the consuming loop outright instead of costing it one turn, so
            # there is no fault this may let through. What it must not do is lose the reason:
            # the cause the consumer gets is the honest coarse one, and `exc_info` keeps the
            # real traceback where an operator can read it.
            logger.exception(
                "tool=%s result=failed cause=%s",
                spec.name,
                TOOL_CAUSE_DEPENDENCY_UNAVAILABLE,
            )
            return self._failed(spec, TOOL_CAUSE_DEPENDENCY_UNAVAILABLE, started)

        # The arguments are deliberately absent from this line, by the rule C30b and C31 left
        # with a test: the operator's query is not written to any log.
        logger.info(
            "tool=%s result=ok cause=- elapsed_ms=%.1f",
            spec.name,
            (time.perf_counter() - started) * 1000.0,
        )
        return ToolObservation.success(spec.name, content)

    @staticmethod
    def _failed(spec: ToolSpec, cause: str, started: float) -> ToolObservation:
        logger.info(
            "tool=%s result=failed cause=%s elapsed_ms=%.1f",
            spec.name,
            cause,
            (time.perf_counter() - started) * 1000.0,
        )
        return ToolObservation.failure(spec.name, cause)


# --- the read-only invariant, by introspection -------------------------------------------------


def _method_names(obj: object) -> list[str]:
    """Public callables the object exposes, without touching a property's getter.

    `getattr_static` rather than `getattr` on purpose: a port is free to compute an attribute
    in a property, and the invariant must not be able to RUN anything while checking that
    nothing writes. An object defining `__slots__` has no `__dict__`, which is why the
    instance half is guarded rather than assumed.
    """
    try:
        instance_names = list(vars(obj))
    except TypeError:  # `__slots__`, and the class half below still answers
        instance_names = []
    names: list[str] = []
    for name in dir(type(obj)) + instance_names:
        if name.startswith("_"):
            continue
        attribute = inspect.getattr_static(obj, name, None)
        if attribute is None or isinstance(attribute, property):
            continue
        if callable(attribute) or inspect.iscoroutinefunction(attribute):
            names.append(name)
    return sorted(set(names))


#: The two objects every tool is handed that are configuration and identity rather than a way
#: to reach anything. **Named one by one, and that is the point.**
#:
#: Both are pydantic models and both trip the write vocabulary on a name of their own that has
#: nothing to do with writing: `Settings` on pydantic's deprecated v1 shim `update_forward_refs`
#: and on its own validator `blank_index_sync_time_budget_is_default`, `ServicePrincipal` on the
#: shim alone. Neither performs I/O and neither holds a session.
#:
#: **Excluding the categories they belong to instead would be the bug this list exists to
#: avoid.** An earlier form of this check excluded every pydantic model and every dataclass,
#: which silently dropped `InMemoryKnowledgeIndex` — a real port, a dataclass, captured by
#: `consultar_conocimiento` — out of all three axes, and would have let a future port that
#: writes through by the same door as long as it were written as either. A port is inspected
#: whatever it is built from; only these two names are not, and adding a third is an edit to
#: the module whose only reason to exist is to check.
_INERT_TYPES: tuple[type, ...] = (Settings, ServicePrincipal)


def _is_collaborator(obj: object) -> bool:
    """Is this captured value an injected collaborator, or inert data?

    The distinction is **structural and never declared by the tool**, which is the whole
    point: a tool cannot opt its dependencies out of the check.

    Excluded are the kinds that carry no behaviour of their own — primitives, containers,
    modules, classes and functions — plus the two named types of `_INERT_TYPES`. Nothing is
    excluded for the construction it happens to use: a dataclass and a pydantic model are both
    ordinary ways to write a port, so both are inspected. Excluding configuration and identity
    is correct; excluding anything that could reach a system of record is not.
    """
    if obj is None or isinstance(obj, (str, bytes, bool, int, float, complex)):
        return False
    if isinstance(obj, (list, tuple, set, frozenset, dict, UUID)):
        return False
    if inspect.ismodule(obj) or inspect.isclass(obj) or inspect.isroutine(obj):
        return False
    if isinstance(obj, _INERT_TYPES):
        return False
    return bool(_method_names(obj))


def captured_collaborators(spec: ToolSpec) -> list[object]:
    """Every collaborator the tool's executor holds, found in the object graph.

    Walks the closure cells of the executor, through `functools.partial` and bound methods,
    and one level into the containers it finds. It does **not** recurse into the attributes of
    a collaborator: the boundary is "what this tool was handed", and following attributes
    turns the check into a scan of the whole process — `Settings` alone would drag in every
    field of the configuration.

    **It also sees only what the executor CLOSES OVER.** A module-level function reaching a
    module-level port by global lookup holds no closure cell, so it would arrive here with
    nothing captured and pass all three axes over an empty list. That is inert today — all six
    executors are closures nested in `build_registry`, which is what `build_registry` being the
    only construction seam buys — and it is the reason a future tool must keep being built the
    same way rather than reaching for a module global.

    That boundary is honest about what the invariant does and does not catch. It catches the
    real case, which is a future tool injected with a port that writes. It does not catch a
    port deliberately smuggled inside another object, and nothing short of a sandbox would:
    an author willing to hide a write has easier routes than this one.
    """
    found: list[object] = []
    seen: set[int] = set()
    pending: list[tuple[object, int]] = [(spec.run, 0)]

    while pending:
        current, depth = pending.pop()
        if current is None or depth > 3:
            continue
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)

        if isinstance(current, functools.partial):
            pending.append((current.func, depth))
            pending.extend((value, depth + 1) for value in current.args)
            pending.extend((value, depth + 1) for value in current.keywords.values())
            continue
        if inspect.ismethod(current):
            pending.append((current.__self__, depth + 1))
            pending.append((current.__func__, depth))
            continue
        if inspect.isfunction(current):
            for cell in current.__closure__ or ():
                try:
                    pending.append((cell.cell_contents, depth + 1))
                except ValueError:  # an empty cell of a recursive closure
                    continue
            continue
        if isinstance(current, (list, tuple, set, frozenset)):
            pending.extend((value, depth + 1) for value in current)
            continue
        if isinstance(current, dict):
            pending.extend((value, depth + 1) for value in current.values())
            continue
        if _is_collaborator(current):
            found.append(current)

    return found


def write_methods_of(obj: object) -> list[str]:
    """Methods whose name declares a write, matched **token by token**.

    Substring containment was the obvious reading and it is wrong: `sync` occurs inside
    `projection_synced_at()` and `synced_at()`, which read a checkpoint, and a check built on
    it would make the invariant unsatisfiable with the very ports this registry must inject.
    Token equality catches every spelling built from one of the verbs — `save_profile`,
    `bulk_insert`, `upsert_projection`, `delete_row`, `sync_now` — and a test registers a
    writing port to hold that claim up rather than leaving it asserted here.

    What it misses is a verb `WRITE_METHOD_VERBS` never held, not an inflection of one it does:
    `put_checkpoint()` writes and matches nothing, under this rule or under substring. The
    vocabulary's own docstring carries that limit; this function only applies it.
    """
    return [
        name
        for name in _method_names(obj)
        if set(name.split("_")) & WRITE_METHOD_VERBS
    ]


def http_write_verbs_of(obj: object) -> list[str]:
    """Non-read HTTP verbs this object exposes as callables.

    The question is what the client **can** issue and never what it happens to issue today: a
    general-purpose HTTP client is one line away from a POST, so registering one fails here,
    while a wrapper that exposes only a read does not.
    """
    return [name for name in _method_names(obj) if name in WRITE_HTTP_VERBS]


def verify_read_only(registry: ToolRegistry) -> None:
    """Three axes over the constructed registry. Raises rather than returning a verdict.

    **Deliberately not a `writes: bool` on the descriptor.** A boolean saying a tool does not
    write is set by whoever registers it, which is precisely who could be wrong, and it would
    pass this check while the tool wrote. What is inspected instead is the object graph: the
    set of registered names, the methods every collaborator a tool captured exposes, and the
    HTTP verbs any registered client could issue. A tool that declares itself read-only and
    captures a port with a write method fails, which is the case that makes this useful in six
    months rather than today.
    """
    registered = set(registry.names())
    if registered != set(TOOL_NAMES):
        raise ToolRegistryError(f"registry names are not the frozen set: {sorted(registered)}")

    for spec in registry.specs():
        for collaborator in captured_collaborators(spec):
            writes = write_methods_of(collaborator)
            if writes:
                raise ToolRegistryError(
                    f"tool {spec.name!r} captures {type(collaborator).__name__}, "
                    f"which exposes write methods: {writes}"
                )
            verbs = http_write_verbs_of(collaborator)
            if verbs:
                raise ToolRegistryError(
                    f"tool {spec.name!r} captures {type(collaborator).__name__}, "
                    f"an HTTP client able to issue: {verbs}"
                )


# --- the embedding counter ---------------------------------------------------------------------


class CountingEmbeddings:
    """Delegating `EmbeddingClient` that counts requests. No behaviour of its own.

    It exists so the embedding calls two tools legitimately make are visible **and kept
    apart** from the chat-call figure the assistance layer publishes. It is not a cache and
    must not become one: the real client already holds one, keyed on the text.
    """

    def __init__(self, inner: EmbeddingClient) -> None:
        self._inner = inner
        self.calls = 0
        self.model_id = inner.model_id
        self.document_version_key = inner.document_version_key
        self.model_version_key = inner.model_version_key

    async def embed(self, texts: list[str]) -> EmbedResult:
        self.calls += 1
        return await self._inner.embed(texts)


# --- the argument models ------------------------------------------------------------------------
#
# `extra="forbid"` on every one of them, so an argument the tool does not declare is a rejected
# call and not a silently ignored one. A model that invented a parameter has misunderstood the
# tool, and serving it anyway would hide the misunderstanding behind a plausible answer.


class _BuscarCatalogoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consulta: str = Field(
        min_length=1,
        max_length=500,
        description="Lo que el cliente busca, en lenguaje natural y en castellano.",
    )
    top_k: int = Field(
        default=TOOL_TOP_K_DEFAULT,
        ge=TOOL_TOP_K_MIN,
        le=TOOL_TOP_K_MAX,
        description=(
            f"Cuantas piezas devolver, entre {TOOL_TOP_K_MIN} y {TOOL_TOP_K_MAX}. "
            "Pide pocas: cada resultado se arrastra en todas las vueltas siguientes."
        ),
    )


class _SkuArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str = Field(
        min_length=1,
        max_length=64,
        description="Referencia de la pieza, tal y como aparece en la etiqueta (p. ej. JBG-0001).",
    )


class _ConsultarConocimientoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pregunta: str = Field(
        min_length=1,
        max_length=500,
        description="La pregunta del cliente sobre cuidados, materiales, tallas o politicas.",
    )
    sku: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "Referencia de la pieza si la pregunta va sobre una concreta. "
            "Al indicarla se descartan las fichas de materiales que la pieza no declara."
        ),
    )


def _clarification_axis_field() -> Any:
    """The axis field, with the closed set taken from the catalogue that owns it.

    Declared from `clarification_axes()` rather than restated as a `Literal`, so the schema a
    model reads and the catalogue the answer is resolved from cannot drift apart. A fifth
    template added to that catalogue publishes a fifth axis here with no edit.
    """
    axes = list(clarification_axes())
    return Field(
        description=(
            "El eje que falta por concretar. Uno de: " + ", ".join(axes) + "."
        ),
        json_schema_extra={"enum": axes},
    )


class _PedirAclaracionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eje: str = _clarification_axis_field()

    def model_post_init(self, _context: object) -> None:
        # Validated here and not only advertised in the schema: the enum in the schema is what
        # a model reads, and this is what makes an axis outside the closed set a rejected
        # argument **before** anything executes, exactly as the requirement words it.
        if self.eje not in clarification_axes():
            raise ValueError(f"unknown clarification axis: {self.eje!r}")


# --- the six tools --------------------------------------------------------------------------------


def _candidate_reasons(reasons: Iterable[str]) -> list[str]:
    """The match reasons as the retrieval produced them. No score travels beside them."""
    return [str(reason) for reason in reasons]


async def _resolve_sku(search: ProductSearchPort, sku: str) -> SourceDocument:
    """One SKU to its document, or the failure that says which of the two things went wrong.

    Unknown and unusable are kept apart because they are two different next moves for the
    consumer: another reference, or another question about this one.
    """
    document = await search.document_by_sku(sku)
    if document is None:
        raise UnknownSkuError(sku)
    if not document.is_active:
        raise UnusableSkuError(sku)
    return document


def build_registry(
    *,
    principal: ServicePrincipal,
    settings: Settings,
    embed: EmbeddingClient,
    search: ProductSearchPort,
    knowledge: KnowledgeSearchIndex,
    freshness: ProjectionFreshness | None = None,
    roster_cap: int = FAMILY_ROSTER_CAP,
    citation_top_k: int = TOOL_CITATION_TOP_K,
) -> ToolRegistry:
    """Assemble the six tools over ports that are **handed in, never constructed here**.

    That is the pattern the whole assistance layer follows since C30a, and it is what lets the
    agent loop and the adversarial suite mount this registry against fakes without opening a
    socket. Constructing a port here would put a `DATABASE_URL` in the middle of a library.

    `principal` is bound at build time on purpose: the reading scope is the token's, as
    everywhere in `/v1`, and a per-call principal would make it an argument a caller could
    choose. Building one registry per request costs nothing — no I/O happens here.
    """
    embeddings = CountingEmbeddings(embed)
    projection = freshness or ProjectionFreshness()

    async def buscar_catalogo(args: _BuscarCatalogoArgs) -> Mapping[str, Any]:
        # **`on_abstention` and not `low_confidence`, and the difference is measured.** An
        # abstention empties the candidate list, and so does a query that simply found
        # nothing; the one field that moves with both carries a DIFFERENT meaning — cross
        # branch consensus, 1 of 20 out-of-domain against 10 of 43 answerable — so a consumer
        # reading it as abstention would report the opposite of the truth on the judged set.
        # This is the seam C30a added for exactly this, and the reason its response carries an
        # `abstained` field of its own rather than reusing the other one.
        decisions: list[bool] = []
        response = await retrieve_products(
            RetrievalRequest(query=args.consulta, top_k=args.top_k),
            principal,
            settings=settings,
            embed=embeddings,
            search=search,
            on_abstention=decisions.append,
        )
        return {
            "candidatos": [
                {
                    # The ordering signal, and the only one. A raw distance would not be
                    # comparable with the similarity another tool reports.
                    "posicion": position,
                    "sku": result.sku,
                    "materiales": list(result.materials),
                    "variante": result.variant_label,
                    "motivos": _candidate_reasons(result.match_reasons),
                }
                for position, result in enumerate(response.results, start=1)
            ],
            # The retriever decided the catalogue cannot answer this query. A different next
            # move from an empty list: reformulate, rather than conclude there is nothing.
            "abstenido": bool(decisions and decisions[-1]),
        }

    async def buscar_sustitutos(args: _SkuArgs) -> Mapping[str, Any]:
        document = await _resolve_sku(search, args.sku)
        if not document.has_embedding:
            raise UnusableSkuError(args.sku)
        response = await retrieve_substitutes(
            SubstitutesRequest(product_id=str(document.product_id), top_k=TOOL_TOP_K_DEFAULT),
            principal,
            settings=settings,
            search=search,
        )
        return {
            "pieza": document.sku,
            "alternativas": [
                {
                    "posicion": position,
                    "sku": result.sku,
                    "materiales": list(result.materials),
                    "variante": result.variant_label,
                    # Already prose written by the substitutes path, already free of price and
                    # of any stock figure, and already checked there. The similarity numbers
                    # beside it are deliberately **not** carried: a similarity of 0,62 is not
                    # comparable with the position above and means nothing to a reader.
                    "motivos": _candidate_reasons(result.match_reasons),
                }
                for position, result in enumerate(response.results, start=1)
            ],
        }

    async def listar_familia(args: _SkuArgs) -> Mapping[str, Any]:
        document = await _resolve_sku(search, args.sku)
        if document.family_id is None:
            # A piece that belongs to no family is a legitimate answer and not a failure: the
            # consumer's next move is to stop asking, which an empty roster says plainly.
            return {"pieza": document.sku, "familia": None, "miembros": []}
        members = await search.family_roster(document.family_id, cap=roster_cap)
        return {
            "pieza": document.sku,
            "familia": next(
                (member.family_name for member in members if member.family_name), None
            ),
            "miembros": [
                {
                    "sku": member.sku,
                    "variante": member.variant_label,
                    "materiales": list(member.materials),
                    "talla": member.size_label,
                }
                for member in members
            ],
        }

    async def consultar_conocimiento(args: _ConsultarConocimientoArgs) -> Mapping[str, Any]:
        exclusions: tuple[UUID, ...] = ()
        anchored: str | None = None
        if args.sku is not None:
            document = await _resolve_sku(search, args.sku)
            anchored = document.sku
            # The C30a filter, and only when the question is anchored to a piece: it removes
            # the sheets of the canonical materials the piece does NOT declare, which are the
            # decoys the corpus warns are structurally identical to the right one.
            exclusions = piece_scoped_exclusions(document.materials)
        citations = await search_knowledge(
            args.pregunta,
            embed=embeddings,
            index=knowledge,
            top_k=citation_top_k,
            exclude_documents=exclusions,
            distance_threshold=settings.jpv_knowledge_distance_threshold,
            trace_id=principal.trace_id,
        )
        return {
            "pieza": anchored,
            "fragmentos": [
                {
                    "posicion": position,
                    "citation_id": citation.citation_id,
                    # Not decoration: a commitment of the establishment read aloud as a fact
                    # of the world is the failure the whole marking mechanism exists to stop.
                    "claim_scope": citation.claim_scope,
                    "titulo": citation.section_title,
                    "contenido": citation.content,
                }
                for position, citation in enumerate(citations, start=1)
            ],
        }

    async def consultar_disponibilidad(args: _SkuArgs) -> Mapping[str, Any]:
        document = await _resolve_sku(search, args.sku)
        etiqueta = AVAILABILITY_NO_SCOPE
        pos_id: UUID | None = None

        if principal.pos_id is not None:
            try:
                pos_id = parse_pos_id(principal.pos_id)
            except InvalidPosIdError:
                # A claim that does not parse is a mis-issued token. Reporting "no scope" is
                # the NARROWEST answer available and reveals nothing, where inventing an
                # absence would fire the pivot to substitutes over a piece the shop may well
                # have. The fault survives in the log rather than in the observation.
                logger.warning(
                    "tool=consultar_disponibilidad pos_id claim does not parse",
                    extra={"trace_id": principal.trace_id},
                )
                pos_id = None

        if pos_id is not None:
            bucket = await search.availability_bucket(document.product_id, pos_id=pos_id)
            # Absence of a row is NOT a bucket of zero: it means this point of sale does not
            # carry the piece, and collapsing the two would report a piece the shop can sell
            # as one it cannot. `AVAILABILITY_NO_SCOPE` is never derived from a bucket.
            if bucket is not None:
                etiqueta = AVAILABILITY_LABEL_BY_BUCKET[bucket]

        age = age_seconds(await projection.synced_at(search))
        return {
            "pieza": document.sku,
            # A qualitative band and never a figure: the buckets the projection stores are
            # literally numerals, and the authority over stock is .NET's.
            "disponibilidad": etiqueta,
            # Freshness travels with the label, and a stale projection degrades the
            # observation instead of failing it: the rule is degrade, never remove.
            "antiguedad_proyeccion_segundos": age,
        }

    async def pedir_aclaracion(args: _PedirAclaracionArgs) -> Mapping[str, Any]:
        # The model decides WHAT is missing; the code decides HOW it is asked. The field this
        # text lands in is typed as prose and no numeric gate inspects it, so a model writing
        # here would be writing into the one field with no net under it.
        return {"eje": args.eje, "pregunta": clarification_for(args.eje)}

    specs = (
        ToolSpec(
            name="buscar_catalogo",
            description=(
                "Busca piezas del catalogo a partir de lo que describe el cliente. "
                "Usala cuando sepas que tipo de pieza quiere y necesites candidatos "
                "concretos. Devuelve las piezas por su referencia, en orden."
            ),
            arguments=_BuscarCatalogoArgs,
            run=buscar_catalogo,
        ),
        ToolSpec(
            name="buscar_sustitutos",
            description=(
                "Propone alternativas a una pieza concreta, con el motivo por el que se "
                "parecen. Usala cuando la pieza que el cliente quiere no sirve: no la hay "
                "en la tienda, no es su talla o no le convence."
            ),
            arguments=_SkuArgs,
            run=buscar_sustitutos,
        ),
        ToolSpec(
            name="listar_familia",
            description=(
                "Enumera las variantes de la misma familia que una pieza: sus medidas, "
                "acabados y materiales. Usala cuando el cliente pregunte si hay otra talla "
                "u otro acabado de lo que tiene delante."
            ),
            arguments=_SkuArgs,
            run=listar_familia,
        ),
        ToolSpec(
            name="consultar_conocimiento",
            description=(
                "Responde preguntas sobre cuidados, materiales, tallas, garantias y "
                "politicas de la joyeria, citando la ficha de donde sale cada respuesta. "
                "Indica la referencia de la pieza si la pregunta va sobre una concreta."
            ),
            arguments=_ConsultarConocimientoArgs,
            run=consultar_conocimiento,
        ),
        ToolSpec(
            name="consultar_disponibilidad",
            description=(
                "Dice si una pieza esta disponible en esta tienda, como una indicacion "
                "aproximada y nunca como una cantidad exacta. Si no consta el ambito de la "
                "tienda lo dira: eso no significa que la pieza este agotada."
            ),
            arguments=_SkuArgs,
            run=consultar_disponibilidad,
        ),
        ToolSpec(
            name="pedir_aclaracion",
            description=(
                "Pide al cliente que concrete lo unico que falta para poder buscar. "
                "Usala cuando la peticion es demasiado vaga, indicando que eje falta; "
                "la pregunta exacta la redacta el sistema."
            ),
            arguments=_PedirAclaracionArgs,
            run=pedir_aclaracion,
        ),
    )
    return ToolRegistry(specs, embeddings=embeddings)
