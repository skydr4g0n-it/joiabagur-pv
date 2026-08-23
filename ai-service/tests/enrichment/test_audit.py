"""Batch auditor lives outside the HTTP POST. Delivered by C09."""

from __future__ import annotations

from fastapi.testclient import TestClient

from jbg_ai.api.main import create_app
from jbg_ai.api.schemas.enrich import ProposedList, ProposedProfile
from jbg_ai.enrichment.audit import AuditRecord, audit_batch
from jbg_ai.enrichment.schema import EnrichmentExtraction
from support.fake_enrich_llm import FakeEnrichLlm
from support.settings import build_settings


def _profile(*, sku: str, tags: list[str] | None = None) -> ProposedProfile:
    tag_list = tags or []
    empty = ProposedList(value=[], confidence=0.2, source="inferred")
    filled = ProposedList(value=tag_list, confidence=0.85, source="inferred")
    return ProposedProfile(
        product_id=sku,
        sku=sku,
        materials=empty,
        color_tags=filled if tag_list else empty,
        style_tags=empty,
        occasion_tags=empty,
    )


def test_original_or_short_may_have_empty_tags() -> None:
    records = [
        AuditRecord(sku="O1", profile=_profile(sku="O1"), stratum="original"),
        AuditRecord(sku="S1", profile=_profile(sku="S1"), stratum="short"),
        AuditRecord(sku="A1", profile=_profile(sku="A1", tags=["dorado"]), stratum="ai_assisted"),
    ]

    result = audit_batch(records)

    assert result.ok


def test_sparse_requires_at_least_one_tag_list() -> None:
    records = [AuditRecord(sku="SP1", profile=_profile(sku="SP1"), stratum="sparse")]

    result = audit_batch(records)

    assert not result.ok
    assert any("sparse" in failure for failure in result.failures)


def test_tag_coverage_gate_is_evaluated_per_text_provenance() -> None:
    records = [
        AuditRecord(sku="O1", profile=_profile(sku="O1"), stratum="original"),
        AuditRecord(sku="SH1", profile=_profile(sku="SH1"), stratum="short"),
        AuditRecord(sku="SP1", profile=_profile(sku="SP1", tags=["dorado"]), stratum="sparse"),
        *[
            AuditRecord(
                sku=f"A{index}",
                profile=_profile(sku=f"A{index}", tags=["dorado"]),
                stratum="ai_assisted",
            )
            for index in range(9)
        ],
        AuditRecord(sku="A9", profile=_profile(sku="A9"), stratum="ai_assisted"),
    ]

    result = audit_batch(records)

    assert result.ok


def test_batch_fails_when_sku_is_duplicated() -> None:
    records = [
        AuditRecord(sku="DUP", profile=_profile(sku="DUP", tags=["dorado"]), stratum="ai_assisted"),
        AuditRecord(sku="DUP", profile=_profile(sku="DUP", tags=["dorado"]), stratum="ai_assisted"),
    ]

    result = audit_batch(records)

    assert not result.ok
    assert any("duplicate SKUs" in failure for failure in result.failures)
    assert any("DUP" in failure for failure in result.failures)


def test_batch_fails_when_tag_coverage_below_threshold() -> None:
    records = [
        AuditRecord(sku=f"A{index}", profile=_profile(sku=f"A{index}"), stratum="ai_assisted")
        for index in range(10)
    ]

    result = audit_batch(records)

    assert not result.ok
    assert any("ai_assisted" in failure for failure in result.failures)


def test_http_batch_with_empty_tags_returns_200_not_422(issue_token) -> None:
    fake = FakeEnrichLlm(default=EnrichmentExtraction())
    settings = build_settings(stub_mode=False, jpv_rag_llm_api_key="sk-test")
    app = create_app(settings)
    app.state.enrich_llm = fake
    headers = {"Authorization": f"Bearer {issue_token()}"}

    with TestClient(app) as client:
        response = client.post(
            "/v1/enrich/products",
            json={
                "products": [
                    {"product_id": "P-1", "sku": "SKU-1", "name": "Pieza original"},
                    {"product_id": "P-2", "sku": "SKU-2", "name": "Otra pieza"},
                ]
            },
            headers=headers,
        )

    assert response.status_code == 200, response.text
    assert response.status_code != 422
    for profile in response.json()["profiles"]:
        assert profile["color_tags"]["value"] == []
        assert profile["style_tags"]["value"] == []
        assert profile["occasion_tags"]["value"] == []
