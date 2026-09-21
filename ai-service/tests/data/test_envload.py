"""Local env file discovery. Delivered by C06b."""

from __future__ import annotations

from jbg_ai.data.envload import local_env_paths
from jbg_ai.data.paths import REPO_ROOT


def test_local_env_prefers_backend_dotenv_next_to_compose() -> None:
    paths = local_env_paths()
    assert paths[0] == REPO_ROOT / "backend" / ".env"
    example = REPO_ROOT / "backend" / ".env.example"
    assert example.is_file()
    text = example.read_text(encoding="utf-8")
    assert "JPV_CATALOG_LLM_API_KEY" in text
    assert "JPV_RAG_LLM_API_KEY" in text
    assert "JPV_PGHOST" in text


def test_every_provider_credential_the_service_reads_is_documented_in_the_example() -> None:
    """A credential a deployment cannot discover is a credential nobody separates. C32b.

    **Scoped to credentials and models on purpose, and not to every `JPV_*` setting.** Seventeen
    retrieval, fusion and abstention knobs are deliberately documented in the service README
    instead of here — they are tuning, not secrets — so a check over all of them would go red
    for reasons that have nothing to do with whether a key can be found.

    These are the ones where being undiscoverable has a cost: each is the head of a fallback
    chain, and an operator who does not know a variable exists silently bills one stage against
    another's key. That is exactly what happened to the agent loop before C32b documented it —
    the chain resolved `assist_fallback` and the separation the variable was created for was
    not obtained.
    """
    from jbg_ai.config import Settings

    text = (REPO_ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    credentials = sorted(
        name.upper()
        for name in Settings.model_fields
        if name.startswith("jpv_") and (name.endswith("_api_key") or name.endswith("_llm_model"))
    )

    assert credentials, "the settings must actually declare some"
    for name in credentials:
        assert f"{name}=" in text, f"{name} is not documented in backend/.env.example"

    # The three chains, each with the link order a reader has to be able to follow.
    for chain in ("JPV_AGENT_LLM_API_KEY", "JPV_ROUTER_LLM_API_KEY", "JPV_ASSIST_LLM_API_KEY"):
        assert f"# {chain}=" in text, f"{chain} should be present and commented out"
