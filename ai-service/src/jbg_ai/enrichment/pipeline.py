"""Assemble a ProposedProfile from regex size + model extraction. Delivered by C09."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.schemas.common import Usage
from jbg_ai.api.schemas.enrich import (
    EnrichProductInput,
    EnrichRequest,
    EnrichResponse,
    ProposedList,
    ProposedProfile,
    ProposedText,
)
from jbg_ai.config import Settings
from jbg_ai.enrichment.confidence import list_confidence, scalar_confidence
from jbg_ai.enrichment.constants import (
    CONFIDENCE_ABSENT,
    CONFIDENCE_RULE,
    DEFAULT_RAG_LLM_CONCURRENCY,
    PROMPT_VERSION,
    RESIDUAL_STONE,
)
from jbg_ai.enrichment.llm import EnrichLlm
from jbg_ai.enrichment.schema import EnrichmentExtraction
from jbg_ai.enrichment.size import SizeHit, extract_size
from jbg_ai.enrichment.vocab import ClosedVocab, Vocabularies, fold, load_vocabularies

logger = logging.getLogger(__name__)

_GEM_HINTS = (
    "piedra",
    "piedras",
    "gema",
    "gemas",
    "engaste",
    "engastada",
    "engastado",
    "preciosa",
    "semipreciosa",
    "cristal",
    "cristales",
    "cabujon",
)


_PROMPT_RELATIVE = Path("prompts") / "enrichment" / "v1.md"


def load_prompt() -> str:
    """Load the C09 extraction prompt (`enrichment/v1`).

    Single source of truth: `ai-service/prompts/enrichment/v1.md`. Distinct from
    `prompts/catalog-synth/v3.md` (C06b generate). The Docker image copies
    `prompts/` into `/app/prompts/` (see `ai-service/Dockerfile`); there is no
    second authored copy inside the Python package.
    """
    here = Path(__file__).resolve()
    candidates = (
        here.parents[3] / _PROMPT_RELATIVE,  # src layout: …/ai-service/src/jbg_ai/enrichment/
        Path.cwd() / _PROMPT_RELATIVE,
        Path("/app") / _PROMPT_RELATIVE,
    )
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "enrichment/v1.md not found; expected ai-service/prompts/enrichment/v1.md "
        f"(searched: {', '.join(str(p) for p in candidates)})"
    )


def _joined_text(name: str | None, description: str | None) -> str:
    return f"{name or ''} {description or ''}".strip()


def _text_asserts_gem(name: str | None, description: str | None) -> bool:
    blob = f" {fold(_joined_text(name, description))} "
    return any(f" {hint} " in blob for hint in _GEM_HINTS)


def _accept_list(
    raw_values: list[str],
    vocab: ClosedVocab,
    warnings: list[str],
    field: str,
) -> list[str]:
    accepted: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        resolved = vocab.resolve(raw)
        if resolved is None:
            warnings.append(f"discarded out-of-vocabulary {field} value: {raw}")
            continue
        if resolved not in seen:
            seen.add(resolved)
            accepted.append(resolved)
    return accepted


def _accept_scalar(
    raw: str | None,
    vocab: ClosedVocab,
    warnings: list[str],
    field: str,
) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    resolved = vocab.resolve(raw)
    if resolved is None:
        warnings.append(f"discarded out-of-vocabulary {field} value: {raw}")
        return None
    return resolved


def _resolve_stone(
    raw: str | None,
    *,
    name: str | None,
    description: str | None,
    vocabs: Vocabularies,
    gem_mentioned: bool,
    warnings: list[str],
) -> str | None:
    resolved = vocabs.stone_type.resolve(raw) if raw else None
    gem_in_text = gem_mentioned or _text_asserts_gem(name, description)
    if resolved is not None and resolved != RESIDUAL_STONE:
        return resolved
    if resolved == RESIDUAL_STONE:
        return RESIDUAL_STONE
    if raw and str(raw).strip() and resolved is None:
        warnings.append(f"discarded out-of-vocabulary stone_type value: {raw}")
        return RESIDUAL_STONE if gem_in_text else None
    if gem_in_text:
        return RESIDUAL_STONE
    return None


def _proposed_text(value: str | None, confidence: float, source: str) -> ProposedText | None:
    if value is None:
        return None
    return ProposedText(value=value, confidence=confidence, source=source)  # type: ignore[arg-type]


def assemble_profile(
    product: EnrichProductInput,
    extraction: EnrichmentExtraction,
    *,
    size_hit: SizeHit | None,
    vocabs: Vocabularies,
) -> ProposedProfile:
    warnings: list[str] = []
    name, description = product.name, product.description

    piece_type = _accept_scalar(extraction.piece_type, vocabs.piece_type, warnings, "piece_type")
    materials = _accept_list(extraction.materials, vocabs.materials, warnings, "materials")
    stone_type = _resolve_stone(
        extraction.stone_type,
        name=name,
        description=description,
        vocabs=vocabs,
        gem_mentioned=extraction.gem_mentioned,
        warnings=warnings,
    )
    if stone_type == "perla":
        materials = [item for item in materials if item != "perla"]

    color_tags = _accept_list(extraction.color_tags, vocabs.color_tags, warnings, "color_tags")
    style_tags = _accept_list(extraction.style_tags, vocabs.style_tags, warnings, "style_tags")
    occasion_tags = _accept_list(
        extraction.occasion_tags, vocabs.occasion_tags, warnings, "occasion_tags"
    )

    if size_hit is not None:
        size_label = _proposed_text(size_hit.value, CONFIDENCE_RULE, "rule")
    else:
        inferred_size = _accept_scalar(
            extraction.size_label, vocabs.size_label, warnings, "size_label"
        )
        size_label = _proposed_text(
            inferred_size,
            scalar_confidence(
                inferred_size, name=name, description=description, vocab=vocabs.size_label
            )
            if inferred_size
            else CONFIDENCE_ABSENT,
            "inferred",
        )
        if inferred_size is None:
            size_label = None

    return ProposedProfile(
        product_id=product.product_id,
        sku=product.sku,
        title=None,
        description=None,
        piece_type=_proposed_text(
            piece_type,
            scalar_confidence(piece_type, name=name, description=description, vocab=vocabs.piece_type),
            "inferred",
        ),
        materials=ProposedList(
            value=materials,
            confidence=list_confidence(
                materials, name=name, description=description, vocab=vocabs.materials
            ),
            source="inferred",
        ),
        stone_type=_proposed_text(
            stone_type,
            scalar_confidence(stone_type, name=name, description=description, vocab=vocabs.stone_type),
            "inferred",
        ),
        size_label=size_label,
        color_tags=ProposedList(
            value=color_tags,
            confidence=list_confidence(
                color_tags, name=name, description=description, vocab=vocabs.color_tags
            ),
            source="inferred",
        ),
        style_tags=ProposedList(
            value=style_tags,
            confidence=list_confidence(
                style_tags, name=name, description=description, vocab=vocabs.style_tags
            ),
            source="inferred",
        ),
        occasion_tags=ProposedList(
            value=occasion_tags,
            confidence=list_confidence(
                occasion_tags, name=name, description=description, vocab=vocabs.occasion_tags
            ),
            source="inferred",
        ),
        family_id=None,
        variant_label=None,
        warnings=warnings,
    )


async def enrich_one(
    product: EnrichProductInput,
    llm: EnrichLlm,
    prompt: str,
    vocabs: Vocabularies,
) -> ProposedProfile:
    size_hit = extract_size(product.name, product.description)
    extraction = await llm.extract(product, prompt)
    profile = assemble_profile(product, extraction, size_hit=size_hit, vocabs=vocabs)
    rule_fields = [
        field
        for field in ("size_label",)
        if getattr(profile, field) is not None and getattr(profile, field).source == "rule"
    ]
    logger.info(
        "enriched sku=%s prompt_version=%s rule_fields=%s",
        product.sku,
        PROMPT_VERSION,
        rule_fields,
    )
    logger.debug("enrichment description sku=%s text=%s", product.sku, product.description)
    return profile


async def enrich_products(
    request: EnrichRequest,
    principal: ServicePrincipal,
    settings: Settings,
    llm: EnrichLlm,
) -> EnrichResponse:
    prompt = load_prompt()
    vocabs = load_vocabularies()
    concurrency = settings.jpv_rag_llm_concurrency or DEFAULT_RAG_LLM_CONCURRENCY
    semaphore = asyncio.Semaphore(concurrency)

    async def _guarded(product: EnrichProductInput) -> ProposedProfile:
        async with semaphore:
            return await enrich_one(product, llm, prompt, vocabs)

    profiles = list(await asyncio.gather(*[_guarded(product) for product in request.products]))
    return EnrichResponse(
        profiles=profiles,
        usage=Usage(model=llm.model_id),
        prompt_version=PROMPT_VERSION,
        trace_id=principal.trace_id,
    )
