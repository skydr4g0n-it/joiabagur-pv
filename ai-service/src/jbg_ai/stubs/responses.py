"""Deterministic response builders for the frozen `/v1` contracts."""

from __future__ import annotations

from datetime import UTC, datetime

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.schemas.assist import (
    AssistGroup,
    AssistGroupMember,
    AssistRequest,
    AssistResponse,
    Citation,
)
from jbg_ai.api.schemas.common import (
    PRICE_PLACEHOLDER,
    STOCK_PLACEHOLDER,
    DebugInfo,
    Usage,
)
from jbg_ai.api.schemas.enrich import (
    EnrichRequest,
    EnrichResponse,
    ProposedList,
    ProposedProfile,
    ProposedText,
)
from jbg_ai.api.schemas.enrich import (
    MAX_BATCH_SIZE as ENRICH_MAX_BATCH_SIZE,
)
from jbg_ai.api.schemas.evals import EvalMetric, EvalRun, EvalRunsResponse
from jbg_ai.api.schemas.index import (
    IndexStatusResponse,
    IndexSyncRequest,
    IndexSyncResponse,
)
from jbg_ai.api.schemas.inventory import (
    InventoryProposal,
    InventoryProposeRequest,
    InventoryProposeResponse,
)
from jbg_ai.api.schemas.retrieval import (
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
    SimilaritySignals,
    SubstituteResult,
    SubstitutesRequest,
    SubstitutesResponse,
)

OVER_RETRIEVAL_FACTOR = 3
OVER_RETRIEVAL_CAP = 60
VARIANTS_PER_FAMILY = 3

STUB_WARNING = "stub_response: deterministic fixture, no model or index was called"

_MATERIALS_CYCLE: tuple[tuple[str, ...], ...] = (
    ("plata",),
    ("oro", "circonita"),
    ("acero",),
    ("plata", "perla"),
)
_VARIANT_CYCLE: tuple[str | None, ...] = ("18 mm", "20 mm", "22 mm", None)
_SIGNAL_CYCLE: tuple[str, ...] = ("coverage_gap", "demand_up", "slow_mover", "family_incomplete")

# Enrichment fixtures. The cycles have coprime-ish lengths on purpose so a batch
# covers combinations rather than repeating one shape.
_PIECE_TYPE_CYCLE: tuple[str, ...] = ("anillo", "collar", "pendiente", "pulsera")
_STONE_TYPE_CYCLE: tuple[str | None, ...] = (None, "circonita", None, "perla", "ninguna")
_SIZE_LABEL_CYCLE: tuple[str, ...] = ("S", "M", "L")
_COLOR_TAG_CYCLE: tuple[tuple[str, ...], ...] = (("dorado",), ("plateado",), ("dorado", "blanco"))

# Straddles any plausible auto-approval threshold, so a batch exercises both the
# auto-approved and the sent-to-review branches of the consuming policy.
_TAG_CONFIDENCE_CYCLE: tuple[float, ...] = (0.92, 0.45, 0.87, 0.63)

#: Stubs run no prompt; the contract still requires the field, and a value that
#: says so is more honest than a plausible-looking version number.
STUB_PROMPT_VERSION = "stub"

# Fixed instants: a clock call would break determinism and the snapshot contract.
_LAST_FULL_SYNC_AT = datetime(2026, 8, 1, 3, 0, tzinfo=UTC)
_LAST_INCREMENTAL_SYNC_AT = datetime(2026, 8, 5, 3, 0, tzinfo=UTC)
_NEXT_CURSOR = datetime(2026, 8, 5, 3, 30, tzinfo=UTC)


def over_retrieval_count(top_k: int) -> int:
    """Candidates the retriever produces for a requested page size (design v3 §7.6)."""
    return min(top_k * OVER_RETRIEVAL_FACTOR, OVER_RETRIEVAL_CAP)


def _materials(index: int) -> list[str]:
    return list(_MATERIALS_CYCLE[index % len(_MATERIALS_CYCLE)])


def _variant_label(index: int) -> str | None:
    """Some variants are unknown on purpose so clients handle the null case."""
    return _VARIANT_CYCLE[index % len(_VARIANT_CYCLE)]


def _family_id(index: int) -> str | None:
    """Every seventh product has no family yet, mirroring an incomplete catalog."""
    if index % 7 == 0:
        return None
    return f"F-{index // VARIANTS_PER_FAMILY:03d}"


def _score(index: int) -> float:
    return round(max(0.99 - index * 0.01, 0.01), 4)


def _result(index: int, query: str) -> RetrievalResult:
    score = _score(index)
    return RetrievalResult(
        product_id=f"P-{index:04d}",
        sku=f"JBG-{index:04d}",
        score=score,
        match_reasons=[f"term_match:{query.strip()[:40]}", "material_match"],
        materials=_materials(index),
        family_id=_family_id(index),
        variant_label=_variant_label(index),
        debug=DebugInfo(
            vector_score=score,
            lexical_score=round(score * 0.8, 4),
            rerank_score=None,
            notes=["stub"],
        ),
    )


def _is_low_confidence(query: str) -> bool:
    return len(query.strip()) < 3


def retrieval_products_stub(
    request: RetrievalRequest, principal: ServicePrincipal
) -> RetrievalResponse:
    count = over_retrieval_count(request.top_k)
    results = [_result(index, request.query) for index in range(count)]
    return RetrievalResponse(
        results=results,
        candidates_returned=count,
        low_confidence=_is_low_confidence(request.query),
        trace_id=principal.trace_id,
        effective_pos_id=principal.pos_id,
    )


def retrieval_substitutes_stub(
    request: SubstitutesRequest, principal: ServicePrincipal
) -> SubstitutesResponse:
    count = over_retrieval_count(request.top_k)
    results: list[SubstituteResult] = []
    for index in range(count):
        base = _result(index, request.product_id)
        results.append(
            SubstituteResult(
                **base.model_dump(),
                similarity_signals=SimilaritySignals(
                    material_overlap=round(0.9 - index * 0.01, 4),
                    style_similarity=round(0.85 - index * 0.01, 4),
                    visual_similarity=None,
                    family_match=base.family_id is not None,
                ),
            )
        )
    return SubstitutesResponse(
        results=results,
        candidates_returned=count,
        low_confidence=False,
        trace_id=principal.trace_id,
        effective_pos_id=principal.pos_id,
    )


def _assist_group(index: int) -> AssistGroup:
    family_id = f"F-{index:03d}"
    members = [
        AssistGroupMember(
            product_id=f"P-{index:03d}-{member:02d}",
            sku=f"JBG-{index:03d}{member:02d}",
            variant_label=_variant_label(member),
            materials=_materials(index + member),
            score=_score(index * VARIANTS_PER_FAMILY + member),
        )
        for member in range(VARIANTS_PER_FAMILY)
    ]
    return AssistGroup(
        family_id=family_id,
        family_label=f"Familia {index:03d}",
        members=members,
    )


def assist_sale_stub(request: AssistRequest, principal: ServicePrincipal) -> AssistResponse:
    groups = [_assist_group(index) for index in range(request.top_k)]
    intent = "gift_search" if "regalo" in request.query.lower() else "product_search"
    pitch = (
        f"Para «{request.query.strip()}» te encajan {len(groups)} familias. "
        f"Precio {PRICE_PLACEHOLDER} y quedan {STOCK_PLACEHOLDER} unidades en tu punto de venta."
    )
    citations = [
        Citation(
            source=f"catalog:{group.family_id}",
            snippet=f"Familia {group.family_id} con {len(group.members)} variantes.",
            product_id=group.members[0].product_id,
        )
        for group in groups
    ]
    return AssistResponse(
        intent=intent,
        groups=groups,
        pitch=pitch,
        citations=citations,
        warnings=[STUB_WARNING],
        clarification_question=(
            "¿Prefieres alguna de estas familias en concreto?" if len(groups) > 1 else None
        ),
        usage=Usage(),
        trace_id=principal.trace_id,
        effective_pos_id=principal.pos_id,
    )


def inventory_propose_stub(
    request: InventoryProposeRequest, principal: ServicePrincipal
) -> InventoryProposeResponse:
    proposals = [
        InventoryProposal(
            product_id=f"P-{index:04d}",
            sku=f"JBG-{index:04d}",
            family_id=_family_id(index),
            variant_label=_variant_label(index),
            priority=index + 1,
            signal=_SIGNAL_CYCLE[index % len(_SIGNAL_CYCLE)],
            rationale=(
                f"Cobertura ajustada para los próximos {request.horizon_days} días; "
                f"quedan {STOCK_PLACEHOLDER} unidades."
            ),
            confidence=round(max(0.9 - index * 0.05, 0.1), 4),
        )
        for index in range(request.limit)
    ]
    return InventoryProposeResponse(
        proposals=proposals,
        horizon_days=request.horizon_days,
        trace_id=principal.trace_id,
        effective_pos_id=principal.pos_id,
    )


def enrich_products_stub(request: EnrichRequest, principal: ServicePrincipal) -> EnrichResponse:
    """Proposed profiles that exercise both provenances and both sides of a threshold.

    The variety is the point, not decoration. A fixture where every sensitive field
    is inferred would let a broken review policy pass its own tests: routing to
    review is what such a policy does by default, so it would never be caught
    exempting nothing. The cycles below guarantee that any batch of four products
    contains at least one `rule` field, at least one `inferred` sensitive field,
    and tags on both sides of a plausible auto-approval threshold.
    """
    profiles: list[ProposedProfile] = []
    for index, product in enumerate(request.products):
        materials = _materials(index)
        title = (product.name or f"Pieza {product.sku}").strip()

        # Every fourth piece has its size read off the SKU by a deterministic rule,
        # mirroring what the real pipeline does before calling a model at all.
        size_is_rule = index % 4 == 0
        tag_confidence = _TAG_CONFIDENCE_CYCLE[index % len(_TAG_CONFIDENCE_CYCLE)]

        profiles.append(
            ProposedProfile(
                product_id=product.product_id,
                sku=product.sku,
                title=ProposedText(value=title, confidence=0.81, source="inferred"),
                description=ProposedText(
                    value=f"{title} en {', '.join(materials)}.",
                    confidence=0.64,
                    source="inferred",
                ),
                piece_type=ProposedText(
                    value=_PIECE_TYPE_CYCLE[index % len(_PIECE_TYPE_CYCLE)],
                    confidence=0.88,
                    source="inferred",
                ),
                materials=ProposedList(value=materials, confidence=0.72, source="inferred"),
                stone_type=(
                    ProposedText(value=stone, confidence=0.61, source="inferred")
                    if (stone := _STONE_TYPE_CYCLE[index % len(_STONE_TYPE_CYCLE)]) is not None
                    else None
                ),
                size_label=(
                    ProposedText(
                        value=_SIZE_LABEL_CYCLE[index % len(_SIZE_LABEL_CYCLE)],
                        confidence=1.0 if size_is_rule else 0.57,
                        source="rule" if size_is_rule else "inferred",
                    )
                ),
                color_tags=ProposedList(
                    value=list(_COLOR_TAG_CYCLE[index % len(_COLOR_TAG_CYCLE)]),
                    confidence=tag_confidence,
                    source="inferred",
                ),
                style_tags=ProposedList(
                    value=["marino", "verano"], confidence=tag_confidence, source="inferred"
                ),
                occasion_tags=ProposedList(
                    value=["regalo"], confidence=tag_confidence, source="inferred"
                ),
                family_id=ProposedText(
                    value=f"F-{index // VARIANTS_PER_FAMILY:03d}",
                    confidence=0.55,
                    source="inferred",
                ),
                variant_label=(
                    ProposedText(value=variant, confidence=0.58, source="inferred")
                    if (variant := _variant_label(index)) is not None
                    else None
                ),
                warnings=[STUB_WARNING],
            )
        )
    return EnrichResponse(
        profiles=profiles,
        usage=Usage(),
        prompt_version=STUB_PROMPT_VERSION,
        trace_id=principal.trace_id,
    )


def index_sync_stub(request: IndexSyncRequest, principal: ServicePrincipal) -> IndexSyncResponse:
    is_full = request.full or request.since is None
    return IndexSyncResponse(
        upserted=120 if is_full else 12,
        skipped=0 if is_full else 8,
        deleted=0,
        failed=0,
        since=request.since,
        cursor=_NEXT_CURSOR,
        trace_id=principal.trace_id,
    )


def index_status_stub(principal: ServicePrincipal) -> IndexStatusResponse:
    return IndexStatusResponse(
        indexed_documents=1500,
        drift_count=3,
        last_full_sync_at=_LAST_FULL_SYNC_AT,
        last_incremental_sync_at=_LAST_INCREMENTAL_SYNC_AT,
        trace_id=principal.trace_id,
    )


def evals_runs_stub(principal: ServicePrincipal) -> EvalRunsResponse:
    return EvalRunsResponse(
        runs=[
            EvalRun(
                run_id="run-0001",
                suite="retrieval-golden-set",
                status="passed",
                started_at=datetime(2026, 8, 4, 10, 0, tzinfo=UTC),
                finished_at=datetime(2026, 8, 4, 10, 4, tzinfo=UTC),
                metrics=[
                    EvalMetric(name="recall_at_10", value=0.82),
                    EvalMetric(name="mrr", value=0.61),
                ],
            ),
            EvalRun(
                run_id="run-0002",
                suite="assist-generation",
                status="failed",
                started_at=datetime(2026, 8, 5, 10, 0, tzinfo=UTC),
                finished_at=datetime(2026, 8, 5, 10, 7, tzinfo=UTC),
                metrics=[EvalMetric(name="grounding_rate", value=0.74)],
            ),
        ],
        trace_id=principal.trace_id,
    )
