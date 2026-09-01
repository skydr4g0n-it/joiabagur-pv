"""Vector retrieval orchestrator: embed, threshold, overfetch, abstention. Delivered by C14."""

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
    VECTOR_UNTIL_C21_NOTE,
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
        **kwargs,
    )


def test_returns_empty_with_low_confidence_when_all_above_threshold() -> None:
    search = FakeProductSearch([_row(A, "S1", 0.9), _row(B, "S2", 0.8)])
    response = _run(
        retrieve_products(
            _request(),
            PRINCIPAL,
            settings=build_settings(),
            embed=FakeEmbeddingClient(),
            search=search,
        )
    )

    assert response.results == []
    assert response.candidates_returned == 0
    assert response.low_confidence is True
    assert response.effective_pos_id == TOKEN_POS_ID
    assert search.search_calls[0]["threshold"] == 0.65


def test_returns_overfetched_candidate_count() -> None:
    rows = [_row(UUID(int=index), f"S{index}", 0.1 + index * 0.001) for index in range(20)]
    search = FakeProductSearch(rows)
    response = _run(
        retrieve_products(
            _request(top_k=5),
            PRINCIPAL,
            settings=build_settings(),
            embed=FakeEmbeddingClient(),
            search=search,
        )
    )

    assert len(response.results) == 15
    assert response.candidates_returned == 15
    assert response.low_confidence is False
    assert search.search_calls[0]["overfetch"] == 15


def test_overfetch_does_not_refill_from_rows_above_threshold() -> None:
    rows = [
        _row(A, "S1", 0.2),
        _row(B, "S2", 0.3),
        *[_row(UUID(int=index + 10), f"X{index}", 0.9) for index in range(20)],
    ]
    response = _run(
        retrieve_products(
            _request(top_k=5),
            PRINCIPAL,
            settings=build_settings(),
            embed=FakeEmbeddingClient(),
            search=FakeProductSearch(rows),
        )
    )

    assert len(response.results) == 2
    assert response.candidates_returned == 2
    assert all(item.score >= 0.35 for item in response.results)


def test_results_ordered_by_ascending_distance() -> None:
    search = FakeProductSearch(
        [_row(A, "far", 0.4), _row(B, "near", 0.1), _row(C, "mid", 0.2)]
    )
    response = _run(
        retrieve_products(
            _request(),
            PRINCIPAL,
            settings=build_settings(),
            embed=FakeEmbeddingClient(),
            search=search,
        )
    )

    distances_as_scores = [round(1.0 - d, 4) for d in (0.1, 0.2, 0.4)]
    assert [item.sku for item in response.results] == ["near", "mid", "far"]
    assert [item.score for item in response.results] == distances_as_scores
    assert all(0.0 <= item.score <= 1.0 for item in response.results)
    assert all("vector" in item.match_reasons for item in response.results)
    assert all("lexical" not in item.match_reasons for item in response.results)


def test_empty_compatible_index_raises_dependency_error() -> None:
    search = FakeProductSearch(compatible_count=0)
    with pytest.raises(RetrievalDependencyError, match="compatible"):
        _run(
            retrieve_products(
                _request(),
                PRINCIPAL,
                settings=build_settings(),
                embed=FakeEmbeddingClient(),
                search=search,
            )
        )
    assert search.search_calls == []


def test_retrieval_embed_client_uses_max_attempts_one() -> None:
    from jbg_ai.indexing.constants import MAX_EMBED_ATTEMPTS

    client = build_retrieval_embed_client(build_settings(jpv_embedding_api_key="sk-test"))

    assert client.max_attempts == 1
    assert MAX_EMBED_ATTEMPTS == 3


def test_body_filters_materials_category_family_and_exclusions() -> None:
    excluded = UUID("99999999-9999-9999-9999-999999999999")
    search = FakeProductSearch(
        [
            _row(A, "keep", 0.1, materials=["plata"], piece_type="anillo", family_id=FAMILY),
            _row(B, "mat", 0.1, materials=["oro"], piece_type="anillo", family_id=FAMILY),
            _row(C, "cat", 0.1, materials=["plata"], piece_type="collar", family_id=FAMILY),
            _row(
                UUID("33333333-3333-3333-3333-333333333333"),
                "fam",
                0.1,
                materials=["plata"],
                piece_type="anillo",
                family_id=OTHER_FAMILY,
            ),
            _row(
                excluded,
                "ex",
                0.1,
                materials=["plata"],
                piece_type="anillo",
                family_id=FAMILY,
            ),
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
    response = _run(
        retrieve_products(
            payload,
            PRINCIPAL,
            settings=build_settings(),
            embed=FakeEmbeddingClient(),
            search=search,
        )
    )

    assert [item.sku for item in response.results] == ["keep"]
    assert str(excluded) not in [item.product_id for item in response.results]


def test_invalid_family_id_raises_before_search() -> None:
    search = FakeProductSearch([_row(A, "S1", 0.1)])
    payload = _request(filters=RetrievalFilters(family_id="not-a-uuid"))
    with pytest.raises(InvalidFamilyIdError):
        _run(
            retrieve_products(
                payload,
                PRINCIPAL,
                settings=build_settings(),
                embed=FakeEmbeddingClient(),
                search=search,
            )
        )
    assert search.count_calls == []
    assert search.search_calls == []


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


def test_hybrid_and_lexical_modes_run_vector_branch() -> None:
    search = FakeProductSearch([_row(A, "S1", 0.2)])
    for mode in (RetrievalMode.HYBRID, RetrievalMode.LEXICAL, None):
        kwargs = {} if mode is None else {"mode": mode}
        response = _run(
            retrieve_products(
                _request(**kwargs),
                PRINCIPAL,
                settings=build_settings(),
                embed=FakeEmbeddingClient(),
                search=search,
            )
        )
        assert response.results
        assert "vector" in response.results[0].match_reasons
        assert "lexical" not in response.results[0].match_reasons
        assert response.results[0].debug is not None
        assert VECTOR_UNTIL_C21_NOTE in response.results[0].debug.notes


def test_vector_mode_omits_until_c21_note() -> None:
    search = FakeProductSearch([_row(A, "S1", 0.2)])
    response = _run(
        retrieve_products(
            _request(mode=RetrievalMode.VECTOR),
            PRINCIPAL,
            settings=build_settings(),
            embed=FakeEmbeddingClient(),
            search=search,
        )
    )

    assert response.results[0].debug is not None
    assert VECTOR_UNTIL_C21_NOTE not in response.results[0].debug.notes
    assert response.results[0].debug.vector_score == response.results[0].score


def test_trace_id_appears_in_stage_logs(caplog: pytest.LogCaptureFixture) -> None:
    search = FakeProductSearch([_row(A, "S1", 0.2)])
    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
        _run(
            retrieve_products(
                _request(),
                PRINCIPAL,
                settings=build_settings(),
                embed=FakeEmbeddingClient(),
                search=search,
            )
        )

    messages = [record.getMessage() for record in caplog.records]
    embed_logs = [msg for msg in messages if "stage=embed" in msg]
    search_logs = [msg for msg in messages if "stage=search" in msg]
    assert embed_logs
    assert search_logs
    assert all(TOKEN_TRACE_ID in msg for msg in embed_logs)
    assert all(TOKEN_TRACE_ID in msg for msg in search_logs)
    assert all(getattr(record, "trace_id", None) == TOKEN_TRACE_ID for record in caplog.records)


def test_embed_failure_is_a_dependency_error() -> None:
    class _Boom(FakeEmbeddingClient):
        async def embed(self, texts: list[str]):
            raise EmbeddingError("provider down")

    search = FakeProductSearch([_row(A, "S1", 0.1)])
    with pytest.raises(RetrievalDependencyError, match="provider down"):
        _run(
            retrieve_products(
                _request(),
                PRINCIPAL,
                settings=build_settings(),
                embed=_Boom(),
                search=search,
            )
        )


def test_expand_stage_log_carries_trace_id(caplog: pytest.LogCaptureFixture) -> None:
    search = FakeProductSearch([_row(A, "S1", 0.1)])
    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
        _run(
            retrieve_products(
                _request(query="sortija de plata"),
                PRINCIPAL,
                settings=build_settings(),
                embed=FakeEmbeddingClient(),
                search=search,
            )
        )

    expand_logs = [msg for msg in (r.getMessage() for r in caplog.records) if "stage=expand" in msg]
    assert expand_logs
    assert all(TOKEN_TRACE_ID in msg for msg in expand_logs)
    assert "enabled=True" in expand_logs[0]
    assert "matched_terms=" in expand_logs[0]
    assert "consumed=False" in expand_logs[0], "C21 is the consumer; C20 must not claim one"


def test_expansion_flag_sweeps_two_configurations_in_one_process(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """C24 needs this: an environment-only switch would force a restart per config."""
    settings = build_settings(jpv_query_expansion_enabled=True)
    responses = []
    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
        for enabled in (True, False):
            search = FakeProductSearch([_row(A, "S1", 0.1)])
            responses.append(
                _run(
                    retrieve_products(
                        _request(query="sortija de plata"),
                        PRINCIPAL,
                        settings=settings,
                        embed=FakeEmbeddingClient(),
                        search=search,
                        expand_synonyms=enabled,
                    )
                )
            )

    assert settings.jpv_query_expansion_enabled is True, "the settings object is not mutated"
    expand_logs = [msg for msg in (r.getMessage() for r in caplog.records) if "stage=expand" in msg]
    assert any("enabled=True" in msg for msg in expand_logs)
    assert any("enabled=False" in msg for msg in expand_logs)
    assert responses[0].model_dump() == responses[1].model_dump()


def test_response_is_unchanged_while_expansion_has_no_consumer() -> None:
    """Until C21 reads the groups, the endpoint must answer exactly as it did before."""
    bodies = []
    for enabled in (True, False):
        search = FakeProductSearch([_row(A, "S1", 0.1), _row(B, "S2", 0.2)])
        response = _run(
            retrieve_products(
                _request(query="gargantilla dorada"),
                PRINCIPAL,
                settings=build_settings(jpv_query_expansion_enabled=enabled),
                embed=FakeEmbeddingClient(),
                search=search,
            )
        )
        bodies.append(response.model_dump())

    assert bodies[0] == bodies[1]
    assert all(item["match_reasons"] == ["vector"] for item in bodies[0]["results"])


def test_vector_branch_embeds_the_original_text() -> None:
    """The expansion feeds the lexical branch only; the vector query is never rewritten."""
    embed = FakeEmbeddingClient()
    search = FakeProductSearch([_row(A, "S1", 0.1)])
    _run(
        retrieve_products(
            _request(query="sortija de plata"),
            PRINCIPAL,
            settings=build_settings(jpv_query_expansion_enabled=True),
            embed=embed,
            search=search,
        )
    )

    assert embed.provider_calls == [["sortija de plata"]]
