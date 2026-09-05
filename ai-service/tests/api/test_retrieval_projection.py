"""HTTP behaviour of the point-of-sale projection guards. C22.

The unit tests next door pin what the orchestrator decides. These pin what the caller
actually receives, which is a different question and the one the operator's panel reads:
a 503 and a 200-with-nothing look identical from inside the retriever and completely
different from outside it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from jbg_ai.api.main import create_app
from support.fake_embedding_client import FakeEmbeddingClient
from support.fake_product_search import (
    FakeAssignment,
    FakeIndexedRow,
    FakeProductSearch,
)
from support.paths import OPENAPI_SNAPSHOT
from support.settings import OTHER_POS_ID, TOKEN_POS_ID, build_settings

MINE = UUID(TOKEN_POS_ID)
THEIRS = UUID(OTHER_POS_ID)

A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
FAMILY = UUID("11111111-1111-1111-1111-111111111111")

QUERY = {"query": "anillo de plata", "top_k": 5}


def row(product_id: UUID, sku: str, distance: float) -> FakeIndexedRow:
    return FakeIndexedRow(
        product_id=product_id,
        sku=sku,
        distance=distance,
        materials=["plata"],
        family_id=FAMILY,
        piece_type="anillo",
        doc_text="Tipo: anillo. Materiales: plata.",
    )


def real_app(search: FakeProductSearch, **overrides):
    app = create_app(build_settings(stub_mode=False, **overrides))
    app.state.retrieval_embed = FakeEmbeddingClient()
    app.state.retrieval_search = search
    return app


def post(app, token: str, body: dict | None = None):
    with TestClient(app) as client:
        return client.post(
            "/v1/retrieval/products",
            json=body or QUERY,
            headers={"Authorization": f"Bearer {token}"},
        )


def test_an_empty_projection_is_503_and_not_a_successful_empty_list(
    issue_token: Callable[..., str],
) -> None:
    app = real_app(FakeProductSearch([row(A, "S1", 0.2)], assignments=[]))

    response = post(app, issue_token())

    assert response.status_code == 503
    assert "projection" in response.json()["detail"]
    assert "results" not in response.json()


def test_health_stays_200_when_the_projection_is_empty(
    issue_token: Callable[..., str],
) -> None:
    """Retrieval refuses; the service is not down."""
    app = real_app(FakeProductSearch([row(A, "S1", 0.2)], assignments=[]))

    with TestClient(app) as client:
        assert post(app, issue_token()).status_code == 503
        assert client.get("/health").status_code == 200


def test_health_stays_200_when_the_projection_is_stale(
    issue_token: Callable[..., str],
) -> None:
    app = real_app(
        FakeProductSearch(
            [row(A, "S1", 0.2)],
            assignments=[FakeAssignment(MINE, A)],
            synced_at=datetime.now(tz=UTC) - timedelta(days=2),
        )
    )

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert post(app, issue_token()).status_code == 200


def test_a_malformed_pos_id_claim_is_422(issue_token: Callable[..., str]) -> None:
    app = real_app(
        FakeProductSearch([row(A, "S1", 0.2)], assignments=[FakeAssignment(MINE, A)])
    )

    response = post(app, issue_token(pos_id="POS-B"))

    assert response.status_code == 422
    assert "pos_id" in response.json()["detail"]


def test_the_response_reports_the_projection_age(
    issue_token: Callable[..., str],
) -> None:
    app = real_app(
        FakeProductSearch(
            [row(A, "S1", 0.2)],
            assignments=[FakeAssignment(MINE, A)],
            synced_at=datetime.now(tz=UTC) - timedelta(seconds=45),
        )
    )

    body = post(app, issue_token()).json()

    assert body["projection_age_seconds"] is not None
    assert 30 < body["projection_age_seconds"] < 180


def test_a_stale_projection_answers_200_with_a_possibly_short_page(
    issue_token: Callable[..., str],
) -> None:
    """Degrading openly: the filter is dropped, the age is told, nothing is hidden."""
    app = real_app(
        FakeProductSearch(
            [row(A, "MINE", 0.3), row(B, "THEIRS", 0.2)],
            assignments=[FakeAssignment(MINE, A), FakeAssignment(THEIRS, B)],
            synced_at=datetime.now(tz=UTC) - timedelta(days=1),
        )
    )

    response = post(app, issue_token())

    assert response.status_code == 200
    body = response.json()
    assert {item["sku"] for item in body["results"]} == {"MINE", "THEIRS"}
    assert body["projection_age_seconds"] > 3600


def test_the_committed_contract_carries_the_new_field() -> None:
    """Regenerated deliberately, with the README recipe, and committed with the change."""
    contract = json.loads(OPENAPI_SNAPSHOT.read_text(encoding="utf-8"))
    schema = contract["components"]["schemas"]["RetrievalResponse"]

    assert "projection_age_seconds" in schema["properties"]
    assert "projection_age_seconds" not in schema.get("required", [])
    assert "projection_age_seconds" not in contract["components"]["schemas"][
        "RetrievalRequest"
    ]["properties"], "the request schema stays frozen"
