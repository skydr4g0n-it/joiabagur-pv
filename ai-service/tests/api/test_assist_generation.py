"""POST /v1/assist/sale with a generation client, over HTTP. C30b.

Offline throughout: the search port, the knowledge index, the embedding client and now the
generation client all go in through `app.state`, which is the seam the retrieval suite already
uses. No socket is opened and no model is called.

The two tests this module exists for are the ones C30a could not write. Its border check ran
over a response whose `pitch` was **empty**, so it asserted nothing about prose; here it runs
over a complete response carrying a real argument. And the persistence check counts data
manipulation on the engine rather than asking which modules were imported.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from jbg_ai.api.main import create_app
from jbg_ai.assist.constants import PROMPT_VERSION
from jbg_ai.knowledge.chunking import chunk_corpus
from jbg_ai.knowledge.corpus import load_corpus
from jbg_ai.knowledge.offline import InMemoryKnowledgeIndex, LocalEmbeddingClient
from support.assist_pitch import pitch, scripted_client
from support.assist_world import FAMILY, LONER, PIECE, SIBLING, indexed_row
from support.fake_product_search import FakeAssignment, FakeProductSearch
from support.settings import TOKEN_POS_ID, build_settings

#: Any bare number followed by a currency mark would mean Python resolved a price.
PRICE_LIKE = re.compile(r"\d+[.,]?\d*\s*(€|eur|euros)", re.IGNORECASE)

#: A price as the index holds it. Deliberately **not** in the payload the model is handed, so a
#: pitch that wrote it would be refused by the gate for the ordinary reason.
INDEXED_PRICE = 87.50

#: The statements that would mean the argument was written down somewhere.
DML = re.compile(r"^\s*(insert|update|delete|merge|copy|create|alter|drop)\b", re.IGNORECASE)

CARE = "material-plata#cuidados-y-limpieza-en-casa"
SKIN = "material-plata#piel-sensible-y-alergias"

GOOD = pitch(
    "Es una pieza de plata de ley que se limpia en casa con un paño suave. "
    "La plata de ley se tolera muy bien incluso con piel sensible. "
    "Cuesta {{price}} y de existencias tenemos {{stock}}.",
    (CARE, "se limpia en casa con un paño suave"),
    (SKIN, "la plata de ley se tolera muy bien"),
)


def _rows() -> list:
    return [
        indexed_row(product_id=PIECE, price=INDEXED_PRICE),
        indexed_row(
            product_id=SIBLING, sku="JBG-0002", variant_label="20 mm", price=INDEXED_PRICE
        ),
        indexed_row(
            product_id=LONER,
            sku="JBG-0009",
            family_id=None,
            family_name=None,
            price=INDEXED_PRICE,
        ),
    ]


def _app(*script, search: FakeProductSearch | None = None, **overrides):
    app = create_app(build_settings(stub_mode=False, **overrides))
    app.state.retrieval_embed = LocalEmbeddingClient()
    app.state.retrieval_search = search if search is not None else FakeProductSearch(_rows())
    app.state.knowledge_index = InMemoryKnowledgeIndex(chunks=chunk_corpus(load_corpus()))
    client, provider = scripted_client(*script)
    app.state.assist_pitch_client = client
    return app, provider


def _client(issue_token: Callable[..., str], *script, **kwargs) -> tuple[TestClient, object]:
    app, provider = _app(*script, **kwargs)
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {issue_token()}"})
    return client, provider


def _walk(value, path="$"):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
    else:
        yield path, value


# --- the route writes, over HTTP -----------------------------------------------------------


def test_the_route_serves_a_generated_argument_with_its_version_and_its_cost(
    issue_token: Callable[..., str],
) -> None:
    client, provider = _client(issue_token, GOOD)

    body = client.post("/v1/assist/sale", json={"product_id": str(PIECE)}).json()

    assert provider.call_count == 1
    assert body["pitch"].startswith("Es una pieza de plata")
    assert body["prompt_version"] == PROMPT_VERSION
    assert body["usage"]["total_tokens"] == 1800
    assert body["usage"]["model"] == "fake/pitch-model"
    assert [item["citation_id"] for item in body["citations"]] == [CARE, SKIN]


def test_the_generated_argument_carries_the_placeholders_and_never_a_figure(
    issue_token: Callable[..., str],
) -> None:
    """HU escenario 3, first half. Price and availability travel as the tokens .NET resolves."""
    client, _ = _client(issue_token, GOOD)

    body = client.post("/v1/assist/sale", json={"product_id": str(PIECE)}).json()

    assert "{{price}}" in body["pitch"] and "{{stock}}" in body["pitch"]


# --- 6.5 · the border check, over a response carrying real prose ----------------------------


def test_response_contains_no_literal_price_or_stock_number(
    issue_token: Callable[..., str],
) -> None:
    """HU escenario 3, second half — and the check C30a **could not** make.

    Its equivalent ran over a response whose `pitch` was empty, so it passed by construction
    and asserted nothing about prose. This one runs over the whole serialised response of a
    request that produced a real argument, and it is the guarantee the change exists for:
    .NET's placeholder mechanism protects one flank and leaves the other open, because an
    argument that writes «39,90 €» literally leaves no placeholder unresolved and passes.
    """
    pos = UUID(TOKEN_POS_ID)
    search = FakeProductSearch(
        _rows(),
        assignments=[
            FakeAssignment(pos_id=pos, product_id=PIECE, qty_bucket="0"),
            FakeAssignment(pos_id=pos, product_id=SIBLING, qty_bucket="1-2"),
            FakeAssignment(pos_id=pos, product_id=LONER, qty_bucket="3+"),
        ],
    )
    client, _ = _client(issue_token, GOOD, search=search)

    body = client.post("/v1/assist/sale", json={"product_id": str(PIECE)}).json()
    blob = json.dumps(body, ensure_ascii=False)

    assert body["pitch"], "the premise: an EMPTY argument would make this pass by construction"
    for forbidden in ("qty_bucket", "sales_30d", "price_band"):
        assert forbidden not in blob
    assert str(INDEXED_PRICE) not in blob
    assert "87,5" not in blob and "87.5" not in blob
    assert PRICE_LIKE.search(blob) is None
    for path, value in _walk(body):
        assert value not in ("0", "1-2", "3+"), path


def test_an_argument_that_writes_a_price_never_reaches_the_response(
    issue_token: Callable[..., str],
) -> None:
    """The gate, seen from the wire: the model writes the figure and the operator never sees it."""
    priced = pitch(
        "Una pieza de plata preciosa que te llevas por 87,50 €.",
        (CARE, "una pieza de plata preciosa"),
    )
    client, provider = _client(issue_token, priced, priced)

    body = client.post("/v1/assist/sale", json={"product_id": str(PIECE)}).json()

    assert provider.call_count == 2
    assert body["pitch"] == ""
    assert "87,50" not in json.dumps(body, ensure_ascii=False)
    assert body["prompt_version"] == PROMPT_VERSION
    assert body["citations"], "degrading must not leave the response poorer than C30a's"


# --- 9.1 · nothing is written down ----------------------------------------------------------


def test_pitch_is_not_persisted_anywhere(issue_token: Callable[..., str]) -> None:
    """HU escenario 14. Data manipulation counted **on the engine**, not modules inspected.

    The listener is installed on the `Engine` class, so it sees every statement of every engine
    created anywhere during the request — including one this layer might build for itself,
    which is precisely what a module-import check cannot see. And the meter is shown to be
    live before the conclusion is drawn: an import check that was silently broken would report
    the same clean result as a layer that genuinely writes nothing.
    """
    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(statement)

    event.listen(Engine, "before_cursor_execute", record)
    try:
        client, _ = _client(issue_token, GOOD)
        body = client.post("/v1/assist/sale", json={"product_id": str(PIECE)}).json()
        during_request = list(statements)

        # The control: the meter registers a write when there is one to register.
        probe = create_engine("sqlite://")
        with probe.begin() as connection:
            connection.execute(text("CREATE TABLE t (v TEXT)"))
            connection.execute(text("INSERT INTO t (v) VALUES ('x')"))
        probe.dispose()
    finally:
        event.remove(Engine, "before_cursor_execute", record)

    assert body["pitch"], "the premise: there is an argument that could have been persisted"
    assert [item for item in during_request if DML.match(item)] == []
    assert [item for item in statements if DML.match(item)], "the meter was live"


def test_the_argument_is_not_written_to_any_log_by_the_http_path(
    issue_token: Callable[..., str], caplog: pytest.LogCaptureFixture
) -> None:
    """HU escenario 15, over the route rather than over the callable.

    The app is built FIRST and the handler attached after: `create_app` configures the root
    logger, so a handler added before it is wiped by it. Same order as the C30a log test, and
    the order is the whole trick.
    """
    import logging

    app, _ = _app(GOOD)
    logging.getLogger().addHandler(caplog.handler)
    with caplog.at_level(logging.DEBUG):
        with TestClient(app) as client:
            body = client.post(
                "/v1/assist/sale",
                json={"product_id": str(PIECE)},
                headers={"Authorization": f"Bearer {issue_token()}"},
            ).json()

    emitted = "\n".join(record.getMessage() for record in caplog.records)
    assert body["pitch"]
    assert "paño suave" not in emitted
    assert "piel sensible" not in emitted
    assert f"prompt_version={PROMPT_VERSION}" in emitted
    assert "pitch_sha256=" in emitted
    assert "model=fake/pitch-model" in emitted


# --- 8.3 · a provider fault is a 200 and never a 5xx -----------------------------------------


def test_a_provider_failure_is_answered_with_two_hundred_and_the_structured_response(
    issue_token: Callable[..., str],
) -> None:
    """HU escenario 13, over HTTP. The route has nothing to catch: the layer degrades inside."""
    client, _ = _client(issue_token, RuntimeError("the provider is unreachable"))

    response = client.post("/v1/assist/sale", json={"product_id": str(PIECE)})
    body = response.json()

    assert response.status_code == 200
    assert body["pitch"] == ""
    assert body["prompt_version"] == PROMPT_VERSION
    assert body["groups"] and body["citations"]


# --- HU escenario 19 · what this change does not do ------------------------------------------


def test_out_of_scope_is_declared_and_not_quietly_performed(
    issue_token: Callable[..., str],
) -> None:
    """No intent classification, no clarification question, and no judge in the serving path.

    The clarification question is declared **of C31** rather than deferred by accident, and the
    ceiling of two provider calls is what says no second model was asked to grade the first:
    a judge would double the latency and the cost where a customer is waiting, and using a
    model to catch another model's fabrications is circular.
    """
    client, provider = _client(issue_token, GOOD)
    calls: dict[str, int] = {}

    for name, payload in (
        ("pieza", {"product_id": str(PIECE)}),
        ("pieza y pregunta", {"product_id": str(PIECE), "query": "¿se puede mojar?"}),
        ("consulta libre", {"query": "anillo de plata"}),
    ):
        before = provider.call_count
        body = client.post("/v1/assist/sale", json=payload).json()
        calls[name] = provider.call_count - before

        assert body["clarification_question"] is None, name
        assert body["intent"] in ("product_pitch", "unclassified"), name

    assert calls["consulta libre"] == 0, "the free query classifies nothing and writes nothing"
    # Never more than the generation plus its one repair, in either anchored mode: the ceiling
    # is what says no second model was asked to grade the first.
    assert calls["pieza"] <= 2 and calls["pieza y pregunta"] <= 2


# --- the timeout the sweep moved, and the seam that lets a deployment move it again ---------


def test_the_configured_timeout_reaches_the_generation_client(
    issue_token: Callable[..., str],
) -> None:
    """Settings supplies the default, the value travels by parameter, and the route wires it.

    Without this the setting would exist and change nothing, which is the failure mode of every
    knob added one layer away from where it is read.
    """
    from jbg_ai.api.main import create_app
    from jbg_ai.assist.constants import PITCH_TIMEOUT_SECONDS

    app = create_app(
        build_settings(
            stub_mode=False,
            jpv_rag_llm_api_key="sk-test",
            jpv_assist_pitch_timeout_seconds=7.5,
        )
    )
    app.state.retrieval_embed = LocalEmbeddingClient()
    app.state.retrieval_search = FakeProductSearch(_rows())
    app.state.knowledge_index = InMemoryKnowledgeIndex(chunks=chunk_corpus(load_corpus()))

    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {issue_token()}"})
    # The call fails at the provider's door — there is no socket — and degrades, which is the
    # behaviour under test everywhere else. What matters here is the client that got built.
    client.post("/v1/assist/sale", json={"product_id": str(PIECE)})

    assert app.state.assist_pitch_client._timeout == 7.5
    assert PITCH_TIMEOUT_SECONDS == 4.0, "the default the sweep set, pinned to its measurement"


def test_a_deployment_without_the_provider_credential_builds_no_client(
    issue_token: Callable[..., str],
) -> None:
    """`None` is a deployment state, not a failure: the route answers 200 with C30a's response
    rather than the 503 the paths with nothing to return answer."""
    from jbg_ai.api.main import create_app

    app = create_app(build_settings(stub_mode=False))
    app.state.retrieval_embed = LocalEmbeddingClient()
    app.state.retrieval_search = FakeProductSearch(_rows())
    app.state.knowledge_index = InMemoryKnowledgeIndex(chunks=chunk_corpus(load_corpus()))

    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {issue_token()}"})
    response = client.post("/v1/assist/sale", json={"product_id": str(PIECE)})

    assert response.status_code == 200
    assert response.json()["pitch"] == ""
    assert response.json()["prompt_version"] is None
    assert response.json()["citations"]
    assert getattr(app.state, "assist_pitch_client", None) is None


# --- the credential and the model the route actually resolves -------------------------------


def _built_client(issue_token: Callable[..., str], **overrides):
    """Drive one request through the real resolution and hand back the client it built."""
    from jbg_ai.api.main import create_app

    app = create_app(build_settings(stub_mode=False, **overrides))
    app.state.retrieval_embed = LocalEmbeddingClient()
    app.state.retrieval_search = FakeProductSearch(_rows())
    app.state.knowledge_index = InMemoryKnowledgeIndex(chunks=chunk_corpus(load_corpus()))

    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {issue_token()}"})
    response = client.post("/v1/assist/sale", json={"product_id": str(PIECE)})

    return getattr(app.state, "assist_pitch_client", None), response


def test_the_dedicated_credential_is_preferred_over_the_enrichment_one(
    issue_token: Callable[..., str],
) -> None:
    """Separating the credential is what makes counter-side generation billable, rate-limitable
    and rotatable apart from C09's batch enrichment — two calls with very different shapes."""
    built, _ = _built_client(
        issue_token,
        jpv_rag_llm_api_key="sk-enrichment",
        jpv_assist_llm_api_key="sk-assist",
    )

    assert built is not None
    assert built._api_key == "sk-assist"


def test_the_enrichment_credential_is_the_fallback_and_not_a_requirement(
    issue_token: Callable[..., str],
) -> None:
    """Optional on purpose. Requiring the new one would have stopped an existing deployment
    generating the day the field appeared — and silently, because the layer degrades to 200."""
    built, response = _built_client(issue_token, jpv_rag_llm_api_key="sk-enrichment")

    assert response.status_code == 200
    assert built is not None
    assert built._api_key == "sk-enrichment"


def test_the_fallback_is_recorded_so_a_deployment_can_check_it_instead_of_assuming(
    issue_token: Callable[..., str], caplog: pytest.LogCaptureFixture
) -> None:
    """A silent fallback would let a deployment believe it had separated its credentials when
    it had not. The line carries WHICH one was resolved and never the key itself."""
    import logging

    from jbg_ai.api.main import create_app

    app = create_app(build_settings(stub_mode=False, jpv_rag_llm_api_key="sk-enrichment"))
    app.state.retrieval_embed = LocalEmbeddingClient()
    app.state.retrieval_search = FakeProductSearch(_rows())
    app.state.knowledge_index = InMemoryKnowledgeIndex(chunks=chunk_corpus(load_corpus()))
    logging.getLogger().addHandler(caplog.handler)
    with caplog.at_level(logging.INFO):
        with TestClient(app) as client:
            client.post(
                "/v1/assist/sale",
                json={"product_id": str(PIECE)},
                headers={"Authorization": f"Bearer {issue_token()}"},
            )

    emitted = "\n".join(record.getMessage() for record in caplog.records)
    assert "stage=assist_client" in emitted
    assert "credential=rag_fallback" in emitted
    assert "sk-enrichment" not in emitted, "a credential never reaches a log line"


def test_the_configured_model_reaches_the_generation_client(
    issue_token: Callable[..., str],
) -> None:
    """The knob has to arrive where the call is made, or it is a setting that changes nothing."""
    built, _ = _built_client(
        issue_token,
        jpv_rag_llm_api_key="sk-enrichment",
        jpv_assist_llm_model="openai/gpt-4.1-mini",
    )

    assert built is not None
    assert built.model_id == "openai/gpt-4.1-mini"


def test_the_enrichment_model_cannot_move_the_assistance_model(
    issue_token: Callable[..., str],
) -> None:
    """The reason the field exists at all: C09's model is a different decision, measured on a
    different workload, and a change to it must not reach the counter."""
    from jbg_ai.assist.constants import DEFAULT_ASSIST_MODEL

    built, _ = _built_client(
        issue_token,
        jpv_rag_llm_api_key="sk-enrichment",
        jpv_rag_llm_model="openai/gpt-4o",
    )

    assert built is not None
    assert built.model_id == DEFAULT_ASSIST_MODEL == "openai/gpt-4o-mini"


# --- C31 · the classifier's own credential, its own model, and the chain --------------------


def _built_router(issue_token: Callable[..., str], **overrides):
    """Drive one FREE-QUERY request through the real resolution and hand back the client built.

    A free query and not an anchored piece: the classifier is resolved for every request the
    route serves, but only the free-query mode ever calls it, so exercising it here is what
    makes the resolution chain observable through the route rather than only through settings.
    """
    from jbg_ai.api.main import create_app

    app = create_app(build_settings(stub_mode=False, **overrides))
    app.state.retrieval_embed = LocalEmbeddingClient()
    app.state.retrieval_search = FakeProductSearch(_rows())
    app.state.knowledge_index = InMemoryKnowledgeIndex(chunks=chunk_corpus(load_corpus()))

    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {issue_token()}"})
    response = client.post("/v1/assist/sale", json={"query": "un anillo de plata"})

    return getattr(app.state, "assist_router_client", None), response


def test_the_classifier_credential_falls_back_through_the_three_links(
    issue_token: Callable[..., str],
) -> None:
    """HU escenario 17. Router, then assist, then enrichment — C30b opened the last two links
    and this prepends one, so a deployment that sets none of them keeps working."""
    dedicated, _ = _built_router(
        issue_token,
        jpv_rag_llm_api_key="sk-enrichment",
        jpv_assist_llm_api_key="sk-assist",
        jpv_router_llm_api_key="sk-router",
    )
    assert dedicated is not None and dedicated._api_key == "sk-router"

    middle, _ = _built_router(
        issue_token,
        jpv_rag_llm_api_key="sk-enrichment",
        jpv_assist_llm_api_key="sk-assist",
    )
    assert middle is not None and middle._api_key == "sk-assist"

    last, response = _built_router(issue_token, jpv_rag_llm_api_key="sk-enrichment")
    assert response.status_code == 200
    assert last is not None and last._api_key == "sk-enrichment"


def test_with_no_credential_at_all_no_classifier_is_constructed(
    issue_token: Callable[..., str],
) -> None:
    """HU escenario 17, last clause, and the rollback. Not a 503 and not a refusal: the answer
    this capability served before it routed anything, with the intent saying so."""
    built, response = _built_router(issue_token)

    assert built is None
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "unclassified"
    assert body["clarification_question"] is None


def test_which_classifier_credential_is_in_force_is_recorded_without_the_key(
    issue_token: Callable[..., str], caplog: pytest.LogCaptureFixture
) -> None:
    """HU escenario 17. `stage=router_client … credential=…` is the verification the deployment
    makes without opening a console or reading a key; its absence says no client was built."""
    import logging

    from jbg_ai.api.main import create_app

    app = create_app(build_settings(stub_mode=False, jpv_rag_llm_api_key="sk-enrichment"))
    app.state.retrieval_embed = LocalEmbeddingClient()
    app.state.retrieval_search = FakeProductSearch(_rows())
    app.state.knowledge_index = InMemoryKnowledgeIndex(chunks=chunk_corpus(load_corpus()))
    logging.getLogger().addHandler(caplog.handler)
    with caplog.at_level(logging.INFO):
        with TestClient(app) as client:
            client.post(
                "/v1/assist/sale",
                json={"query": "un anillo de plata"},
                headers={"Authorization": f"Bearer {issue_token()}"},
            )

    emitted = "\n".join(record.getMessage() for record in caplog.records)
    assert "stage=router_client" in emitted
    assert "credential=rag_fallback" in emitted
    assert "sk-enrichment" not in emitted, "a credential never reaches a log line"


def test_the_configured_classifier_model_and_timeout_reach_the_client(
    issue_token: Callable[..., str],
) -> None:
    """Both knobs have to arrive where the call is made, or they are settings that change
    nothing — the failure mode of every knob added one layer away from where it is read."""
    from jbg_ai.assist.constants import DEFAULT_ROUTER_MODEL, ROUTER_TIMEOUT_SECONDS

    built, _ = _built_router(
        issue_token,
        jpv_rag_llm_api_key="sk-enrichment",
        jpv_router_llm_model="openai/gpt-4.1-nano",
        jpv_router_timeout_seconds=1.25,
    )

    assert built is not None
    assert built.model_id == "openai/gpt-4.1-nano"
    assert built._timeout == 1.25
    assert ROUTER_TIMEOUT_SECONDS == 2.0, "declared NOT calibrated, and pinned to that claim"
    # Moved from `gpt-4o-mini` BY the measurement: same prompt, the mini arm silenced three
    # answerable queries and the veto rejected it. Pinned to the arm that passed.
    assert DEFAULT_ROUTER_MODEL == "openai/gpt-4o"


def test_the_argument_model_cannot_move_the_classifier_model(
    issue_token: Callable[..., str],
) -> None:
    """D9, as the reason the field exists. ~30 output tokens against a paragraph is not the
    same call, and sharing a variable would make any cost comparison between them false."""
    from jbg_ai.assist.constants import DEFAULT_ROUTER_MODEL

    built, _ = _built_router(
        issue_token,
        jpv_rag_llm_api_key="sk-enrichment",
        jpv_assist_llm_model="openai/gpt-4.1-mini",
        jpv_rag_llm_model="openai/gpt-4o",
    )

    assert built is not None
    assert built.model_id == DEFAULT_ROUTER_MODEL
