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


def test_defaults_remain_gpt4o_and_concurrency_8() -> None:
    from jbg_ai.enrichment.constants import (
        DEFAULT_RAG_LLM_CONCURRENCY,
        DEFAULT_RAG_LLM_MODEL,
        MAX_ENRICH_PROVIDER_ATTEMPTS,
    )

    assert DEFAULT_RAG_LLM_MODEL == "openai/gpt-4o"
    assert DEFAULT_RAG_LLM_CONCURRENCY == 8
    assert MAX_ENRICH_PROVIDER_ATTEMPTS == 4
    source = Path(__import__("jbg_ai.enrichment.llm", fromlist=["llm"]).__file__).read_text(
        encoding="utf-8"
    )
    assert '"num_retries": 0' in source


def test_retry_on_429() -> None:
    calls = {"n": 0}
    extraction = EnrichmentExtraction(piece_type="anillo")

    async def _complete(product: EnrichProductInput, prompt: str) -> str:
        _ = product, prompt
        calls["n"] += 1
        if calls["n"] == 1:
            error = RuntimeError("rate limited")
            error.status_code = 429  # type: ignore[attr-defined]
            raise error
        return extraction.model_dump_json()

    sleeps: list[float] = []

    async def _sleep(delay: float) -> None:
        sleeps.append(delay)

    client = LiteLlmEnrichClient(
        api_key="sk-test", complete=_complete, sleep=_sleep, max_attempts=4
    )
    product = EnrichProductInput(product_id="P-1", sku="SKU-1", name="Anillo")
    got = asyncio.run(client.extract(product, "prompt"))

    assert got.piece_type == "anillo"
    assert calls["n"] == 2
    assert sleeps == [2.0]


def test_retry_on_rate_limit_error_by_type_name() -> None:
    class RateLimitError(Exception):
        pass

    calls = {"n": 0}
    extraction = EnrichmentExtraction(materials=["plata"])

    async def _complete(product: EnrichProductInput, prompt: str) -> str:
        _ = product, prompt
        calls["n"] += 1
        if calls["n"] == 1:
            raise RateLimitError("tpm")
        return extraction.model_dump_json()

    sleeps: list[float] = []

    async def _sleep(delay: float) -> None:
        sleeps.append(delay)

    client = LiteLlmEnrichClient(
        api_key="sk-test", complete=_complete, sleep=_sleep
    )
    product = EnrichProductInput(product_id="P-1", sku="SKU-1", name="Pulsera")
    got = asyncio.run(client.extract(product, "prompt"))

    assert got.materials == ["plata"]
    assert calls["n"] == 2
    assert sleeps == [2.0]


def test_non_retryable_error_is_not_retried() -> None:
    calls = {"n": 0}

    async def _complete(product: EnrichProductInput, prompt: str) -> str:
        _ = product, prompt
        calls["n"] += 1
        error = RuntimeError("bad request")
        error.status_code = 400  # type: ignore[attr-defined]
        raise error

    sleeps: list[float] = []

    async def _sleep(delay: float) -> None:
        sleeps.append(delay)

    client = LiteLlmEnrichClient(
        api_key="sk-test", complete=_complete, sleep=_sleep
    )
    product = EnrichProductInput(product_id="P-1", sku="SKU-1", name="Anillo")
    try:
        asyncio.run(client.extract(product, "prompt"))
    except RuntimeError as exc:
        assert "bad request" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")

    assert calls["n"] == 1
    assert sleeps == []


def test_one_failed_extract_does_not_drop_the_rest_of_the_batch() -> None:
    async def _run() -> None:
        fake = FakeEnrichLlm(
            default=EnrichmentExtraction(piece_type="anillo"),
            errors={"SKU-FAIL": RuntimeError("rate limited")},
        )
        settings = build_settings(
            stub_mode=False,
            jpv_rag_llm_api_key="sk-test",
            jpv_rag_llm_concurrency=8,
        )
        request = EnrichRequest(
            products=[
                EnrichProductInput(product_id="P-1", sku="SKU-1", name="Anillo"),
                EnrichProductInput(product_id="P-2", sku="SKU-FAIL", name="Colgante"),
                EnrichProductInput(product_id="P-3", sku="SKU-3", name="Pulsera"),
            ]
        )
        principal = ServicePrincipal(user_id="u-1", role="Operator", trace_id="t-1")
        response = await enrich_products(request, principal, settings, fake)
        assert [profile.sku for profile in response.profiles] == ["SKU-1", "SKU-3"]
        assert len(fake.calls) == 3

    asyncio.run(_run())


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
