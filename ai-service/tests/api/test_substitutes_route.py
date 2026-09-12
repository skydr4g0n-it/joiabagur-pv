"""Real POST /v1/retrieval/substitutes: the last closeable 501 of the contract. C26.

The route-level half of the change. What is asserted here and not in
`tests/retrieval/test_substitutes.py` is everything that only exists once FastAPI is in the
picture: the stub still serving under `STUB_MODE`, the status codes, and the frozen snapshot.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi.testclient import TestClient

from jbg_ai.api.main import create_app
from jbg_ai.api.schemas.retrieval import SubstitutesResponse
from support.fake_product_search import FakeIndexedRow, FakeProductSearch
from support.settings import build_settings

SOURCE = UUID("00000000-0000-4000-8000-000000000013")
SIBLING = UUID("00000000-0000-4000-8000-000000000014")


def _rows() -> list[FakeIndexedRow]:
    return [
        FakeIndexedRow(
            product_id=SOURCE,
            sku="SKU13",
            distance=0.0,
            materials=["plata"],
            piece_type="anillo",
            size_label="M",
        ),
        FakeIndexedRow(
            product_id=SIBLING,
            sku="SKU14",
            distance=0.0868,
            materials=["plata"],
            piece_type="anillo",
            size_label="L",
        ),
    ]


def _real_app(search: FakeProductSearch | None = None, **overrides):
    app = create_app(build_settings(stub_mode=False, **overrides))
    if search is not None:
        app.state.retrieval_search = search
    return app


def _post(app, token: str, **body):
    payload = {"product_id": str(SOURCE), "top_k": 5}
    payload.update(body)
    with TestClient(app) as client:
        return client.post(
            "/v1/retrieval/substitutes",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )


def test_stub_mode_still_serves_the_c02_substitutes_fixture(
    issue_token: Callable[..., str]
) -> None:
    """The committed contract tests measure the CONTRACT, so the fixture has to survive.

    Its invented signals (`0,9 - i*0,01`) are exactly why it must not reach real mode, and
    exactly why it is still the right thing to serve when stubs are on: a client wiring
    itself against the frozen schema needs a deterministic body and no index at all.
    """
    search = FakeProductSearch(_rows())
    app = create_app(build_settings(stub_mode=True))
    app.state.retrieval_search = search

    response = _post(app, issue_token())

    assert response.status_code == 200
    parsed = SubstitutesResponse.model_validate(response.json())
    assert parsed.candidates_returned == 15
    assert parsed.results[0].product_id.startswith("P-")
    # No database session was opened: the stub is a fixture, not a shortcut through the port.
    assert search.source_document_calls == []
    assert search.neighbour_calls == []


def test_real_mode_returns_substitutes_instead_of_501(
    issue_token: Callable[..., str]
) -> None:
    search = FakeProductSearch(_rows())

    response = _post(_real_app(search), issue_token())

    assert response.status_code == 200
    parsed = SubstitutesResponse.model_validate(response.json())
    assert [item.sku for item in parsed.results] == ["SKU14"]
    assert parsed.low_confidence is False
    assert parsed.results[0].similarity_signals.visual_similarity is None
    assert search.neighbour_calls


def test_the_route_no_longer_defers_to_a_later_change(
    issue_token: Callable[..., str]
) -> None:
    """The obligation `vector-retrieval` used to impose, asserted in the negative."""
    response = _post(_real_app(FakeProductSearch(_rows())), issue_token())

    assert response.status_code != 501
    assert "later change" not in response.text
    assert "C26" not in response.text


def test_an_unusable_source_product_is_an_explicit_error_and_not_an_empty_page(
    issue_token: Callable[..., str]
) -> None:
    """422, with the cause named. Never a 200 whose empty list means two different things."""
    response = _post(
        _real_app(FakeProductSearch(_rows())),
        issue_token(),
        product_id="00000000-0000-4000-8000-000000009999",
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "not present in the retrieval index" in detail
    assert "results" not in response.json()


def test_a_source_product_without_an_embedding_is_rejected_by_name(
    issue_token: Callable[..., str]
) -> None:
    rows = _rows()
    rows[0] = FakeIndexedRow(
        product_id=SOURCE,
        sku="SKU13",
        distance=0.0,
        materials=["plata"],
        piece_type="anillo",
        size_label="M",
        has_embedding=False,
    )

    response = _post(_real_app(FakeProductSearch(rows)), issue_token())

    assert response.status_code == 422
    assert "no embedding" in response.json()["detail"]


def test_real_mode_without_a_database_is_503_and_not_501(
    issue_token: Callable[..., str]
) -> None:
    """No embedding key is demanded, because this route embeds nothing. Only the database."""
    response = _post(_real_app(), issue_token())

    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]


def test_the_token_scope_wins_over_the_body(issue_token: Callable[..., str]) -> None:
    """`pos_id` in the body is accepted for compatibility and ignored, as on products."""
    search = FakeProductSearch(_rows())

    response = _post(
        _real_app(search),
        issue_token(),
        pos_id="ffffffff-ffff-4fff-8fff-ffffffffffff",
    )

    assert response.status_code == 200
    parsed = SubstitutesResponse.model_validate(response.json())
    assert parsed.effective_pos_id != "ffffffff-ffff-4fff-8fff-ffffffffffff"
    assert search.neighbour_calls[-1]["signal_pos_id"] != UUID(
        "ffffffff-ffff-4fff-8fff-ffffffffffff"
    )


def test_authentication_precedes_everything(issue_token: Callable[..., str]) -> None:
    with TestClient(_real_app(FakeProductSearch(_rows()))) as client:
        response = client.post(
            "/v1/retrieval/substitutes", json={"product_id": str(SOURCE), "top_k": 5}
        )

    assert response.status_code == 401
