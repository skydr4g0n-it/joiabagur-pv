"""Weighted RRF: consensus, symmetric depth and the measured defaults. Delivered by C21."""

from __future__ import annotations

import socket

import pytest

from jbg_ai.config.settings import FUSION_DEFAULTS
from jbg_ai.retrieval import fusion as fusion_module
from jbg_ai.retrieval.fusion import (
    DEFAULT_BRANCH_DEPTH,
    DEFAULT_RRF_K,
    RankedList,
    fuse,
    normalised_scores,
    truncate,
)
from support.settings import build_settings

K = DEFAULT_RRF_K


def _list(name: str, weight: float, *keys: str) -> RankedList:
    return RankedList(name=name, weight=weight, keys=keys)


def test_rrf_fuses_ranked_lists_preserving_top_hit() -> None:
    """Consensus outranks a single-list champion: 2nd + 5th beats 1st and absent."""
    fused = fuse(
        [
            _list("a", 1.0, "champion", "consensus", "x", "y", "z"),
            _list("b", 1.0, "p", "q", "r", "s", "consensus"),
        ],
        k=K,
        depth=DEFAULT_BRANCH_DEPTH,
    )

    assert fused[0].key == "consensus"
    assert fused[0].ranks == {"a": 2, "b": 5}
    assert fused[0].list_count == 2
    champion = next(item for item in fused if item.key == "champion")
    assert champion.ranks == {"a": 1}
    assert champion.score < fused[0].score


def test_provenance_reports_every_list_and_position() -> None:
    fused = fuse([_list("a", 1.0, "x", "y"), _list("b", 0.33, "y")], k=K, depth=10)
    by_key = {item.key: item for item in fused}

    assert by_key["y"].ranks == {"a": 2, "b": 1}
    assert by_key["x"].ranks == {"a": 1}
    assert by_key["y"].lists == ("a", "b")


def test_fusion_performs_no_input_or_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pure by contract: C23, C25 and C26 import it without an endpoint around it."""

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the fusion must not open a socket")

    monkeypatch.setattr(socket.socket, "connect", _fail)
    monkeypatch.setattr(socket, "create_connection", _fail)

    assert fuse([_list("a", 1.0, "x")], k=K, depth=10)[0].key == "x"

    source = fusion_module.__doc__ or ""
    assert "session" not in fusion_module.__dict__
    for forbidden in ("sqlalchemy", "psycopg", "litellm", "session_scope"):
        assert forbidden not in str(sorted(fusion_module.__dict__)), forbidden
    assert source


def test_raw_branch_scores_are_not_consumed() -> None:
    """`RankedList` has room for identifiers and a weight, and for nothing else."""
    fields = set(RankedList.__dataclass_fields__)

    assert fields == {"name", "weight", "keys"}
    assert "distance" not in fields
    assert "ts_rank" not in fields


def test_branch_depth_is_symmetric_across_lists() -> None:
    long_list = _list("lexical", 0.5, *[f"L{index}" for index in range(200)])
    short_list = _list("vector", 0.33, *[f"V{index}" for index in range(60)])

    fused = fuse([long_list, short_list], k=K, depth=10)
    per_list: dict[str, int] = {}
    for item in fused:
        for name in item.ranks:
            per_list[name] = per_list.get(name, 0) + 1

    assert per_list == {"lexical": 10, "vector": 10}
    assert max(rank for item in fused for rank in item.ranks.values()) == 10


def test_branch_depth_is_independent_of_overfetch() -> None:
    """`over_retrieval_count` follows `top_k`; the depth does not follow anything."""
    from jbg_ai.stubs.responses import over_retrieval_count

    keys = [f"K{index}" for index in range(100)]
    fused = fuse([_list("a", 1.0, *keys)], k=K, depth=40)

    assert len(fused) == 40
    assert over_retrieval_count(5) == 15
    assert over_retrieval_count(20) == 60
    assert len(fuse([_list("a", 1.0, *keys)], k=K, depth=40)) == 40


def test_truncate_keeps_first_occurrence_and_the_order() -> None:
    assert truncate(["a", "b", "a", "c"], depth=10) == ("a", "b", "c")
    assert truncate(["a", "b", "c"], depth=2) == ("a", "b")


def test_fusion_weights_and_k_load_from_settings_not_hardcoded() -> None:
    settings = build_settings()

    assert settings.jpv_rrf_k == 60
    assert settings.jpv_rrf_weight_typed == 0.5
    assert settings.jpv_rrf_weight_expanded == 0.5
    assert settings.jpv_rrf_weight_vector == 0.33
    assert settings.jpv_branch_depth == 60

    swept = build_settings(jpv_rrf_k=10, jpv_rrf_weight_vector=1.0, jpv_branch_depth=5)
    assert (swept.jpv_rrf_k, swept.jpv_rrf_weight_vector, swept.jpv_branch_depth) == (10, 1.0, 5)

    source = (fusion_module.__file__ or "")
    assert source
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "0.33" not in text, "the measured weights are configuration, not code"
    assert "0.5" not in text


def test_vector_branch_weight_defaults_below_lexical() -> None:
    """Measured: branch parity is the WORST fusion, 96/120 against 105/120 at 0,33.

    The cause is structural rather than incidental: the 0,65 distance threshold passes
    1.168 of 1.168 documents on an ordinary query, so the vector branch returns a full list
    whether or not it understood the query — and a branch that always fills its list always
    votes at full strength. Raising this weight "for symmetry" sinks `dije de plata` from
    10/10 to 2/10 and `gargantilla dorada` from 10 to 5.
    """
    settings = build_settings()

    assert settings.jpv_rrf_weight_vector < settings.jpv_rrf_weight_typed
    assert settings.jpv_rrf_weight_vector < settings.jpv_rrf_weight_expanded
    assert FUSION_DEFAULTS["jpv_rrf_weight_vector"] < FUSION_DEFAULTS["jpv_rrf_weight_typed"]
    assert FUSION_DEFAULTS["jpv_rrf_weight_vector"] < FUSION_DEFAULTS["jpv_rrf_weight_expanded"]


def test_the_two_lexical_weights_sum_to_one_lexical_list() -> None:
    typed = FUSION_DEFAULTS["jpv_rrf_weight_typed"]
    expanded = FUSION_DEFAULTS["jpv_rrf_weight_expanded"]

    assert typed + expanded == pytest.approx(1.0)


def test_branch_depth_is_of_the_same_order_as_the_smoothing_constant() -> None:
    depth = FUSION_DEFAULTS["jpv_branch_depth"]
    k = FUSION_DEFAULTS["jpv_rrf_k"]

    assert 0.5 * k <= depth <= 2 * k


def test_disabled_expansion_degrades_to_single_lexical_vote() -> None:
    """A ≡ B, so 0,5/(k+r) + 0,5/(k+r) = 1/(k+r): exactly one list at full weight."""
    keys = ("a", "b", "c", "d")
    identical = fuse(
        [_list("typed", 0.5, *keys), _list("expanded", 0.5, *keys)],
        k=K,
        depth=DEFAULT_BRANCH_DEPTH,
    )
    single = fuse([_list("lexical", 1.0, *keys)], k=K, depth=DEFAULT_BRANCH_DEPTH)

    assert [item.key for item in identical] == [item.key for item in single]
    for fused_item, single_item in zip(identical, single, strict=True):
        assert fused_item.score == pytest.approx(single_item.score)
    assert normalised_scores(identical) == pytest.approx(normalised_scores(single))


def test_normalised_scores_start_at_one_and_never_increase() -> None:
    fused = fuse(
        [_list("a", 1.0, "x", "y", "z"), _list("b", 0.33, "y", "z")],
        k=K,
        depth=DEFAULT_BRANCH_DEPTH,
    )
    scores = normalised_scores(fused)

    assert scores[0] == 1.0
    assert all(0.0 <= score <= 1.0 for score in scores)
    assert list(scores) == sorted(scores, reverse=True)
    assert normalised_scores(()) == ()
