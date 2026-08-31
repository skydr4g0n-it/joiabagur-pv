"""Family suggestion route contract tests (no LLM / embeddings / RDS). C18a."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jbg_ai.api.schemas.families import FamilySuggestResponse
from jbg_ai.config.settings import Settings

ROUTE = "/v1/families/suggest"


def test_stub_matches_response_schema(
    client: TestClient, auth_headers: dict[str, str], forbid_network: None
) -> None:
    response = client.post(ROUTE, json={}, headers=auth_headers)

    assert response.status_code == 200
    parsed = FamilySuggestResponse.model_validate(response.json())
    assert parsed.proposals


def test_stub_populates_all_three_lists(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A stub returning only proposals lets a client ship without handling refusals.

    Both kinds of omission are where the catalogue problems surface, so the fixture
    exercises them.
    """
    body = client.post(ROUTE, json={}, headers=auth_headers).json()

    assert body["proposals"]
    assert body["rejected_groups"]
    assert body["excluded_products"]
    assert "already_in_family_count" in body


def test_members_carry_nullable_variant_and_ordered_positions(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    members = client.post(ROUTE, json={}, headers=auth_headers).json()["proposals"][0][
        "members"
    ]

    assert [member["position"] for member in members] == list(range(len(members)))
    for member in members:
        # An unknown variant must serialize as null, never be dropped: the .NET
        # client maps it to a nullable and the distinction carries meaning.
        assert "variant_label" in member
        assert "flagged_for_review" in member


def test_a_flagged_member_reports_its_margin(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    members = client.post(ROUTE, json={}, headers=auth_headers).json()["proposals"][0][
        "members"
    ]
    flagged = [member for member in members if member["flagged_for_review"]]

    assert flagged, "the fixture must exercise the veto mark"
    assert flagged[0]["margin"] is not None
    assert flagged[0]["review_reason"]


def test_route_requires_the_service_token(client: TestClient) -> None:
    response = client.post(ROUTE, json={})

    assert response.status_code in (401, 403)


def test_rejects_a_max_proposals_outside_the_contract(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(ROUTE, json={"max_proposals": 0}, headers=auth_headers)

    assert response.status_code == 422


def test_stub_opens_no_database_connection(
    client: TestClient, auth_headers: dict[str, str], forbid_network: None
) -> None:
    """`forbid_network` fails the test if the route reaches for anything outside."""
    assert client.post(ROUTE, json={}, headers=auth_headers).status_code == 200


@pytest.mark.parametrize("payload", [{}, {"piece_type": "anillo"}, {"max_proposals": 5}])
def test_stub_is_deterministic(
    client: TestClient, auth_headers: dict[str, str], payload: dict[str, object]
) -> None:
    first = client.post(ROUTE, json=payload, headers=auth_headers).json()
    second = client.post(ROUTE, json=payload, headers=auth_headers).json()

    assert first == second


def test_real_mode_without_a_database_answers_503(
    minimal_settings: Settings, auth_headers: dict[str, str]
) -> None:
    """503 and not a degraded answer: there is no honest partial grouping."""
    from jbg_ai.api.main import create_app

    unstubbed_settings = minimal_settings.model_copy(
        update={"stub_mode": False, "database_url": None}
    )
    with TestClient(create_app(unstubbed_settings)) as unstubbed:
        response = unstubbed.post(ROUTE, json={}, headers=auth_headers)

    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]
