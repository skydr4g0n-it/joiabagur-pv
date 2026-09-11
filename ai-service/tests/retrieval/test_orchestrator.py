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
        async def search_lexical(self, request, *, depth, filters, pos_id=None):
            lexical_started.set()
            return await super().search_lexical(
                request, depth=depth, filters=filters, pos_id=pos_id
            )

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
    """C24 sweeps in-process: an environment-only knob would force a restart per config.

    The knobs swept are the per-BRANCH weights, which are the effective ones under the live
    two-stage fusion. C21's three flat weights remain reachable through `fusion="flat"`, and
    `test_flat_fusion_mode_reproduces_the_published_baseline` is what exercises them.
    """
    settings = build_settings()
    rows = [_row(A, "both", 0.1), _blind_row(B, "vector-only", 0.05)]

    lexical_heavy = _serve(
        FakeProductSearch(rows), settings=settings, branch_weight_vector=0.0
    )
    vector_heavy = _serve(
        FakeProductSearch(rows), settings=settings, branch_weight_lexical=0.0
    )

    assert settings.jpv_branch_weight_lexical == 0.5, "the settings object is not mutated"
    assert settings.jpv_branch_weight_vector == 0.5, "the settings object is not mutated"
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


# --------------------------------------------------------------------------------------
# Guards closed after the verify pass
# --------------------------------------------------------------------------------------


def test_the_expansion_finds_what_the_typed_form_alone_would_miss() -> None:
    """The second half of *The groups reach the lexical query*, which was unpinned.

    The document says `anillo`; the operator says `sortija`. The typed list cannot reach it —
    that is the whole reason C20 exists — and the expanded one can, because `sortija` and
    `anillo` are the same equivalence class.
    """
    only_canonical = _row(
        A, "canonical-only", 0.9, doc_text="Tipo: anillo. Materiales: plata."
    )
    search = FakeProductSearch([only_canonical])
    payload = _request(query="sortija")

    response = _serve(search, payload)

    typed_call, expanded_call = search.lexical_calls
    assert typed_call["request"].name == "typed"
    assert expanded_call["request"].name == "expanded"
    assert "anillo" in [form for group in expanded_call["request"].groups for form in group]

    # The candidate exists only because the expanded list reached it.
    assert [item.sku for item in response.results] == ["canonical-only"]
    assert response.results[0].match_reasons == ["lexical"]

    without_expansion = _serve(
        FakeProductSearch([only_canonical]), payload, expand_synonyms=False
    )
    assert without_expansion.results == [], "the typed form alone matches nothing"


def test_embedding_vectors_are_never_logged_at_information(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A 1536-float vector in a log line is a leak and a bill. Pinned, not assumed."""
    embed = FakeEmbeddingClient()
    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
        _serve(FakeProductSearch([_row(A, "S1", 0.2)]), embed=embed)

    vector = _run(embed.embed(["anillo de plata"])).vectors[0]
    assert len(vector) == 1536
    components = {str(value) for value in vector[:8]}

    for record in caplog.records:
        if record.levelno < logging.INFO:
            continue
        message = record.getMessage()
        assert not (components & {part for part in message.split()}), message
        assert all(str(value) not in message for value in vector[:8]), message
        # A stage line is a handful of key=value pairs; 1536 floats could not hide in one.
        assert len(message) < 400, message


def test_only_one_lexical_query_is_in_flight_at_a_time() -> None:
    """The other half of D10: the branch races the provider, its two lists do not race
    each other. Two concurrent statements would hold two of the five pool connections
    against `max_overflow=0`, which is what racing the provider exists to avoid."""

    class _CountingSearch(FakeProductSearch):
        def __init__(self, rows):
            super().__init__(rows)
            self.in_flight = 0
            self.peak = 0

        async def search_lexical(self, request, *, depth, filters, pos_id=None):
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)
            try:
                await asyncio.sleep(0)
                return await super().search_lexical(
                    request, depth=depth, filters=filters, pos_id=pos_id
                )
            finally:
                self.in_flight -= 1

    search = _CountingSearch([_row(A, "S1", 0.2)])
    _serve(search)

    assert len(search.lexical_calls) == 2
    assert search.peak == 1, "the two lexical lists must not hold two pool connections"


def test_the_search_stage_does_not_borrow_the_response_confidence_field(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The two fields have different subjects, and they really do diverge.

    The case is a vector branch that found candidates while the lexical one found none: the
    branch is healthy, so the search stage would have said `low_confidence=False`, and the
    response is marked low confidence because nothing was produced by both branches. One
    trace, one field name, two opposite values — which is the kind of log that gets believed
    over the code.
    """
    rows = [_blind_row(A, "vector-only", 0.1), _blind_row(B, "also-vector", 0.2)]
    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
        response = _serve(FakeProductSearch(rows))

    messages = [record.getMessage() for record in caplog.records]
    search_entry = next(msg for msg in messages if "stage=search " in msg)
    fuse_entry = next(msg for msg in messages if "stage=fuse " in msg)

    assert "candidates=2" in search_entry, "the vector branch is healthy"
    assert "vector_empty=False" in search_entry
    assert "low_confidence" not in search_entry
    assert "low_confidence=True" in fuse_entry, "no candidate came from both branches"
    assert response.low_confidence is True
    assert len(response.results) == 2, "a signal, not a suppression"


# --------------------------------------------------------------------------------------
# C25 — fusion in two stages, with the flat mode conserved.
# --------------------------------------------------------------------------------------

#: The three queries of `descripcion-sin-anclaje` where the grade-2 document the vector branch
#: ranks FIRST lands at position 33 of the live hybrid. Measured on run `d9222333`.
BURIED_QUERIES = (
    ("la campanita que se cuelga a los bebes para protegerlos", "campanita"),
    ("follaje seco que cae en septiembre", "follaje"),
    ("una bicicleta antigua", "bicicleta"),
)


def _buried_corpus(decoy_word: str, *, decoys: int = 60):
    """A lexical list of `decoys` documents that the vector branch cannot see, plus one
    document only the vector branch sees and ranks first.

    The decoys sit above the distance threshold on purpose, so the two branches are disjoint.
    That is the regime the exploration modelled and the one the live queries are in: the
    grade-2 document is not somewhere in the lexical list, it is absent from it.
    """
    rows = [
        _row(
            UUID(f"00000000-0000-0000-0000-{index:012d}"),
            f"decoy-{index:02d}",
            0.9,  # above the 0.65 threshold: invisible to the vector branch
            doc_text=f"Tipo: {decoy_word} numero {index} de plata.",
        )
        for index in range(1, decoys + 1)
    ]
    target = _row(
        UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        "vector-top-hit",
        0.05,
        doc_text="Tipo: broche. Materiales: laton.",
    )
    return [*rows, target]


@pytest.mark.parametrize(("query", "decoy_word"), BURIED_QUERIES)
def test_vector_top_hit_reaches_the_top_five_without_lexical_consensus(
    query: str, decoy_word: str
) -> None:
    """The correction, stated as the property the baseline fails. C25 D5.

    Under the flat fusion the sixty lexical documents outscore the vector branch's best hit
    every time, so the document lands behind all of them. Under the two-stage fusion each
    branch holds one vote and the best hit of each takes one of the first two places.
    """
    payload = _request(query=query, top_k=5)

    branch = _serve(FakeProductSearch(_buried_corpus(decoy_word)), payload=payload)
    flat = _serve(
        FakeProductSearch(_buried_corpus(decoy_word)),
        payload=payload,
        fusion="flat",
        weight_typed=0.5,
        weight_expanded=0.5,
        weight_vector=0.33,
    )

    top_five = [item.sku for item in branch.results[:5]]
    assert "vector-top-hit" in top_five, f"buried under the two-stage fusion: {top_five}"
    assert "vector-top-hit" not in [item.sku for item in flat.results[:5]], (
        "the flat mode is supposed to bury it — if it no longer does, the baseline row "
        "has changed and the comparison this change rests on is gone"
    )


def test_branch_vote_is_independent_of_how_many_of_its_lists_matched() -> None:
    """The crossover stops being a property of the query nobody declared. C25 D5(a).

    Live, the vector branch needs wC > 0,469 when only the expanded list matched and
    wC > 0,938 when both did. Under the two-stage fusion the lexical branch votes `w_lex`
    in both regimes, so the position the vector branch's best candidate can reach is the same.
    """
    from jbg_ai.retrieval.orchestrator import _fuse_two_stage

    lexical_ids = [UUID(f"00000000-0000-0000-0000-{i:012d}") for i in range(1, 61)]
    target = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

    both_lists = _fuse_two_stage(
        lexical_ids,
        lexical_ids,
        [target],
        k=60,
        depth=60,
        branch_weights=(0.5, 0.5),
        internal_weights=(0.5, 0.5),
    )
    one_list_only = _fuse_two_stage(
        [],
        lexical_ids,
        [target],
        k=60,
        depth=60,
        branch_weights=(0.5, 0.5),
        internal_weights=(0.5, 0.5),
    )

    def position_of(fused) -> int:
        return [item.key for item in fused].index(target) + 1

    assert position_of(both_lists) == position_of(one_list_only)
    # And the branch leader holds exactly its declared weight in both regimes.
    for fused in (both_lists, one_list_only):
        by_key = {item.key: item.score for item in fused}
        assert by_key[lexical_ids[0]] == pytest.approx(0.5 / 61)
        assert by_key[target] == pytest.approx(0.5 / 61)


def test_multi_list_branch_contributes_no_more_candidates_than_a_single_list_one() -> None:
    """Sixty per branch, not a hundred and twenty. C25 D5(b).

    The second, independent over-weighting the exploration found: `typed` and `expanded` are
    truncated separately, so the lexical branch could present twice the slots of the vector
    branch. Stage 1's output is truncated at `depth` too, which closes it.
    """
    from jbg_ai.retrieval.orchestrator import LEXICAL_BRANCH_LIST, VECTOR_LIST, _fuse_two_stage

    typed_ids = [UUID(f"00000000-0000-0000-0000-{i:012d}") for i in range(1, 61)]
    expanded_ids = [UUID(f"11111111-0000-0000-0000-{i:012d}") for i in range(1, 61)]
    vector_ids = [UUID(f"22222222-0000-0000-0000-{i:012d}") for i in range(1, 61)]
    assert not (set(typed_ids) & set(expanded_ids)), "the two lexical lists must be disjoint"

    fused = _fuse_two_stage(
        typed_ids,
        expanded_ids,
        vector_ids,
        k=60,
        depth=60,
        branch_weights=(0.5, 0.5),
        internal_weights=(0.5, 0.5),
    )

    from_lexical = [item for item in fused if LEXICAL_BRANCH_LIST in item.ranks]
    from_vector = [item for item in fused if VECTOR_LIST in item.ranks]

    assert len(from_lexical) == 60, f"the lexical branch contributed {len(from_lexical)}"
    assert len(from_lexical) == len(from_vector) == 60


def test_low_confidence_means_the_same_under_both_fusion_modes() -> None:
    """Stage 2 has exactly two lists, and they are exactly the two branches. C25 D5(c).

    Under the flat fusion, `len(reasons) > 1` needed a written nuance: a candidate seen by
    both LEXICAL lists is not cross-branch, because with the expansion disabled the two lists
    are identical and every lexical hit would qualify. Under the two-stage fusion the nuance
    is structural rather than explained — the lexical branch presents ONE list — so the
    signal cannot drift back to meaning "two lists agreed".

    The requirement is unchanged, so the behaviour must be unchanged too.
    """
    agreeing = [_row(A, "both", 0.1)]
    disagreeing = [_blind_row(B, "vector-only", 0.1), _row(C, "lexical-only", 0.9)]
    flat = dict(fusion="flat", weight_typed=0.5, weight_expanded=0.5, weight_vector=0.33)

    for rows, expected in ((agreeing, False), (disagreeing, True)):
        branch_mode = _serve(FakeProductSearch(list(rows)))
        flat_mode = _serve(FakeProductSearch(list(rows)), **flat)
        assert branch_mode.low_confidence is expected
        assert flat_mode.low_confidence is expected, "the signal changed meaning with the mode"


def test_a_candidate_seen_by_both_lexical_lists_alone_is_not_cross_branch() -> None:
    """The nuance that justified the rule, now witnessed under the live fusion.

    `both-lexical-lists` matches the operator's literal text AND the equivalence groups, and
    the vector branch cannot see it. It must NOT count as consensus, in either mode.
    """
    rows = [_row(A, "both-lexical-lists", 0.9)]  # above threshold: the vector branch is blind

    for kwargs in ({}, dict(fusion="flat", weight_typed=0.5, weight_expanded=0.5, weight_vector=0.33)):
        response = _serve(FakeProductSearch(list(rows)), **kwargs)
        assert response.low_confidence is True, "two lexical lists are not two branches"
        assert [item.sku for item in response.results] == ["both-lexical-lists"]
