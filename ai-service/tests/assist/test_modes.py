"""Mode resolution and the structural intent. Delivered by C30a. Pure, no I/O at all."""

from __future__ import annotations

import pytest

from jbg_ai.assist.constants import (
    ASSIST_INTENTS,
    INTENT_IN_DOMAIN,
    INTENT_NOT_IN_CATALOGUE,
    INTENT_OUT_OF_DOMAIN,
    INTENT_PRODUCT_PITCH,
    INTENT_UNCLASSIFIED,
)
from jbg_ai.assist.errors import NoAnchorError
from jbg_ai.assist.modes import AssistMode, resolve_mode


def test_a_piece_with_no_question_resolves_to_the_piece_only_mode() -> None:
    assert resolve_mode(product_id="P-1", query=None) is AssistMode.PIECE_ONLY


def test_a_question_with_no_piece_resolves_to_the_query_only_mode() -> None:
    assert resolve_mode(product_id=None, query="¿se puede mojar?") is AssistMode.QUERY_ONLY


def test_a_piece_with_a_question_resolves_to_the_third_mode() -> None:
    mode = resolve_mode(product_id="P-1", query="¿se puede mojar?")

    assert mode is AssistMode.PIECE_AND_QUERY


def test_neither_anchor_is_an_error_naming_both_fields() -> None:
    with pytest.raises(NoAnchorError) as error:
        resolve_mode(product_id=None, query=None)

    message = str(error.value)
    assert "product_id" in message
    assert "query" in message


def test_a_blank_query_is_not_an_anchor() -> None:
    """Whitespace would put the request in a mode with a question and hand the search none."""
    assert resolve_mode(product_id="P-1", query="   ") is AssistMode.PIECE_ONLY

    with pytest.raises(NoAnchorError):
        resolve_mode(product_id=None, query="   ")


def test_a_blank_product_id_is_not_an_anchor() -> None:
    assert resolve_mode(product_id="  ", query="anillo") is AssistMode.QUERY_ONLY


# --- the intent is structural ------------------------------------------------------------


def test_the_piece_anchored_mode_is_the_only_one_reporting_a_determinate_intent() -> None:
    assert AssistMode.PIECE_ONLY.intent == INTENT_PRODUCT_PITCH
    assert AssistMode.QUERY_ONLY.intent == INTENT_UNCLASSIFIED
    assert AssistMode.PIECE_AND_QUERY.intent == INTENT_UNCLASSIFIED


def test_two_queries_worded_differently_with_the_same_anchors_report_one_intent() -> None:
    """No keyword heuristic: «regalo» must not move the value, and neither must anything."""
    wordings = [
        "un regalo para mi madre",
        "¿se puede mojar en la piscina?",
        "REGALO",
        "anillo de plata barato",
        "¿qué significa el 925?",
    ]
    intents = {resolve_mode(product_id=None, query=text).intent for text in wordings}

    assert intents == {INTENT_UNCLASSIFIED}

    anchored = {
        resolve_mode(product_id="P-1", query=text).intent for text in wordings
    }
    assert anchored == {INTENT_UNCLASSIFIED}


def test_the_intent_vocabulary_gained_the_routing_verdicts_and_kept_the_piece_anchored_one() -> None:
    """C31 replaced `unclassified` in the free-query mode and never touched `product_pitch`,
    which is exactly what `modes.py` promised before the router existed.

    **This module still derives only the two structural values.** The three verdicts are
    reachable only through the classifier, which runs in the free-query mode alone, so the
    intents a *mode* can produce stay a strict subset of the vocabulary a *response* can carry.
    """
    assert ASSIST_INTENTS == (
        INTENT_PRODUCT_PITCH,
        INTENT_IN_DOMAIN,
        INTENT_OUT_OF_DOMAIN,
        INTENT_NOT_IN_CATALOGUE,
        INTENT_UNCLASSIFIED,
    )
    assert INTENT_PRODUCT_PITCH in ASSIST_INTENTS
    assert {mode.intent for mode in AssistMode} == {
        INTENT_PRODUCT_PITCH,
        INTENT_UNCLASSIFIED,
    }
    assert {mode.intent for mode in AssistMode} < set(ASSIST_INTENTS)


def test_only_the_query_only_mode_is_not_anchored() -> None:
    assert not AssistMode.QUERY_ONLY.is_anchored
    assert AssistMode.PIECE_ONLY.is_anchored
    assert AssistMode.PIECE_AND_QUERY.is_anchored
