"""Fused retrieval: honest modes, real provenance, demoting filters. C14 + C21."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import pytest

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.schemas.retrieval import RetrievalFilters, RetrievalMode, RetrievalRequest
from jbg_ai.indexing.errors import EmbeddingError
from jbg_ai.retrieval.errors import InvalidFamilyIdError, RetrievalDependencyError
from jbg_ai.retrieval.orchestrator import (
    build_retrieval_embed_client,
    parse_body_filters,
    retrieve_products,
)
from support.fake_embedding_client import FakeEmbeddingClient
from support.fake_product_search import FakeIndexedRow, FakeProductSearch
from support.settings import TOKEN_POS_ID, TOKEN_TRACE_ID, build_settings

A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
C = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
FAMILY = UUID("11111111-1111-1111-1111-111111111111")
OTHER_FAMILY = UUID("22222222-2222-2222-2222-222222222222")

DOC = "Tipo: anillo de plata. Materiales: plata."

PRINCIPAL = ServicePrincipal(
    user_id="u-1",
    role="Operator",
    trace_id=TOKEN_TRACE_ID,
    pos_id=TOKEN_POS_ID,
)


def _run(coro):
    return asyncio.run(coro)


def _request(**overrides) -> RetrievalRequest:
    values = {"query": "anillo de plata", "top_k": 5}
    values.update(overrides)
    return RetrievalRequest(**values)


def _row(product_id: UUID, sku: str, distance: float, **kwargs) -> FakeIndexedRow:
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


def _blind_row(product_id: UUID, sku: str, distance: float, **kwargs) -> FakeIndexedRow:
    """A row no lexical query can reach, so the vector branch is the only one that sees it."""
    return _row(product_id, sku, distance, doc_text="Tipo: broche. Materiales: laton.", **kwargs)


def _serve(search: FakeProductSearch, payload=None, **kwargs):
    return _run(
        retrieve_products(
            payload if payload is not None else _request(),
            PRINCIPAL,
            settings=kwargs.pop("settings", build_settings()),
            embed=kwargs.pop("embed", FakeEmbeddingClient()),
            search=search,
            **kwargs,
        )
    )


# --------------------------------------------------------------------------------------
# Abstention, over-retrieval and branch depth
# --------------------------------------------------------------------------------------


def test_returns_empty_with_low_confidence_when_no_branch_produces_anything() -> None:
    search = FakeProductSearch([_blind_row(A, "S1", 0.9), _blind_row(B, "S2", 0.8)])
    response = _serve(search)

    assert response.results == []
    assert response.candidates_returned == 0
    assert response.low_confidence is True
    assert response.effective_pos_id == TOKEN_POS_ID
    assert search.search_calls[0]["threshold"] == 0.65


def test_returns_overfetched_candidate_count() -> None:
    rows = [_row(UUID(int=index), f"S{index}", 0.1 + index * 0.001) for index in range(20)]
    response = _serve(FakeProductSearch(rows), _request(top_k=5))

    assert len(response.results) == 15
    assert response.candidates_returned == 15
    assert response.low_confidence is False


def test_branch_depth_does_not_follow_the_requested_page_size() -> None:
    rows = [_row(UUID(int=index), f"S{index}", 0.1 + index * 0.001) for index in range(20)]

    small = FakeProductSearch(rows)
    large = FakeProductSearch(rows)
    _serve(small, _request(top_k=5))
    _serve(large, _request(top_k=20))

    assert small.search_calls[0]["depth"] == 60
    assert large.search_calls[0]["depth"] == 60
    assert {call["depth"] for call in small.lexical_calls} == {60}
    assert {call["depth"] for call in large.lexical_calls} == {60}


def test_branch_depth_is_a_call_parameter() -> None:
    rows = [_row(UUID(int=index), f"S{index}", 0.1 + index * 0.001) for index in range(20)]
    search = FakeProductSearch(rows)
    response = _serve(search, _request(top_k=5), branch_depth=3)

    assert search.search_calls[0]["depth"] == 3
    assert {call["depth"] for call in search.lexical_calls} == {3}
    # Three lists of three can name at most nine distinct products, well under the
    # over-retrieval window of 15 the page size asked for.
    assert 0 < len(response.results) <= 9


def test_overfetch_does_not_refill_from_rows_above_threshold() -> None:
    rows = [
        _row(A, "S1", 0.2),
        _row(B, "S2", 0.3),
        *[_blind_row(UUID(int=index + 10), f"X{index}", 0.9) for index in range(20)],
    ]
    response = _serve(FakeProductSearch(rows), _request(top_k=5, mode=RetrievalMode.VECTOR))

    assert len(response.results) == 2
    assert response.candidates_returned == 2


def test_empty_compatible_index_raises_dependency_error() -> None:
    search = FakeProductSearch(compatible_count=0)
    with pytest.raises(RetrievalDependencyError, match="compatible"):
        _serve(search)
    assert search.search_calls == []


# --------------------------------------------------------------------------------------
# Score, provenance and diagnostics
# --------------------------------------------------------------------------------------


def test_score_is_the_fused_rank_score_normalised_to_the_first_result() -> None:
    search = FakeProductSearch(
        [_row(A, "far", 0.4), _row(B, "near", 0.1), _row(C, "mid", 0.2)]
    )
    response = _serve(search)

    scores = [item.score for item in response.results]
    assert scores[0] == 1.0
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= score <= 1.0 for score in scores)


def test_match_reasons_report_real_provenance() -> None:
    search = FakeProductSearch(
        [
            _row(A, "both", 0.1),
            _blind_row(B, "vector-only", 0.2),
            _row(C, "lexical-only", 0.9),
        ]
    )
    response = _serve(search)
    by_sku = {item.sku: item for item in response.results}

    assert sorted(by_sku["both"].match_reasons) == ["lexical", "vector"]
    assert by_sku["vector-only"].match_reasons == ["vector"]
    assert by_sku["lexical-only"].match_reasons == ["lexical"]
    assert len({tuple(item.match_reasons) for item in response.results}) > 1


def test_an_absent_diagnostic_is_none_never_fabricated() -> None:
    search = FakeProductSearch([_row(A, "both", 0.1), _row(C, "lexical-only", 0.9)])
    response = _serve(search)
    by_sku = {item.sku: item for item in response.results}

    lexical_only = by_sku["lexical-only"]
    assert lexical_only.debug is not None
    assert lexical_only.debug.lexical_score is not None
    assert lexical_only.debug.vector_score is None

    both = by_sku["both"]
    assert both.debug is not None
    assert both.debug.vector_score == pytest.approx(0.9)
    assert both.debug.lexical_score is not None
    assert both.debug.rerank_score is None


def test_vector_only_until_c21_no_longer_appears_in_any_response() -> None:
    search = FakeProductSearch([_row(A, "S1", 0.2)])
    for mode in (RetrievalMode.HYBRID, RetrievalMode.LEXICAL, RetrievalMode.VECTOR, None):
        kwargs = {} if mode is None else {"mode": mode}
        response = _serve(FakeProductSearch(search.rows), _request(**kwargs))
        for item in response.results:
            assert item.debug is not None
            assert "vector_only_until_c21" not in item.debug.notes


# --------------------------------------------------------------------------------------
# Honest modes and honest degradation
# --------------------------------------------------------------------------------------


def test_lexical_mode_makes_no_provider_call() -> None:
    embed = FakeEmbeddingClient()
    search = FakeProductSearch([_row(A, "S1", 0.9)])
    response = _serve(search, _request(mode=RetrievalMode.LEXICAL), embed=embed)

    assert embed.provider_calls == []
    assert search.search_calls == []
    assert search.count_calls == []
    assert [item.sku for item in response.results] == ["S1"]
    assert response.results[0].match_reasons == ["lexical"]


def test_vector_mode_does_not_query_tsv() -> None:
    search = FakeProductSearch([_row(A, "S1", 0.2)])
    response = _serve(search, _request(mode=RetrievalMode.VECTOR))

    assert search.lexical_calls == []
    assert response.results[0].match_reasons == ["vector"]


def test_hybrid_mode_fuses_all_three_lists() -> None:
    search = FakeProductSearch([_row(A, "S1", 0.2)])
    _serve(search, _request(mode=RetrievalMode.HYBRID))

    assert len(search.lexical_calls) == 2
    assert [call["request"].name for call in search.lexical_calls] == ["typed", "expanded"]
    assert len(search.search_calls) == 1


def test_embedding_failure_in_hybrid_degrades_to_lexical() -> None:
    class _Boom(FakeEmbeddingClient):
        async def embed(self, texts: list[str]):
            raise EmbeddingError("provider down")

    search = FakeProductSearch([_row(A, "S1", 0.1)])
    response = _serve(search, embed=_Boom())

    assert response.results
    assert all("vector" not in item.match_reasons for item in response.results)
    assert response.results[0].match_reasons == ["lexical"]


def test_embedding_failure_with_no_lexical_hits_is_503() -> None:
    class _Boom(FakeEmbeddingClient):
        async def embed(self, texts: list[str]):
            raise EmbeddingError("provider down")

    search = FakeProductSearch([_blind_row(A, "S1", 0.1)])
    with pytest.raises(RetrievalDependencyError, match="provider down"):
        _serve(search, embed=_Boom())


def test_embedding_failure_in_vector_mode_is_503_even_with_lexical_rows() -> None:
    class _Boom(FakeEmbeddingClient):
        async def embed(self, texts: list[str]):
            raise EmbeddingError("provider down")

    search = FakeProductSearch([_row(A, "S1", 0.1)])
    with pytest.raises(RetrievalDependencyError, match="provider down"):
        _serve(search, _request(mode=RetrievalMode.VECTOR), embed=_Boom())


def test_low_confidence_signals_absence_of_cross_branch_consensus() -> None:
    """The measured failure: the vector says *pulsera*, the lexical says *sortija*, 0/10 overlap."""
    agreeing = FakeProductSearch([_row(A, "both", 0.1)])
    disagreeing = FakeProductSearch(
        [_blind_row(B, "vector-only", 0.1), _row(C, "lexical-only", 0.9)]
    )

    assert _serve(agreeing).low_confidence is False

    response = _serve(disagreeing)
    assert response.low_confidence is True
    assert len(response.results) == 2, "a signal must not suppress results"
    assert [item.sku for item in response.results] == [
        item.sku for item in _serve(FakeProductSearch(disagreeing.rows)).results
    ]


# --------------------------------------------------------------------------------------
# Concurrency, body filters and structural filters
# --------------------------------------------------------------------------------------


def test_lexical_query_runs_concurrently_with_embedding() -> None:
    """It races the provider, not the vector search: one pool connection at any moment."""
    lexical_started = asyncio.Event()

    class _WaitingEmbed(FakeEmbeddingClient):
        async def embed(self, texts: list[str]):
            await asyncio.wait_for(lexical_started.wait(), timeout=2)
            return await super().embed(texts)

    class _SignallingSearch(FakeProductSearch):
        async def search_lexical(self, request, *, depth, filters):
            lexical_started.set()
            return await super().search_lexical(request, depth=depth, filters=filters)

    search = _SignallingSearch([_row(A, "S1", 0.1)])
    response = _run(
        asyncio.wait_for(
            retrieve_products(
                _request(),
                PRINCIPAL,
                settings=build_settings(),
                embed=_WaitingEmbed(),
                search=search,
            ),
            timeout=5,
        )
    )

    assert response.results


def test_body_filters_materials_category_family_and_exclusions() -> None:
    excluded = UUID("99999999-9999-9999-9999-999999999999")
    search = FakeProductSearch(
        [
            _row(A, "keep", 0.1),
            _row(B, "mat", 0.1, materials=["oro"]),
            _row(C, "cat", 0.1, piece_type="collar"),
            _row(UUID("33333333-3333-3333-3333-333333333333"), "fam", 0.1, family_id=OTHER_FAMILY),
            _row(excluded, "ex", 0.1),
        ]
    )
    payload = _request(
        filters=RetrievalFilters(
            materials=["plata"],
            category="anillo",
            family_id=str(FAMILY),
            exclude_product_ids=[str(excluded), "not-a-uuid"],
        )
    )
    response = _serve(search, payload)

    assert [item.sku for item in response.results] == ["keep"]
    assert str(excluded) not in [item.product_id for item in response.results]


def test_invalid_family_id_raises_before_search() -> None:
    search = FakeProductSearch([_row(A, "S1", 0.1)])
    payload = _request(filters=RetrievalFilters(family_id="not-a-uuid"))
    with pytest.raises(InvalidFamilyIdError):
        _serve(search, payload)
    assert search.count_calls == []
    assert search.search_calls == []
    assert search.lexical_calls == []


def test_malformed_exclusions_are_ignored(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="jbg_ai.retrieval.orchestrator"):
        parsed = parse_body_filters(
            RetrievalFilters(exclude_product_ids=[str(A), "nope", "also-bad"])
        )

    assert parsed.exclude_product_ids == [A]
    messages = [record.getMessage() for record in caplog.records]
    debug_msgs = [msg for msg in messages if "exclude_product_id" in msg]
    assert debug_msgs
    assert any("nope" in msg for msg in debug_msgs)
    assert any("also-bad" in msg for msg in debug_msgs)
    assert not any(str(A) in msg for msg in debug_msgs)


def test_structural_filter_demotes_but_never_removes() -> None:
    search = FakeProductSearch(
        [
            _row(A, "expensive", 0.1, price=200.0),
            _row(B, "cheap", 0.5, price=50.0),
            _row(C, "unpriced", 0.6, price=None),
        ]
    )
    response = _serve(search, _request(query="anillo de plata menos de 80"))

    skus = [item.sku for item in response.results]
    assert set(skus) == {"expensive", "cheap", "unpriced"}, "nothing is removed"
    assert skus[-1] == "expensive"
    assert skus.index("cheap") < skus.index("expensive")


def test_extracted_constraints_are_reported_in_debug_notes() -> None:
    search = FakeProductSearch([_row(A, "S1", 0.1, price=50.0)])
    response = _serve(search, _request(query="anillo de plata menos de 80"))

    notes = response.results[0].debug.notes  # type: ignore[union-attr]
    assert any("price_ceiling=80" in note for note in notes)


def test_no_filter_is_invented_when_the_query_expresses_none() -> None:
    """`anillo` resolves to a piece type, which is never filtered and never demotes."""
    search = FakeProductSearch([_row(A, "S1", 0.1, price=500.0)])
    response = _serve(search, _request(query="anillo"))

    assert response.results[0].debug is not None
    assert response.results[0].debug.notes == []


# --------------------------------------------------------------------------------------
# Configuration and observability
# --------------------------------------------------------------------------------------


def test_retrieval_embed_client_uses_max_attempts_one_and_a_bounded_cache() -> None:
    from jbg_ai.indexing.constants import MAX_EMBED_ATTEMPTS
    from jbg_ai.retrieval.cache import BoundedEmbeddingCache

    client = build_retrieval_embed_client(build_settings(jpv_embedding_api_key="sk-test"))

    assert client.max_attempts == 1
    assert MAX_EMBED_ATTEMPTS == 3
    assert isinstance(client.cache, BoundedEmbeddingCache)


def test_two_weight_configurations_run_in_one_process() -> None:
    """C24 sweeps in-process: an environment-only knob would force a restart per config."""
    settings = build_settings()
    rows = [_row(A, "both", 0.1), _blind_row(B, "vector-only", 0.05)]

    lexical_heavy = _serve(FakeProductSearch(rows), settings=settings, weight_vector=0.0)
    vector_heavy = _serve(
        FakeProductSearch(rows),
        settings=settings,
        weight_typed=0.0,
        weight_expanded=0.0,
    )

    assert settings.jpv_rrf_weight_vector == 0.33, "the settings object is not mutated"
    assert lexical_heavy.results[0].sku == "both"
    assert vector_heavy.results[0].sku == "vector-only"


def test_expansion_flag_sweeps_two_configurations_in_one_process(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = build_settings(jpv_query_expansion_enabled=True)
    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
        for enabled in (True, False):
            _serve(
                FakeProductSearch([_row(A, "S1", 0.1)]),
                _request(query="sortija de plata"),
                settings=settings,
                expand_synonyms=enabled,
            )

    assert settings.jpv_query_expansion_enabled is True
    expand_logs = [msg for msg in (r.getMessage() for r in caplog.records) if "stage=expand" in msg]
    assert any("enabled=True" in msg for msg in expand_logs)
    assert any("enabled=False" in msg for msg in expand_logs)


def test_the_expansion_stage_no_longer_reports_itself_unconsumed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
        _serve(FakeProductSearch([_row(A, "S1", 0.1)]), _request(query="sortija de plata"))

    expand_logs = [msg for msg in (r.getMessage() for r in caplog.records) if "stage=expand" in msg]
    assert expand_logs
    assert all(TOKEN_TRACE_ID in msg for msg in expand_logs)
    assert "consumed=True" in expand_logs[0], "C21 is the consumer the log was waiting for"
    assert "matched_terms=" in expand_logs[0]


def test_the_new_stages_are_traceable(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
        _serve(FakeProductSearch([_row(A, "S1", 0.2)]))

    messages = [record.getMessage() for record in caplog.records]
    for stage in ("expand", "embed", "search", "lexical", "filters", "fuse"):
        entries = [msg for msg in messages if f"stage={stage} " in msg]
        assert entries, stage
        assert all(TOKEN_TRACE_ID in msg for msg in entries), stage
    assert all(getattr(record, "trace_id", None) == TOKEN_TRACE_ID for record in caplog.records)

    lexical = next(msg for msg in messages if "stage=lexical " in msg)
    assert "latency_ms=" in lexical and "typed=" in lexical and "expanded=" in lexical

    filters_entry = next(msg for msg in messages if "stage=filters " in msg)
    assert "extracted=" in filters_entry and "demoted=" in filters_entry

    fuse_entry = next(msg for msg in messages if "stage=fuse " in msg)
    assert "typed=" in fuse_entry and "expanded=" in fuse_entry and "vector=" in fuse_entry
    assert "cross_branch=" in fuse_entry and "low_confidence=" in fuse_entry


def test_the_operator_query_is_not_logged_at_information(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
        _serve(FakeProductSearch([_row(A, "S1", 0.2)]), _request(query="anillo de plata"))

    for record in caplog.records:
        if record.levelno >= logging.INFO:
            assert "anillo de plata" not in record.getMessage()


def test_vector_branch_embeds_the_original_text() -> None:
    """The expansion feeds the lexical branch only; the vector query is never rewritten."""
    embed = FakeEmbeddingClient()
    _serve(
        FakeProductSearch([_row(A, "S1", 0.1)]),
        _request(query="sortija de plata"),
        embed=embed,
    )

    assert embed.provider_calls == [["sortija de plata"]]


# --------------------------------------------------------------------------------------
# low_confidence only carries the consensus signal where there were branches to disagree
# --------------------------------------------------------------------------------------


def test_single_branch_modes_do_not_report_permanent_low_confidence() -> None:
    """With one branch no candidate can ever appear twice, so the consensus rule would be
    a constant `true` — a field carrying no information, which is the shape of lie this
    change removed from `match_reasons`."""
    for mode in (RetrievalMode.LEXICAL, RetrievalMode.VECTOR):
        response = _serve(FakeProductSearch([_row(A, "S1", 0.2)]), _request(mode=mode))

        assert response.results, mode
        assert len({tuple(item.match_reasons) for item in response.results}) == 1
        assert response.low_confidence is False, mode


def test_single_branch_modes_keep_the_c14_meaning_when_nothing_matches() -> None:
    for mode, rows in (
        (RetrievalMode.LEXICAL, [_blind_row(A, "S1", 0.1)]),
        (RetrievalMode.VECTOR, [_row(A, "S1", 0.9)]),
    ):
        response = _serve(FakeProductSearch(rows), _request(mode=mode))

        assert response.results == [], mode
        assert response.low_confidence is True, mode


def test_a_degraded_hybrid_response_is_not_marked_low_confidence() -> None:
    """The provider failed, so only the lexical branch ran: there was no second opinion to
    disagree with, and saying "the branches disagree" would invent one."""

    class _Boom(FakeEmbeddingClient):
        async def embed(self, texts: list[str]):
            raise EmbeddingError("provider down")

    response = _serve(FakeProductSearch([_row(A, "S1", 0.1)]), embed=_Boom())

    assert response.results
    assert response.results[0].match_reasons == ["lexical"]
    assert response.low_confidence is False


def test_hybrid_still_reports_total_branch_disagreement() -> None:
    response = _serve(
        FakeProductSearch([_blind_row(B, "vector-only", 0.1), _row(C, "lexical-only", 0.9)])
    )

    assert response.low_confidence is True
    assert len(response.results) == 2


def test_the_fuse_log_names_the_branches_that_actually_ran(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cases = {
        RetrievalMode.HYBRID: "branches=lexical+vector",
        RetrievalMode.LEXICAL: "branches=lexical",
        RetrievalMode.VECTOR: "branches=vector",
    }
    for mode, expected in cases.items():
        caplog.clear()
        with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
            _serve(FakeProductSearch([_row(A, "S1", 0.2)]), _request(mode=mode))

        entry = next(
            msg for msg in (r.getMessage() for r in caplog.records) if "stage=fuse " in msg
        )
        assert expected in entry, mode
