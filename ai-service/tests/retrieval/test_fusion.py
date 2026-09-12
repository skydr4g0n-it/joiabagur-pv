"""Weighted RRF: consensus, symmetric depth and the measured defaults. Delivered by C21."""

from __future__ import annotations

import inspect
import socket

import pytest

from jbg_ai.config.settings import FUSION_DEFAULTS
from jbg_ai.retrieval import fusion as fusion_module
from jbg_ai.retrieval.fusion import (
    RankedList,
    fuse,
    normalised_scores,
    truncate,
)
from support.settings import build_settings

#: Held here and not in `fusion.py`: the module must carry the rule, never the figure.
K = 60
DEPTH = 60


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
        depth=DEPTH,
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
    """Pure by contract: C23 imports it, C25 composes it with itself, C26 is next."""

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
    assert settings.jpv_branch_weight_lexical == 0.5
    assert settings.jpv_branch_weight_vector == 0.5
    assert settings.jpv_branch_depth == 60

    swept = build_settings(jpv_rrf_k=10, jpv_branch_weight_vector=1.0, jpv_branch_depth=5)
    assert (swept.jpv_rrf_k, swept.jpv_branch_weight_vector, swept.jpv_branch_depth) == (
        10,
        1.0,
        5,
    )

    source = (fusion_module.__file__ or "")
    assert source
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "0.33" not in text, "the measured weights are configuration, not code"
    assert "0.5" not in text

    # The smoothing constant and the depth are named by the same requirement as the weights,
    # and a module-level default is how a figure gets written into the code without anybody
    # deciding to: the next importer picks it up silently. Asserted on the signature rather
    # than by scanning for "60", so the measured rationale can stay in the prose.
    signature = inspect.signature(fuse)
    for name in ("k", "depth"):
        assert signature.parameters[name].default is inspect.Parameter.empty, (
            f"`{name}` must have no default in fusion.py: it comes from settings or from the "
            "orchestration call, never from this module"
        )
    assert not hasattr(fusion_module, "DEFAULT_RRF_K")
    assert not hasattr(fusion_module, "DEFAULT_BRANCH_DEPTH")


def test_the_default_branch_ratio_is_one_vote_each() -> None:
    """The pin that replaced "the vector weight is lower". C25bis.

    That earlier default belonged to the per-LIST weights, and it was already declared
    withdrawn when the two-stage composition was adopted: under a graded golden set it made
    the vector branch unable to place a candidate the lexical branch had not also produced.
    The per-list weights are gone, so the pin has to be on what exists — the ratio between the
    two BRANCH weights, whose default is a value of principle: each branch holds one vote.

    Measured as robust rather than merely chosen: with the adaptive coverage rule on, the
    sweep's range over that ratio falls from 0,070 to 0,007 — a cliff turned into a plateau.
    """
    settings = build_settings()

    assert settings.jpv_branch_weight_vector == pytest.approx(
        settings.jpv_branch_weight_lexical
    )
    assert FUSION_DEFAULTS["jpv_branch_weight_vector"] == pytest.approx(
        FUSION_DEFAULTS["jpv_branch_weight_lexical"]
    )


def test_the_internal_lexical_weights_are_equal_and_not_settable() -> None:
    """Equal by requirement, and therefore not configuration at all. C25bis.

    The specification requires the two lists of the lexical branch to carry the same weight and
    forbids sweeping them. A setting could then only ever be moved into violation, with nothing
    to detect it — which is worse than a dead knob, because it looks like a decision. So they
    became one declared constant, and no per-list weight survives in settings.

    The move could not change a result: both lists carry the same value, RRF scales linearly
    with the weight, and stage two receives only the ORDER stage one produced.
    """
    from jbg_ai.retrieval import orchestrator

    assert orchestrator.LEXICAL_INTERNAL_WEIGHT > 0

    settings = build_settings()
    for retired in (
        "jpv_rrf_weight_typed",
        "jpv_rrf_weight_expanded",
        "jpv_rrf_weight_vector",
    ):
        assert not hasattr(settings, retired), f"{retired} must not exist as a setting"
        assert retired not in FUSION_DEFAULTS


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
        depth=DEPTH,
    )
    single = fuse([_list("lexical", 1.0, *keys)], k=K, depth=DEPTH)

    assert [item.key for item in identical] == [item.key for item in single]
    for fused_item, single_item in zip(identical, single, strict=True):
        assert fused_item.score == pytest.approx(single_item.score)
    assert normalised_scores(identical) == pytest.approx(normalised_scores(single))


def test_normalised_scores_start_at_one_and_never_increase() -> None:
    fused = fuse(
        [_list("a", 1.0, "x", "y", "z"), _list("b", 0.33, "y", "z")],
        k=K,
        depth=DEPTH,
    )
    scores = normalised_scores(fused)

    assert scores[0] == 1.0
    assert all(0.0 <= score <= 1.0 for score in scores)
    assert list(scores) == sorted(scores, reverse=True)
    assert normalised_scores(()) == ()


# --------------------------------------------------------------------------------------
# C25 — the fusion is composed in two stages, and the formula is untouched.
# --------------------------------------------------------------------------------------


def test_fuse_composes_with_itself_without_changing_the_formula() -> None:
    """Stage 1's ORDER feeds back in as a ranked list. That is the whole mechanism.

    `fuse` takes identifiers in order and returns identifiers in order, so composing it with
    itself needs no new entry point and no change to `score(d) = sum w_i / (k + rank_i(d))`.
    What the composition loses is declared: only the order survives stage 1, so the magnitude
    of the intra-lexical consensus is flattened.
    """
    typed = _list("typed", 0.5, "a", "b", "c")
    expanded = _list("expanded", 0.5, "b", "a", "d")

    stage_one = fuse([typed, expanded], k=K, depth=DEPTH)
    relayed = RankedList("lexical", 1.0, [item.key for item in stage_one])
    stage_two = fuse([relayed], k=K, depth=DEPTH)

    # A single list fused alone is order-preserving, so stage 2 hands back stage 1's order.
    assert [item.key for item in stage_two] == [item.key for item in stage_one]
    # And the relayed list carries ONE name, so provenance collapses to the branch.
    assert all(item.ranks == {"lexical": position} for position, item in enumerate(stage_two, 1))


def test_a_branch_relayed_as_one_list_votes_once_however_many_lists_composed_it() -> None:
    """Two lists agreeing and one list alone relay the same total vote. C25 D5(a)."""
    agreeing = fuse(
        [_list("typed", 0.5, "x", "y"), _list("expanded", 0.5, "x", "y")], k=K, depth=DEPTH
    )
    alone = fuse([_list("expanded", 0.5, "x", "y")], k=K, depth=DEPTH)

    for stage_one in (agreeing, alone):
        relayed = fuse(
            [
                RankedList("lexical", 0.5, [item.key for item in stage_one]),
                RankedList("vector", 0.5, ["v"]),
            ],
            k=K,
            depth=DEPTH,
        )
        by_key = {item.key: item.score for item in relayed}
        # The branch's leader scores exactly w_lex / (k + 1) in both regimes: the crossover
        # is no longer 0,469 or 0,938 depending on whether the typed list happened to match.
        assert by_key["x"] == pytest.approx(0.5 / (K + 1))
        assert by_key["v"] == pytest.approx(0.5 / (K + 1))


# --------------------------------------------------------------------------------------
# The fossil: why the single-stage fusion was retired, kept executable and unreachable.
#
# These are the weights C21 shipped, written here as LOCAL LITERALS and deliberately not read
# from `FUSION_DEFAULTS` — they no longer live there, and that is the point. A number in a
# settings module is a configuration somebody can set; the same number in a test is a record of
# what was measured. The path that consumed them is gone, `fuse()` is pure and domain-free, and
# nothing selects this arithmetic: it can be read, and it cannot be switched on.
RETIRED_W_TYPED = 0.5
RETIRED_W_EXPANDED = 0.5
RETIRED_W_VECTOR = 0.33


def test_the_flat_arithmetic_that_was_retired_buried_the_vector_leader() -> None:
    """Why one composition exists and not two. C25bis D-F, over `fuse()` alone.

    The single-stage fusion over all three lists did not fuse: it concatenated. The defect was
    an ARITY, not a weighting choice — the lexical branch fielded two lists against the vector
    branch's one, so its combined vote ran to 1,00 against 0,33 and its documents occupied
    twice as many slots.

    The consequence, measured on the published run: a grade-2 document the vector branch ranked
    FIRST landed at position 33 in three separate queries of the golden set, and the 32 ahead
    of it were lexical-only while the tail preserved the vector order exactly.
    """
    lexical_ids = [f"lex-{i:03d}" for i in range(1, 33)]
    vector_leader = "vector-top-hit"

    fused = fuse(
        [
            RankedList("typed", RETIRED_W_TYPED, lexical_ids),
            RankedList("expanded", RETIRED_W_EXPANDED, lexical_ids),
            RankedList("vector", RETIRED_W_VECTOR, [vector_leader, *lexical_ids]),
        ],
        k=K,
        depth=DEPTH,
    )
    order = [item.key for item in fused]

    assert order.index(vector_leader) == 32, (
        "the vector branch's best candidate lands at position 33, behind every lexical "
        f"document: {order[:5]}"
    )

    # And the arithmetic that forces it, stated as the two numbers that cannot cross. The worst
    # possible lexical document — last of a full list, in BOTH lexical lists — still outscores
    # the vector branch's first.
    worst_lexical = RETIRED_W_TYPED / (K + DEPTH) + RETIRED_W_EXPANDED / (K + DEPTH)
    best_vector = RETIRED_W_VECTOR / (K + 1)

    assert worst_lexical == pytest.approx(0.008333, abs=1e-6)
    assert best_vector == pytest.approx(0.005410, abs=1e-6)
    assert worst_lexical > best_vector, (
        "with the retired per-list weights the whole lexical list outranks the vector "
        "branch's leader in EVERY query — which is what made it a defect and not a setting"
    )


def test_no_flat_fusion_path_exists() -> None:
    """The retired composition must not come back through a configuration. C25bis."""
    import inspect

    from jbg_ai.config import settings as settings_module
    from jbg_ai.retrieval import orchestrator

    source = inspect.getsource(orchestrator)
    assert "FUSION_MODE" not in source
    assert "flat_weights" not in source

    for gone in ("FUSION_MODES", "FUSION_MODE_FLAT", "FUSION_MODE_BRANCH"):
        assert not hasattr(settings_module, gone), f"{gone} must not exist"

    signature = inspect.signature(orchestrator.retrieve_products)
    for gone in ("fusion", "weight_typed", "weight_expanded", "weight_vector"):
        assert gone not in signature.parameters, f"`{gone}` must not be an orchestration knob"

    # The second half of the scenario, asserted in the same test so that the requirement maps
    # to one place: no per-list weight is defined anywhere a configuration could reach.
    from jbg_ai.evals.configs import EvalConfig

    for gone in ("jpv_rrf_weight_typed", "jpv_rrf_weight_expanded", "jpv_rrf_weight_vector"):
        assert gone not in FUSION_DEFAULTS
        assert not hasattr(build_settings(), gone)
    for gone in ("weight_typed", "weight_expanded", "weight_vector", "fusion"):
        assert gone not in EvalConfig.__dataclass_fields__, (
            f"`{gone}` must not be an evaluation configuration key"
        )
