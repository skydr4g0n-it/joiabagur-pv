"""Point-of-sale scope, availability demotion, freshness and the ablation flag. C22.

Offline throughout: an injected search port and an injected embedding client. Nothing here
opens a socket and nothing reads schema `public`.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.schemas.retrieval import RetrievalMode, RetrievalRequest
from jbg_ai.retrieval.errors import InvalidPosIdError, RetrievalDependencyError
from jbg_ai.retrieval.orchestrator import retrieve_products
from jbg_ai.retrieval.projection import (
    ProjectionFreshness,
    age_seconds,
    parse_pos_id,
    resolve_scope,
)
from support.fake_embedding_client import FakeEmbeddingClient
from support.fake_product_search import (
    FakeAssignment,
    FakeIndexedRow,
    FakeProductSearch,
)
from support.settings import OTHER_POS_ID, TOKEN_POS_ID, TOKEN_TRACE_ID, build_settings

MINE = UUID(TOKEN_POS_ID)
THEIRS = UUID(OTHER_POS_ID)

A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
C = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
D = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
FAMILY = UUID("11111111-1111-1111-1111-111111111111")

DOC = "Tipo: anillo de plata. Materiales: plata."

PRINCIPAL = ServicePrincipal(
    user_id="u-1", role="Operator", trace_id=TOKEN_TRACE_ID, pos_id=TOKEN_POS_ID
)


def run(coro):
    return asyncio.run(coro)


def row(product_id: UUID, sku: str, distance: float, **kwargs) -> FakeIndexedRow:
    return FakeIndexedRow(
        product_id=product_id,
        sku=sku,
        distance=distance,
        materials=kwargs.pop("materials", ["plata"]),
        family_id=kwargs.pop("family_id", FAMILY),
        piece_type=kwargs.pop("piece_type", "anillo"),
        doc_text=kwargs.pop("doc_text", DOC),
        **kwargs,
    )


def request(**overrides) -> RetrievalRequest:
    values = {"query": "anillo de plata", "top_k": 5}
    values.update(overrides)
    return RetrievalRequest(**values)


def serve(search: FakeProductSearch, payload=None, principal=PRINCIPAL, **kwargs):
    return run(
        retrieve_products(
            payload if payload is not None else request(),
            principal,
            settings=kwargs.pop("settings", build_settings()),
            embed=kwargs.pop("embed", FakeEmbeddingClient()),
            search=search,
            freshness=kwargs.pop("freshness", ProjectionFreshness(ttl_seconds=0.0)),
            **kwargs,
        )
    )


def skus(response) -> list[str]:
    return [item.sku for item in response.results]


# --------------------------------------------------------------------------- the claim


def test_a_malformed_pos_id_is_rejected() -> None:
    with pytest.raises(InvalidPosIdError):
        parse_pos_id("POS-B")


@pytest.mark.parametrize("claim", [None, "", "   ", "POS-B", "not-a-uuid", "42"])
def test_no_claim_shape_short_of_a_uuid_is_accepted(claim: str | None) -> None:
    with pytest.raises(InvalidPosIdError):
        parse_pos_id(claim)


def test_a_malformed_claim_never_produces_an_unscoped_search() -> None:
    """The failure mode this guards is silent: a broken token answered with everything."""
    search = FakeProductSearch([row(A, "S1", 0.1)])
    broken = ServicePrincipal(
        user_id="u-1", role="Operator", trace_id=TOKEN_TRACE_ID, pos_id="POS-B"
    )

    with pytest.raises(InvalidPosIdError):
        serve(search, principal=broken)

    assert search.search_calls == [], "no branch may run before the claim is read"
    assert search.lexical_calls == []


# --------------------------------------------------------------------------- the scope


def test_candidates_come_only_from_the_assortment() -> None:
    search = FakeProductSearch(
        [row(A, "MINE-1", 0.1), row(B, "THEIRS-1", 0.05), row(C, "MINE-2", 0.2)],
        assignments=[
            FakeAssignment(MINE, A),
            FakeAssignment(MINE, C),
            FakeAssignment(THEIRS, B),
        ],
    )

    response = serve(search)

    assert sorted(skus(response)) == ["MINE-1", "MINE-2"]
    assert "THEIRS-1" not in skus(response), "a nearer product of another shop stays out"


def test_a_soft_deleted_assignment_is_out_of_scope() -> None:
    """The row survives in the projection; it just stops being a candidate."""
    search = FakeProductSearch(
        [row(A, "CARRIED", 0.2), row(B, "DROPPED", 0.1)],
        assignments=[
            FakeAssignment(MINE, A),
            FakeAssignment(MINE, B, qty_bucket="0", is_assigned_hint=False),
        ],
    )

    response = serve(search)

    assert skus(response) == ["CARRIED"]


def test_the_scope_is_applied_to_every_branch() -> None:
    search = FakeProductSearch(
        [row(A, "MINE-1", 0.1)], assignments=[FakeAssignment(MINE, A)]
    )

    serve(search)

    assert search.search_calls[0]["pos_id"] == MINE
    assert [call["pos_id"] for call in search.lexical_calls] == [MINE, MINE]


def test_the_scope_comes_from_the_token_and_never_from_the_body() -> None:
    search = FakeProductSearch(
        [row(A, "MINE-1", 0.1)], assignments=[FakeAssignment(MINE, A)]
    )

    serve(search, request(pos_id=OTHER_POS_ID))

    assert search.search_calls[0]["pos_id"] == MINE


def test_the_scoped_branch_returns_its_full_depth() -> None:
    """A small assortment must fill the window it can fill, not be truncated below it.

    The failure this pins has no error of its own: an approximate index scan asked for 60
    neighbours returns what its search list happened to hold and the filter discards the
    rest, so the branch quietly comes back short. Here the scope is established first, so
    the depth is honoured by construction.
    """
    rows = [row(UUID(int=index + 1), f"MINE-{index}", 0.1) for index in range(40)]
    search = FakeProductSearch(
        rows + [row(UUID(int=900), "THEIRS", 0.01)],
        assignments=[FakeAssignment(MINE, item.product_id) for item in rows],
    )

    serve(search, request(mode=RetrievalMode.VECTOR, top_k=50))

    assert len(search.search_calls) == 1
    assert search.search_calls[0]["depth"] == 60
    hits = run(
        search.search(
            [0.1],
            threshold=0.65,
            depth=60,
            filters=search.search_calls[0]["filters"],
            model_version_key="k",
            model_id="m",
            pos_id=MINE,
        )
    )
    assert len(hits) == 40, "every assigned candidate within the depth is returned"


# --------------------------------------------------------------------------- demotion


def test_out_of_stock_product_is_penalised_not_removed() -> None:
    search = FakeProductSearch(
        [row(A, "EMPTY", 0.10), row(B, "STOCKED", 0.11)],
        assignments=[
            FakeAssignment(MINE, A, qty_bucket="0"),
            FakeAssignment(MINE, B, qty_bucket="3+"),
        ],
    )

    response = serve(search)

    assert set(skus(response)) == {"EMPTY", "STOCKED"}, "demoted, never removed"
    assert skus(response).index("STOCKED") < skus(response).index("EMPTY")


def test_a_typed_constraint_outranks_the_stock_signal() -> None:
    """What the operator typed beats a signal they did not ask about."""
    search = FakeProductSearch(
        [
            row(A, "CHEAP-EMPTY", 0.20, price=40.0),
            row(B, "DEAR-STOCKED", 0.10, price=900.0),
        ],
        assignments=[
            FakeAssignment(MINE, A, qty_bucket="0"),
            FakeAssignment(MINE, B, qty_bucket="3+"),
        ],
    )

    response = serve(search, request(query="anillo de plata por menos de 80 euros"))

    assert skus(response)[0] == "CHEAP-EMPTY", "the ceiling block outranks availability"


def test_the_two_non_zero_buckets_are_not_ordered_against_each_other() -> None:
    search = FakeProductSearch(
        [row(A, "FEW", 0.10), row(B, "MANY", 0.11)],
        assignments=[
            FakeAssignment(MINE, A, qty_bucket="1-2"),
            FakeAssignment(MINE, B, qty_bucket="3+"),
        ],
    )

    response = serve(search)

    assert skus(response) == ["FEW", "MANY"], "the fused order survives untouched"


def test_no_bucket_reaches_the_response() -> None:
    search = FakeProductSearch(
        [row(A, "EMPTY", 0.1)], assignments=[FakeAssignment(MINE, A, qty_bucket="0")]
    )

    payload = serve(search).model_dump()

    assert "qty_bucket" not in str(payload)
    assert "3+" not in str(payload)


# --------------------------------------------------------------------------- freshness


def test_freshness_reflects_the_last_synchronisation_not_the_last_change() -> None:
    """The trap: the feed is incremental, so the rows are old by design."""
    search = FakeProductSearch(
        [row(A, "S1", 0.1)],
        assignments=[FakeAssignment(MINE, A)],
        synced_at=datetime.now(tz=UTC) - timedelta(seconds=30),
    )

    response = serve(search)

    assert response.projection_age_seconds is not None
    assert 20 < response.projection_age_seconds < 120
    assert search.synced_at_calls == 1, "one checkpoint read, not one per branch"


def test_the_age_is_read_through_a_cache() -> None:
    search = FakeProductSearch(
        [row(A, "S1", 0.1)], assignments=[FakeAssignment(MINE, A)]
    )
    shared = ProjectionFreshness(ttl_seconds=60.0, clock=lambda: 0.0)

    serve(search, freshness=shared)
    serve(search, freshness=shared)

    assert search.synced_at_calls == 1, "the pool is capped at five; do not spend it twice"


def test_the_age_is_absent_when_the_prefilter_did_not_run() -> None:
    search = FakeProductSearch(
        [row(A, "S1", 0.1)], assignments=[FakeAssignment(MINE, A)]
    )

    response = serve(search, pos_prefilter=False)

    assert response.projection_age_seconds is None


def test_a_never_synchronised_checkpoint_has_no_age() -> None:
    assert age_seconds(None) is None


def test_a_naive_timestamp_is_read_as_utc() -> None:
    """PostgreSQL hands back an aware value; a driver or a fake may not."""
    naive = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(seconds=10)

    computed = age_seconds(naive)

    assert computed is not None and 5 < computed < 60


# --------------------------------------------------------------------------- guards


def test_an_unsynchronised_projection_is_503_and_not_an_abstention() -> None:
    """A 200 with an empty list is indistinguishable from a legitimate abstention."""
    search = FakeProductSearch([row(A, "S1", 0.1)], assignments=[])

    with pytest.raises(RetrievalDependencyError, match="projection"):
        serve(search)


def test_the_empty_guard_names_the_projection_as_the_cause() -> None:
    search = FakeProductSearch([row(A, "S1", 0.1)], assignments=[])

    with pytest.raises(RetrievalDependencyError) as caught:
        serve(search)

    assert "projection" in str(caught.value)
    assert "refusing to abstain" in str(caught.value)


def test_a_point_of_sale_carrying_nothing_is_not_confused_with_a_query_that_matched_nothing() -> None:
    empty_scope = FakeProductSearch([row(A, "S1", 0.1)], assignments=[])
    matched_nothing = FakeProductSearch(
        [row(A, "S1", 0.9, doc_text="Tipo: broche.")],
        assignments=[FakeAssignment(MINE, A)],
    )

    with pytest.raises(RetrievalDependencyError):
        serve(empty_scope)

    response = serve(matched_nothing, request(mode=RetrievalMode.VECTOR))
    assert response.results == [], "an honest abstention is still a 200"
    assert response.low_confidence is True


def test_a_stale_projection_stops_filtering_instead_of_hiding_products() -> None:
    search = FakeProductSearch(
        [row(A, "MINE", 0.2), row(B, "THEIRS", 0.1)],
        assignments=[FakeAssignment(MINE, A), FakeAssignment(THEIRS, B)],
        synced_at=datetime.now(tz=UTC) - timedelta(hours=5),
    )

    response = serve(search)

    assert search.search_calls[0]["pos_id"] is None, "the scope is dropped, not narrowed"
    assert set(skus(response)) == {"MINE", "THEIRS"}
    assert response.projection_age_seconds is not None
    assert response.projection_age_seconds > 3600


def test_a_stale_projection_logs_the_degradation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    search = FakeProductSearch(
        [row(A, "MINE", 0.2)],
        assignments=[FakeAssignment(MINE, A)],
        synced_at=datetime.now(tz=UTC) - timedelta(hours=5),
    )

    with caplog.at_level(logging.WARNING, logger="jbg_ai.retrieval.orchestrator"):
        serve(search)

    degraded = [r for r in caplog.records if "degraded=unscoped" in r.getMessage()]
    assert degraded, "a silent degradation is the failure this change exists to avoid"
    assert TOKEN_TRACE_ID in degraded[0].getMessage()


def test_a_projection_that_was_never_synchronised_degrades_rather_than_scoping() -> None:
    search = FakeProductSearch(
        [row(A, "MINE", 0.2), row(B, "THEIRS", 0.1)],
        assignments=[FakeAssignment(MINE, A), FakeAssignment(THEIRS, B)],
        never_synchronised=True,
    )

    response = serve(search)

    assert search.search_calls[0]["pos_id"] is None
    assert response.projection_age_seconds is None


def test_a_fresh_projection_applies_the_filter() -> None:
    search = FakeProductSearch(
        [row(A, "MINE", 0.2), row(B, "THEIRS", 0.1)],
        assignments=[FakeAssignment(MINE, A), FakeAssignment(THEIRS, B)],
        synced_at=datetime.now(tz=UTC) - timedelta(seconds=5),
    )

    response = serve(search)

    assert search.search_calls[0]["pos_id"] == MINE
    assert skus(response) == ["MINE"]


def test_the_ceiling_is_configurable_per_call() -> None:
    search = FakeProductSearch(
        [row(A, "MINE", 0.2), row(B, "THEIRS", 0.1)],
        assignments=[FakeAssignment(MINE, A), FakeAssignment(THEIRS, B)],
        synced_at=datetime.now(tz=UTC) - timedelta(seconds=120),
    )

    serve(search, projection_max_age_seconds=60)
    assert search.search_calls[0]["pos_id"] is None

    serve(search, projection_max_age_seconds=3600)
    assert search.search_calls[1]["pos_id"] == MINE


# --------------------------------------------------------------------------- the flag


def test_disabling_the_prefilter_restores_the_previous_behaviour() -> None:
    search = FakeProductSearch(
        [row(A, "MINE", 0.2), row(B, "THEIRS", 0.1)],
        assignments=[FakeAssignment(MINE, A), FakeAssignment(THEIRS, B)],
    )

    response = serve(search, pos_prefilter=False)

    assert search.search_calls[0]["pos_id"] is None
    assert [call["pos_id"] for call in search.lexical_calls] == [None, None]
    assert set(skus(response)) == {"MINE", "THEIRS"}
    assert search.scope_calls == [], "a disabled prefilter must not even count the scope"


def test_a_sweep_overrides_the_default_without_restarting() -> None:
    settings = build_settings()
    search = FakeProductSearch(
        [row(A, "MINE", 0.2), row(B, "THEIRS", 0.1)],
        assignments=[FakeAssignment(MINE, A), FakeAssignment(THEIRS, B)],
    )

    scoped = serve(search, settings=settings, pos_prefilter=True)
    unscoped = serve(search, settings=settings, pos_prefilter=False)

    assert skus(scoped) == ["MINE"]
    assert set(skus(unscoped)) == {"MINE", "THEIRS"}
    assert settings.jpv_pos_prefilter_enabled is True, "the default was not mutated"


def test_the_flag_is_not_part_of_the_request_contract() -> None:
    fields = set(RetrievalRequest.model_fields)

    assert "pos_prefilter" not in fields
    assert "projection_max_age_seconds" not in fields
    assert fields == {"query", "top_k", "filters", "mode", "pos_id"}


# --------------------------------------------------------------------------- logging


def test_the_projection_stage_reports_what_the_scope_admitted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    search = FakeProductSearch(
        [row(A, "MINE", 0.2), row(C, "MINE-2", 0.3)],
        assignments=[FakeAssignment(MINE, A), FakeAssignment(MINE, C)],
    )

    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
        serve(search)

    entries = [r.getMessage() for r in caplog.records if "stage=projection" in r.getMessage()]
    assert entries
    assert TOKEN_TRACE_ID in entries[0]
    assert "scope_size=2" in entries[0]
    assert "applied=True" in entries[0]
    assert "age_seconds=" in entries[0]


def test_the_search_stage_reports_the_scoped_cardinality(
    caplog: pytest.LogCaptureFixture,
) -> None:
    search = FakeProductSearch(
        [row(A, "MINE", 0.2)], assignments=[FakeAssignment(MINE, A)]
    )

    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
        serve(search, request(mode=RetrievalMode.VECTOR))

    entries = [r.getMessage() for r in caplog.records if "stage=search" in r.getMessage()]
    assert entries
    assert "scoped=True" in entries[0]
    assert "candidates=1" in entries[0]
    assert "truncated=True" in entries[0], "a branch below its depth must be visible"


def test_no_vector_reaches_the_logs(caplog: pytest.LogCaptureFixture) -> None:
    search = FakeProductSearch(
        [row(A, "MINE", 0.2)], assignments=[FakeAssignment(MINE, A)]
    )

    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
        serve(search)

    for record in caplog.records:
        message = record.getMessage()
        assert "[0." not in message
        assert "embedding=[" not in message


# ------------------------------------------------------------------- sales, unread


def test_the_retrieval_path_cannot_read_the_sales_figures() -> None:
    """Written by the drain, read by nothing here. Structural, not a promise.

    `sales_30d`, `sales_90d` and `last_sale_at` are persisted so the business-signals
    ranking that follows has an input, and this capability must not quietly start using
    them — a weight that appeared here would be uncalibrated by definition, because the
    golden set that could calibrate it does not exist yet. The cheapest guarantee is that
    the values never reach the pipeline at all: no hit type carries them, so no ordering
    rule can read one by accident.
    """
    import inspect

    from jbg_ai.retrieval import filters, fusion, orchestrator
    from jbg_ai.retrieval.ports import LexicalHit, SearchHit

    for hit_type in (SearchHit, LexicalHit):
        fields = set(hit_type.__dataclass_fields__)
        assert not any(name.startswith("sales_") for name in fields), hit_type
        assert "last_sale_at" not in fields

    for module in (orchestrator, filters, fusion):
        source = inspect.getsource(module)
        assert "sales_30d" not in source, module.__name__
        assert "sales_90d" not in source, module.__name__
        assert "last_sale_at" not in source, module.__name__


def test_sales_figures_do_not_change_the_order() -> None:
    """Two candidates the fusion ranks equally stay in fused order whatever they sold."""
    search = FakeProductSearch(
        [row(A, "SOLD-A-LOT", 0.10), row(B, "SOLD-NOTHING", 0.11)],
        assignments=[
            FakeAssignment(MINE, A, qty_bucket="3+"),
            FakeAssignment(MINE, B, qty_bucket="3+"),
        ],
    )

    response = serve(search)

    assert skus(response) == ["SOLD-A-LOT", "SOLD-NOTHING"], "distance decides, not rotation"


# --------------------------------------------------------------------------- unit


def test_resolve_scope_skips_every_query_when_disabled() -> None:
    search = FakeProductSearch([row(A, "S1", 0.1)], assignments=[])

    scope = run(
        resolve_scope(
            MINE,
            search=search,
            enabled=False,
            max_age_seconds=3600,
            freshness=ProjectionFreshness(ttl_seconds=0.0),
        )
    )

    assert scope.pos_id is None
    assert scope.applied is False
    assert scope.reported_age is None
    assert search.scope_calls == []
    assert search.synced_at_calls == 0
