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


def test_flat_fusion_mode_reproduces_the_published_baseline() -> None:
    """The flat mode is bit-identical to C21's single fusion over the three lists.

    This is the offline half of the guarantee: the flat path composes nothing, so the order
    it produces is the one the published baseline was measured under. The other half is the
    live half — `v2-hibrido.yaml` pins `fusion: flat` and reproduces 0,603 / 0,942 / 0,535
    against golden set `1:93a94fa8fbc3`, recorded in the C25 implementation report.

    If this fails, the table has lost the row every other row is read against.
    """
    from uuid import UUID

    from jbg_ai.retrieval.orchestrator import _fuse_branches

    typed = [UUID(f"00000000-0000-0000-0000-{i:012d}") for i in range(1, 31)]
    expanded = [UUID(f"00000000-0000-0000-0000-{i:012d}") for i in range(5, 45)]
    vector = [UUID(f"22222222-0000-0000-0000-{i:012d}") for i in range(1, 61)]

    c21_weights = (
        FUSION_DEFAULTS["jpv_rrf_weight_typed"],
        FUSION_DEFAULTS["jpv_rrf_weight_expanded"],
        FUSION_DEFAULTS["jpv_rrf_weight_vector"],
    )
    expected = fuse(
        [
            RankedList("typed", c21_weights[0], typed),
            RankedList("expanded", c21_weights[1], expanded),
            RankedList("vector", c21_weights[2], vector),
        ],
        k=FUSION_DEFAULTS["jpv_rrf_k"],
        depth=FUSION_DEFAULTS["jpv_branch_depth"],
    )

    hits = {key: _FakeHit(key) for key in (*typed, *expanded, *vector)}
    ordered, _ = _fuse_branches(
        [hits[key] for key in typed],
        [hits[key] for key in expanded],
        [hits[key] for key in vector],
        k=FUSION_DEFAULTS["jpv_rrf_k"],
        depth=FUSION_DEFAULTS["jpv_branch_depth"],
        mode="flat",
        flat_weights=c21_weights,
        branch_weights=(0.5, 0.5),
        internal_weights=(0.5, 0.5),
    )

    assert [item.product_id for item in ordered] == [item.key for item in expected]


class _FakeHit:
    """The minimum a hit needs to be rebuilt into a candidate by the orchestrator."""

    def __init__(self, product_id) -> None:
        self.product_id = product_id
        self.sku = str(product_id)[:8]
        self.materials: list[str] = []
        self.family_id = None
        self.variant_label = None
        self.price = None
        self.size_label = None
        self.qty_bucket = None
        self.sales_30d = None
        self.ts_rank = 0.5
        self.coordination = 1
        self.distance = 0.3
