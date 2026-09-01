"""Family audit route contract tests (no LLM / embeddings / RDS). C18b — tenth path."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jbg_ai.api.schemas.families import FamilyAuditResponse

ROUTE = "/v1/families/audit"


def test_stub_matches_response_schema(
    client: TestClient, auth_headers: dict[str, str], forbid_network: None
) -> None:
    response = client.post(ROUTE, json={}, headers=auth_headers)

    assert response.status_code == 200
    parsed = FamilyAuditResponse.model_validate(response.json())
    assert parsed.flagged_members
    assert parsed.orphan_candidates


def test_stub_populates_both_findings_and_both_refusals(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A stub returning only findings lets a client ship without rendering a refusal.

    Same reasoning as the suggestion stub, and the same consequence: the refusals are
    where the catalogue problems surface.
    """
    body = client.post(ROUTE, json={}, headers=auth_headers).json()

    assert body["flagged_members"]
    assert body["orphan_candidates"]
    assert body["rejected_groups"]
    assert body["excluded_products"]
    assert body["families_reviewed_count"] >= 1
    assert body["members_examined_count"] >= 1


def test_a_flagged_member_carries_its_margin_and_the_stranger(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The margin is what the reviewer judges by; without it the flag is an assertion."""
    flagged = client.post(ROUTE, json={}, headers=auth_headers).json()["flagged_members"][0]

    assert flagged["margin"] > 0
    assert flagged["family_id"]
    assert flagged["stranger_family_id"]
    assert flagged["reason"] == "closer_to_another_family"
    # Null is the base piece, a legitimate variant value: present and nullable, never
    # dropped, because the .NET client maps it to a nullable and the distinction means
    # "this is the plain one" rather than "nobody decided yet".
    assert "variant_label" in flagged


def test_a_candidate_carries_the_evidence_a_reviewer_needs(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    candidate = client.post(ROUTE, json={}, headers=auth_headers).json()[
        "orphan_candidates"
    ][0]

    assert candidate["margin"] == pytest.approx(
        candidate["similarity"] - candidate["worst_sibling"]
    )
    assert candidate["data_origin"] in {"real", "synthetic"}
    assert 0 <= candidate["purity"] <= 5
    assert candidate["family_id"]


def test_purity_is_reported_but_is_not_the_criterion(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The stub nominates on margin while carrying a purity below any majority.

    Pinned because purity is the intuitive criterion and the measured wrong one: over
    this corpus it fires on 55 synthetic products against 19 real. A client that
    started filtering on it would silently adopt the mistake.
    """
    candidate = client.post(ROUTE, json={}, headers=auth_headers).json()[
        "orphan_candidates"
    ][0]

    assert candidate["margin"] > 0
    assert candidate["purity"] < 3


def test_judged_pairs_are_omitted(client: TestClient, auth_headers: dict[str, str]) -> None:
    body = client.post(ROUTE, json={}, headers=auth_headers).json()
    flagged = body["flagged_members"][0]
    orphan = body["orphan_candidates"][0]

    filtered = client.post(
        ROUTE,
        json={
            "judged_pairs": [
                {"product_id": flagged["product_id"], "family_id": flagged["family_id"]},
                {"product_id": orphan["product_id"], "family_id": orphan["family_id"]},
            ]
        },
        headers=auth_headers,
    ).json()

    assert not filtered["flagged_members"]
    assert not filtered["orphan_candidates"]
    # Refusals are never filtered by a verdict: they are catalogue findings, not
    # membership questions, and nothing was dismissed about them.
    assert filtered["rejected_groups"]
    assert filtered["excluded_products"]


def test_judged_pairs_are_not_remembered_between_calls(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The service stores no verdict. The caller brings what it knows, every time."""
    body = client.post(ROUTE, json={}, headers=auth_headers).json()
    orphan = body["orphan_candidates"][0]

    client.post(
        ROUTE,
        json={
            "judged_pairs": [
                {"product_id": orphan["product_id"], "family_id": orphan["family_id"]}
            ]
        },
        headers=auth_headers,
    )
    again = client.post(ROUTE, json={}, headers=auth_headers).json()

    assert again["orphan_candidates"]


def test_the_candidate_cap_never_truncates_a_refusal(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    body = client.post(ROUTE, json={"max_orphans": 1}, headers=auth_headers).json()

    assert len(body["orphan_candidates"]) <= 1
    assert body["rejected_groups"]
    assert body["excluded_products"]


def test_the_route_requires_the_service_token(client: TestClient) -> None:
    response = client.post(ROUTE, json={})

    assert response.status_code in {401, 403}


def test_margins_out_of_range_are_refused(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A similarity margin above one cannot describe a cosine, so it is a typo.

    Answering 200 with an empty body would look exactly like a clean catalogue.
    """
    response = client.post(ROUTE, json={"orphan_margin": 1.5}, headers=auth_headers)

    assert response.status_code == 422
