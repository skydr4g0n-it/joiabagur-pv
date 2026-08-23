"""LiteLLM port, fake injection, concurrency. Delivered by C09."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.main import create_app
from jbg_ai.api.schemas.enrich import EnrichProductInput, EnrichRequest
from jbg_ai.enrichment.constants import PROMPT_VERSION
from jbg_ai.enrichment.llm import LiteLlmEnrichClient
from jbg_ai.enrichment.pipeline import enrich_products, load_prompt
from jbg_ai.enrichment.schema import EnrichmentExtraction
from support.fake_enrich_llm import FakeEnrichLlm
from support.paths import AI_SERVICE_ROOT
from support.settings import build_settings


def test_enrich_llm_uses_litellm_not_openai_catalog_client() -> None:
    source = Path(__import__("jbg_ai.enrichment.llm", fromlist=["llm"]).__file__).read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert "litellm" in source
    assert any(name == "litellm" or name.startswith("litellm") for name in imported) or "from litellm import" in source
    assert "jbg_ai.data" not in imported and "from jbg_ai.data" not in source
    client = LiteLlmEnrichClient(api_key="sk-test", model="openai/gpt-4o")
    assert client.model_id == "openai/gpt-4o"
    assert "OpenAICatalogLlm" not in imported


def test_prompt_version_is_enrichment_v1() -> None:
    public = AI_SERVICE_ROOT / "prompts" / "enrichment" / "v1.md"
    prompt = load_prompt()

    assert public.is_file()
    assert PROMPT_VERSION == "enrichment/v1"
    assert prompt == public.read_text(encoding="utf-8")
    assert "title" in prompt.lower()
    assert "style_tags" in prompt
    assert not (AI_SERVICE_ROOT / "src" / "jbg_ai" / "enrichment" / "prompt_v1.md").exists()


def test_concurrency_setting_caps_in_flight_calls() -> None:
    async def _run() -> None:
        fake = FakeEnrichLlm(delay=0.05, default=EnrichmentExtraction())
        settings = build_settings(
            stub_mode=False,
            jpv_rag_llm_api_key="sk-test",
            jpv_rag_llm_concurrency=8,
        )
        request = EnrichRequest(
            products=[
                EnrichProductInput(product_id=f"P-{index}", sku=f"SKU-{index}", name="Anillo")
                for index in range(50)
            ]
        )
        principal = ServicePrincipal(user_id="u-1", role="Operator", trace_id="t-1")
        response = await enrich_products(request, principal, settings, fake)
        assert len(response.profiles) == 50
        assert len(fake.calls) == 50
        assert fake.max_in_flight <= 8
        assert fake.max_in_flight >= 2

    asyncio.run(_run())


def test_unit_suite_makes_no_provider_calls(forbid_network: None) -> None:
    _ = forbid_network
    from jbg_ai.api import main as api_main

    source = Path(api_main.__file__).read_text(encoding="utf-8")
    assert "jbg_ai.data" not in source


def test_real_mode_does_not_use_stub_cycle(issue_token) -> None:
    fake = FakeEnrichLlm(
        default=EnrichmentExtraction(piece_type="anillo", materials=["plata"]),
    )
    settings = build_settings(
        stub_mode=False,
        jpv_rag_llm_api_key="sk-test",
        jpv_rag_llm_model="openai/gpt-4o",
    )
    app = create_app(settings)
    app.state.enrich_llm = fake
    headers = {"Authorization": f"Bearer {issue_token()}"}

    with TestClient(app) as client:
        response = client.post(
            "/v1/enrich/products",
            json={"products": [{"product_id": "P-1", "sku": "SKU-1", "name": "Anillo de plata"}]},
            headers=headers,
        )

    body = response.json()
    assert response.status_code == 200, response.text
    assert body["prompt_version"] == PROMPT_VERSION
    assert body["usage"]["model"] == fake.model_id
    profile = body["profiles"][0]
    assert profile["title"] is None
    assert profile["family_id"] is None
    assert "stub_response" not in profile["warnings"]
    assert fake.calls


def test_real_mode_without_key_fails_explicitly(issue_token) -> None:
    settings = build_settings(stub_mode=False, jpv_rag_llm_api_key=None)
    app = create_app(settings)
    headers = {"Authorization": f"Bearer {issue_token()}"}

    with TestClient(app) as client:
        response = client.post(
            "/v1/enrich/products",
            json={"products": [{"product_id": "P-1", "sku": "SKU-1", "name": "Anillo"}]},
            headers=headers,
        )

    assert response.status_code == 503
    assert response.status_code != 501
    assert "JPV_RAG_LLM_API_KEY" in response.json()["detail"]
