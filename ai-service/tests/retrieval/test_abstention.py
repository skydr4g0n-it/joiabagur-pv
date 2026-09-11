"""Whether the catalogue can answer at all: the relative rule, and what it must never do. C25.

Offline throughout: an injected search port and an injected embedding client. Nothing here
opens a socket.

The form of the rule was chosen by a measurement under a criterion written before it. The two
populations of best-hit distance overlap completely - the whole out-of-domain range sits inside
the answerable one - so a scalar bound cannot separate them, and what the relative rule reads is
the SHAPE of the distance profile: an out-of-domain query is flat, because nothing in the
catalogue stands out for it.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import pytest

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.schemas.retrieval import RetrievalMode, RetrievalRequest
from jbg_ai.retrieval.abstention import (
    AbstentionRule,
    candidates_in_band,
    log_decision,
    should_abstain,
)
from jbg_ai.retrieval.errors import RetrievalDependencyError
from jbg_ai.retrieval.orchestrator import retrieve_products
from support.fake_embedding_client import FakeEmbeddingClient
from support.fake_product_search import FakeAssignment, FakeIndexedRow, FakeProductSearch
from support.settings import TOKEN_POS_ID, TOKEN_TRACE_ID, build_settings

PRINCIPAL = ServicePrincipal(
    user_id="u-1", role="Operator", trace_id=TOKEN_TRACE_ID, pos_id=TOKEN_POS_ID
)
DOC = "Tipo: anillo de plata. Materiales: plata."

#: The measured operating point on the five out-of-domain queries: three of five caught at a
#: cost of four answerable ones, four times cheaper than the scalar. A STARTING POINT for the
#: calibration that follows the category growing to 15-20, not a fixed figure.
LIVE = AbstentionRule(enabled=True, band_alpha=0.05, min_candidates=10)


def _run(coro):
    return asyncio.run(coro)


def _rows(distances, *, doc_text: str = DOC):
    return [
        FakeIndexedRow(
            product_id=UUID(f"00000000-0000-0000-0000-{index:012d}"),
            sku=f"SKU{index:02d}",
            distance=distance,
            materials=["plata"],
            piece_type="anillo",
            doc_text=doc_text,
        )
        for index, distance in enumerate(distances, start=1)
    ]


def _serve(search, **kwargs):
    return _run(
        retrieve_products(
            RetrievalRequest(query="anillo de plata", top_k=5),
            PRINCIPAL,
            settings=kwargs.pop("settings", build_settings()),
            embed=kwargs.pop("embed", FakeEmbeddingClient()),
            search=search,
            **kwargs,
        )
    )


# --------------------------------------------------------------------------- the shape rule


def test_a_flat_distance_profile_is_what_the_rule_reads() -> None:
    """Flat means nothing stands out, which is the shape of a query the catalogue cannot answer."""
    flat = [0.50, 0.505, 0.51, 0.512, 0.515, 0.518, 0.52, 0.521, 0.522, 0.523]
    peaked = [0.21, 0.44, 0.47, 0.49, 0.51, 0.52, 0.53, 0.54, 0.55, 0.56]

    assert candidates_in_band(flat, 0.05) == 10, "everything sits inside the band"
    assert candidates_in_band(peaked, 0.05) == 1, "only the peak does"

    assert should_abstain(flat, LIVE) is True
    assert should_abstain(peaked, LIVE) is False


def test_the_rule_reads_the_shape_and_not_the_level() -> None:
    """A scalar cannot separate the two populations, which is why this form was chosen.

    These two profiles have the SAME best distance. A bound on that number would treat them
    identically; the relative rule separates them, because one has a peak and one does not.
    """
    same_best_flat = [0.45, 0.455, 0.46, 0.462, 0.465, 0.467, 0.469, 0.47, 0.471, 0.472]
    same_best_peaked = [0.45, 0.62, 0.64, 0.65, 0.66, 0.67, 0.68, 0.69, 0.70, 0.71]

    assert min(same_best_flat) == min(same_best_peaked)
    assert should_abstain(same_best_flat, LIVE) is True
    assert should_abstain(same_best_peaked, LIVE) is False


def test_an_empty_distance_list_is_not_a_flat_profile() -> None:
    """Absence is not flatness, and conflating them lets an abstention stand in for a failure."""
    assert candidates_in_band([], 0.05) == 0
    assert should_abstain([], LIVE) is False


def test_the_rule_is_disabled_by_default() -> None:
    """Two parameters cannot be fixed against five out-of-domain queries.

    Enabling it can only make the service answer LESS, so the default that changes nothing is
    the safe one. It is implemented, measured and published, and it decides nothing until the
    category grows to 15-20 - which costs no per-document labelling, because every document is
    grade zero there by the annotation criterion.
    """
    settings = build_settings()
    assert settings.jpv_abstention_enabled is False
    assert AbstentionRule().enabled is False
    assert AbstentionRule().describe() == "disabled"

    flat = [0.50] * 20
    assert should_abstain(flat, AbstentionRule()) is False, "disabled decides nothing"


# ------------------------------------------------------------------ what it must never do


def test_abstention_does_not_fire_on_answerable_queries() -> None:
    """The hard half of the trade. Raising the rate is trivial; not silencing answers is the work.

    The spec puts it as a requirement rather than an aspiration: a rule that abstains on a
    query whose labelled relevant set is non-empty MUST be reported as costing an answer.
    """
    answerable = _rows([0.18, 0.44, 0.47, 0.50, 0.52, 0.55, 0.58, 0.60, 0.62, 0.64])

    response = _serve(FakeProductSearch(answerable), abstain=True)

    assert response.results, "an answerable query must not be silenced"
    assert response.low_confidence is False
    assert response.candidates_returned == len(response.results)


def test_a_dependency_failure_is_not_disguised_as_an_abstention() -> None:
    """A 200 with an empty list is indistinguishable from a deliberate abstention.

    So the provider failure has to keep failing loudly. C16's panel paints its "we found
    nothing" screen on exactly the shape an abstention produces, and serving a broken
    dependency behind it is the lie the fusion design's D8 prevents.
    """
    from jbg_ai.indexing.errors import EmbeddingError

    class _Boom(FakeEmbeddingClient):
        async def embed(self, texts):  # type: ignore[override]
            raise EmbeddingError("provider down")

    # Nothing lexical to degrade to either, so there is no honest 200 available.
    search = FakeProductSearch(_rows([0.5] * 20, doc_text="Tipo: broche. Materiales: laton."))

    with pytest.raises(RetrievalDependencyError):
        _serve(search, embed=_Boom(), abstain=True)


def test_an_empty_projection_is_not_an_abstention() -> None:
    """A point of sale that carries nothing fails loudly, as the projection capability defines."""
    search = FakeProductSearch(_rows([0.5] * 20), assignments=[])

    with pytest.raises(RetrievalDependencyError):
        _serve(search, pos_prefilter=True, abstain=True)


def test_an_abstention_is_a_decision_about_the_query_not_a_filter() -> None:
    """It returns no candidate AND marks low confidence, so the two cases stay distinguishable.

    An abstention built by removing candidates one at a time would be indistinguishable from a
    retrieval that merely found little, and the two ask different things of the operator.
    """
    flat = _rows([0.50, 0.505, 0.51, 0.512, 0.515, 0.518, 0.52, 0.521, 0.522, 0.523])

    answered = _serve(FakeProductSearch(list(flat)))
    abstained = _serve(FakeProductSearch(list(flat)), abstain=True)

    assert answered.results, "the premise: with the rule off this query is answered"
    assert answered.low_confidence is False

    assert abstained.results == [], "no candidate is returned"
    assert abstained.candidates_returned == 0
    assert abstained.low_confidence is True, "and it is marked, so it is not an empty page"


def test_the_rule_does_not_alter_the_candidate_set() -> None:
    """The property that decides its phase, and that keeps the persisted windows valid.

    A rule expressed as a distance bound inside the retrieval statement changes which
    candidates exist; this one runs after the fusion and changes only whether they are served.
    """
    flat = _rows([0.50, 0.505, 0.51, 0.512, 0.515, 0.518, 0.52, 0.521, 0.522, 0.523])
    search_off = FakeProductSearch(list(flat))
    search_on = FakeProductSearch(list(flat))

    _serve(search_off)
    _serve(search_on, abstain=True)

    assert search_off.search_calls[0]["threshold"] == search_on.search_calls[0]["threshold"]
    assert search_off.search_calls[0]["depth"] == search_on.search_calls[0]["depth"]
    assert len(search_off.search_calls) == len(search_on.search_calls)


# ------------------------------------------------------------------------ observability


def test_the_abstention_decision_is_logged_with_its_inputs(caplog) -> None:
    flat = _rows([0.50, 0.505, 0.51, 0.512, 0.515, 0.518, 0.52, 0.521, 0.522, 0.523])

    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.abstention"):
        _serve(FakeProductSearch(flat), abstain=True)

    entry = next(message for message in caplog.messages if "stage=abstain" in message)
    assert TOKEN_TRACE_ID in entry
    assert "rule=band(alpha=0.05,n>=10)" in entry
    assert "best_distance=0.5000" in entry
    assert "decision=abstain" in entry


def test_no_vector_reaches_the_abstention_log(caplog) -> None:
    """It cannot, and the guarantee is the signature rather than the discipline of the caller.

    Every entry point of this module takes `Sequence[float]` - distances, which are scalars.
    There is no argument through which an embedding could arrive, so none can be logged.
    """
    import ast
    import inspect
    import typing
    from collections.abc import Sequence

    from jbg_ai.retrieval import abstention

    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.abstention"):
        _serve(FakeProductSearch(_rows([0.2, 0.5, 0.6])), abstain=True)

    entry = next(message for message in caplog.messages if "stage=abstain" in message)
    assert "[" not in entry and "embedding" not in entry

    for function in (abstention.should_abstain, abstention.candidates_in_band, log_decision):
        hints = typing.get_type_hints(function)
        assert hints.get("distances") == Sequence[float], function.__name__
    # And the module imports nothing that could hand it one. A source-text search would be
    # checking the prose instead of the code - the docstring says the word - so what is
    # asserted is the import graph, which is what actually constrains the behaviour.
    tree = ast.parse(inspect.getsource(abstention))
    imported = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not any("indexing" in name or "embed" in name for name in imported), imported


def test_the_decision_is_logged_even_when_it_answers(caplog) -> None:
    """Otherwise the log only shows the rule on the queries it silenced, which is half of it."""
    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.abstention"):
        _serve(FakeProductSearch(_rows([0.2, 0.5, 0.6])), abstain=True)

    entry = next(message for message in caplog.messages if "stage=abstain" in message)
    assert "decision=answer" in entry


def test_the_rule_describes_itself_with_its_parameters() -> None:
    """The report cites the rule in force, so it has to be renderable in one string."""
    assert LIVE.describe() == "band(alpha=0.05,n>=10)"
    assert AbstentionRule(enabled=False).describe() == "disabled"


def test_log_decision_handles_an_empty_profile() -> None:
    """A query the vector branch answered with nothing still logs, and names the absence."""
    log_decision(trace_id="t", rule=LIVE, distances=[], abstained=False)
