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

#: The point fixed against the category once it grew to 20: it abstains on 2 of those 20 and
#: on none of the 43 answerable queries. The only operating points that silence no answerable
#: query are this one and two that catch less.
LIVE = AbstentionRule(enabled=True, band_alpha=0.03, min_candidates=15)

#: A flat profile needs at least `min_candidates` entries to be flat, so the fixtures carry
#: twenty: ten could never trip a rule that asks for fifteen, and a test that passed on that
#: technicality would witness nothing.
FLAT = [0.500 + 0.0005 * index for index in range(20)]
PEAKED = [0.21] + [0.44 + 0.01 * index for index in range(19)]


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
    assert candidates_in_band(FLAT, 0.03) == 20, "everything sits inside the band"
    assert candidates_in_band(PEAKED, 0.03) == 1, "only the peak does"

    assert should_abstain(FLAT, LIVE) is True
    assert should_abstain(PEAKED, LIVE) is False


def test_the_rule_reads_the_shape_and_not_the_level() -> None:
    """A scalar cannot separate the two populations, which is why this form was chosen.

    These two profiles have the SAME best distance. A bound on that number would treat them
    identically; the relative rule separates them, because one has a peak and one does not.
    """
    same_best_flat = [0.45 + 0.0005 * index for index in range(20)]
    same_best_peaked = [0.45] + [0.62 + 0.005 * index for index in range(19)]

    assert min(same_best_flat) == min(same_best_peaked)
    assert should_abstain(same_best_flat, LIVE) is True
    assert should_abstain(same_best_peaked, LIVE) is False


def test_an_empty_distance_list_is_not_a_flat_profile() -> None:
    """Absence is not flatness, and conflating them lets an abstention stand in for a failure."""
    assert candidates_in_band([], 0.03) == 0
    assert should_abstain([], LIVE) is False


def test_the_live_rule_is_the_one_the_measurement_fixed() -> None:
    """Enabled, at the band fixed against 20 out-of-domain and 43 answerable queries.

    The only operating points that silence no answerable query are this one and two that catch
    less, so it is the most the rule can do for free. The 0,80 the ticket asked for costs
    silencing 21 of the 43, and that gap is declared rather than closed.
    """
    from jbg_ai.config.settings import ABSTENTION_DEFAULTS

    settings = build_settings()
    assert settings.jpv_abstention_enabled is True
    assert settings.jpv_abstention_band_alpha == 0.03
    assert settings.jpv_abstention_band_min_candidates == 15
    assert ABSTENTION_DEFAULTS["jpv_abstention_enabled"] is True

    # The dataclass stays disabled, so a rule built by hand silences nothing by accident.
    assert AbstentionRule().enabled is False
    assert AbstentionRule().describe() == "disabled"
    assert should_abstain([0.50] * 20, AbstentionRule()) is False

    # And turning it off is the rollback: every query is answered again.
    assert should_abstain(FLAT, AbstentionRule(enabled=False)) is False


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
    flat = _rows(FLAT)

    answered = _serve(FakeProductSearch(list(flat)), abstain=False)
    abstained = _serve(FakeProductSearch(list(flat)), abstain=True)

    assert answered.results, "the premise: with the rule off this query is answered"
    assert len(answered.results) > 0
    assert answered.low_confidence is False

    assert abstained.results == [], "no candidate is returned"
    assert abstained.candidates_returned == 0
    assert abstained.low_confidence is True, "and it is marked, so it is not an empty page"


def test_the_rule_does_not_alter_the_candidate_set() -> None:
    """The property that decides its phase, and that keeps the persisted windows valid.

    A rule expressed as a distance bound inside the retrieval statement changes which
    candidates exist; this one runs after the fusion and changes only whether they are served.
    """
    flat = _rows(FLAT)
    search_off = FakeProductSearch(list(flat))
    search_on = FakeProductSearch(list(flat))

    _serve(search_off, abstain=False)
    _serve(search_on, abstain=True)

    assert search_off.search_calls[0]["threshold"] == search_on.search_calls[0]["threshold"]
    assert search_off.search_calls[0]["depth"] == search_on.search_calls[0]["depth"]
    assert len(search_off.search_calls) == len(search_on.search_calls)


# ------------------------------------------------------------------------ observability


def test_the_abstention_decision_is_logged_with_its_inputs(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.abstention"):
        _serve(FakeProductSearch(_rows(FLAT)), abstain=True)

    entry = next(message for message in caplog.messages if "stage=abstain" in message)
    assert TOKEN_TRACE_ID in entry
    assert "rule=band(alpha=0.03,n>=15)" in entry
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
    assert LIVE.describe() == "band(alpha=0.03,n>=15)"
    assert AbstentionRule(enabled=False).describe() == "disabled"


def test_log_decision_handles_an_empty_profile() -> None:
    """A query the vector branch answered with nothing still logs, and names the absence."""
    log_decision(trace_id="t", rule=LIVE, distances=[], abstained=False)
