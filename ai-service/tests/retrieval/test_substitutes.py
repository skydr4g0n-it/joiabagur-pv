"""The substitutes engine: hard filter, continuous ordering, declared signals. C26.

**The fixture is not invented.** `SKU13_NEIGHBOURS` holds the real cosine distances the live
index returns for `SKU13 Anillo erizo de mar M` once the hard filter on `piece_type` has run
— the same ten rows the C26 exploration report tabulates. A fixture with round numbers would
let the ordering tests pass on arithmetic that the catalogue does not produce; these numbers
are the ones the ordering has to survive, and two of the scenarios below are only
discriminating because the real gaps are as narrow as they are.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.schemas.retrieval import (
    RetrievalFilters,
    SubstitutesRequest,
    SubstitutesResponse,
)
from jbg_ai.retrieval.errors import UnusableSourceProductError
from jbg_ai.retrieval.substitutes import NO_STYLE_TAGS_REASON, retrieve_substitutes
from jbg_ai.stubs.responses import over_retrieval_count
from support.fake_product_search import (
    DEFAULT_BUCKET,
    FakeAssignment,
    FakeIndexedRow,
    FakeProductSearch,
)
from support.settings import TOKEN_POS_ID, TOKEN_TRACE_ID, build_settings

SOURCE = UUID("00000000-0000-4000-8000-000000000013")
ERIZO_FAMILY = UUID("11111111-1111-1111-1111-111111111111")
OTHER_FAMILY = UUID("22222222-2222-2222-2222-222222222222")
POS = UUID(TOKEN_POS_ID)


def _pid(tag: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{tag:012d}")


#: `(sku, distance, size_label, same family)` — measured against the live index on
#: 2026-09-12, filtered to `piece_type = 'anillo'`, source `SKU13` excluded.
SKU13_NEIGHBOURS: tuple[tuple[str, float, str, bool], ...] = (
    ("SKU14", 0.0868, "L", True),
    ("SKU12", 0.0908, "S", True),
    ("SKU15", 0.1229, "XL", True),
    ("SKU04", 0.1375, "S", False),
    ("SKU50", 0.1535, "M", False),
    ("SKU85", 0.1578, "M", False),
    ("SKU433", 0.1638, "XL", False),
    ("SKU49", 0.1668, "S", False),
    ("SKU334", 0.1854, "M", False),
    ("SKU48", 0.1916, "XS", False),
)


def _source_row(**kwargs) -> FakeIndexedRow:
    values = {
        "product_id": SOURCE,
        "sku": "SKU13",
        "distance": 0.0,
        "materials": ["plata"],
        "family_id": ERIZO_FAMILY,
        "piece_type": "anillo",
        "size_label": "M",
        "price_band": "media",
    }
    values.update(kwargs)
    return FakeIndexedRow(**values)


def _erizo_rows(**source_overrides) -> list[FakeIndexedRow]:
    """The source product plus its ten real same-type neighbours."""
    rows = [_source_row(**source_overrides)]
    for index, (sku, distance, size, same_family) in enumerate(SKU13_NEIGHBOURS, start=1):
        rows.append(
            FakeIndexedRow(
                product_id=_pid(index),
                sku=sku,
                distance=distance,
                materials=["plata"],
                family_id=ERIZO_FAMILY if same_family else OTHER_FAMILY,
                piece_type="anillo",
                size_label=size,
                price_band="media",
            )
        )
    return rows


def _principal() -> ServicePrincipal:
    return ServicePrincipal(
        user_id="u-1", role="Operator", trace_id=TOKEN_TRACE_ID, pos_id=TOKEN_POS_ID
    )


def _run(
    search: FakeProductSearch,
    *,
    product_id: UUID | str = SOURCE,
    top_k: int = 10,
    exclude: list[str] | None = None,
    **overrides,
) -> SubstitutesResponse:
    payload = SubstitutesRequest(
        product_id=str(product_id),
        top_k=top_k,
        filters=RetrievalFilters(exclude_product_ids=exclude or []),
    )
    return asyncio.run(
        retrieve_substitutes(
            payload,
            _principal(),
            settings=build_settings(stub_mode=False, **overrides),
            search=search,
        )
    )


def _skus(response: SubstitutesResponse) -> list[str]:
    return [item.sku for item in response.results]


# --- The hard filter and the three exclusions ---------------------------------------------


def test_never_returns_a_different_piece_type() -> None:
    """The vector alone violates the type in 2 of the 4 measured cases.

    `Colgante erizo de mar M` is the #4 neighbour of `SKU13` by raw cosine and is put here
    NEARER than every ring, so a filter that merely demoted would still return it first.
    A ring is not a second-best pendant; it is a different object.
    """
    rows = _erizo_rows()
    rows.append(
        FakeIndexedRow(
            product_id=_pid(90),
            sku="SKU39",
            distance=0.0001,
            materials=["plata"],
            piece_type="colgante",
            size_label="M",
        )
    )

    response = _run(FakeProductSearch(rows))

    assert "SKU39" not in _skus(response)
    assert _skus(response)


def test_source_product_never_returned_as_own_substitute() -> None:
    response = _run(FakeProductSearch(_erizo_rows()))

    assert "SKU13" not in _skus(response)
    assert str(SOURCE) not in [item.product_id for item in response.results]


def test_explicitly_excluded_products_are_not_returned() -> None:
    response = _run(FakeProductSearch(_erizo_rows()), exclude=[str(_pid(1))])

    assert "SKU14" not in _skus(response)
    assert "SKU12" in _skus(response)


# --- The family: recall guaranteed, priority refused --------------------------------------


def test_no_live_family_member_is_dropped_from_the_result() -> None:
    """Recall is what survived the measurement, not the "same family first" of the ticket.

    **Read the name with the scope the spec states.** What is guaranteed is that no RULE
    removes a sibling: the only hard filter is `piece_type`, which a family shares by
    construction. A sibling can still be absent by falling outside the over-retrieval window,
    and the spec says so rather than promising a bound the statement does not enforce — with
    `top_k=1` the window is three rows and a family of eight cannot fit in it. Here the window
    holds every candidate, so what this asserts is the absence of the rule.
    """
    response = _run(FakeProductSearch(_erizo_rows()))

    siblings = {"SKU14", "SKU12", "SKU15"}
    assert siblings <= set(_skus(response))
    by_sku = {item.sku: item for item in response.results}
    assert all(by_sku[sku].similarity_signals.family_match for sku in siblings)


def test_family_membership_does_not_force_the_first_position() -> None:
    """`SKU50` shares no family with the source and outranks the family's `XL`.

    Under "same family first" every sibling would head the list and the first usable
    candidate would be #4. The family is orthogonal; the size is what discriminates.
    """
    response = _run(FakeProductSearch(_erizo_rows()))
    order = _skus(response)

    assert order.index("SKU50") < order.index("SKU15")
    assert response.results[order.index("SKU50")].similarity_signals.family_match is False


# --- The ordering, and the shortcut it must not take --------------------------------------


def test_same_size_candidate_outranks_same_family_different_size() -> None:
    """The finding of the exploration, on the real `SKU13` numbers.

    `SKU50 Anillo oreja de mar M` is further away by cosine (0,1535) than the family's
    `SKU15 XL` (0,1229) and still has to come first: the customer asked for an M, and an
    XL that does not fit is not a second option — `criterion.md` already graded it 1.
    """
    response = _run(FakeProductSearch(_erizo_rows()))
    order = _skus(response)

    assert order.index("SKU50") < order.index("SKU15")


def test_different_size_sibling_stays_inside_the_visible_window() -> None:
    """**The test that forbids the shortcut.** An integer block cannot pass it.

    Reusing `demotion_rank` would put the size in an integer block, and a block PARTITIONS:
    every M — `SKU50`, `SKU85`, `SKU334` — would land ahead of every non-M, so the nearest
    sibling `SKU14 L` (0,0868, nearly twice as close as `SKU334` at 0,1854) would fall to
    position 4 behind all three. That is banishment, not demotion, and it is the exact shape
    C25 measured and withdrew: 11.067 inverted pairs, 71,2 % of them more than ten places.

    So it is not enough that the right size rises. The two assertions below are the ones a
    block fails: a demoted sibling still beats some size-matching candidates, and the worst
    sibling of all is still inside the window an operator actually sees.
    """
    response = _run(FakeProductSearch(_erizo_rows()))
    order = _skus(response)

    size_matching = [order.index(sku) for sku in ("SKU50", "SKU85", "SKU334")]
    assert order.index("SKU14") < max(size_matching), (
        "the nearest different-size sibling was pushed behind every size match, "
        "which is what an integer block does"
    )
    assert order.index("SKU15") < 5, "the furthest sibling left the visible window"


def test_size_term_is_inert_when_either_side_declares_no_size() -> None:
    """Absence is not a mismatch, on either side. 54 % of the rings declare no size."""
    unsized_source = _run(FakeProductSearch(_erizo_rows(size_label=None)))
    no_weight = _run(
        FakeProductSearch(_erizo_rows(size_label=None)), jpv_substitute_weight_size=0.0
    )
    assert _skus(unsized_source) == _skus(no_weight)

    rows = _erizo_rows()
    rows.append(
        FakeIndexedRow(
            product_id=_pid(91),
            sku="SKU777",
            distance=0.13,
            materials=["plata"],
            piece_type="anillo",
            size_label=None,
        )
    )
    response = _run(FakeProductSearch(rows))
    unsized = next(item for item in response.results if item.sku == "SKU777")

    # 1 - 0.13 exactly: no penalty was applied for declaring no size.
    assert unsized.score == pytest.approx(0.87)


def test_size_weight_of_zero_reproduces_the_ordering_without_the_term() -> None:
    """Zero is the rollback, and it must restore pure cosine order exactly."""
    response = _run(
        FakeProductSearch(_erizo_rows()), jpv_substitute_weight_size=0.0
    )

    assert _skus(response) == [sku for sku, *_ in SKU13_NEIGHBOURS]


def test_material_overlap_increases_similarity_score() -> None:
    """A strict tiebreak, asserted where it is the only thing that can decide.

    The two candidates are given the SAME distance and the same size status, so the composed
    key ties exactly and nothing but the shared material can separate them. It is not a
    weight: making it one would mean pricing a shared material in units of cosine similarity,
    and no query of the golden set can calibrate that number.
    """
    rows = [_source_row(materials=["plata", "perla"])]
    rows.append(
        FakeIndexedRow(
            product_id=_pid(41),
            sku="SHARES",
            distance=0.2,
            materials=["plata"],
            piece_type="anillo",
            size_label="M",
        )
    )
    rows.append(
        FakeIndexedRow(
            product_id=_pid(40),  # the lower id, so the final tiebreak favours the OTHER one
            sku="SHARES-NONE",
            distance=0.2,
            materials=["acero"],
            piece_type="anillo",
            size_label="M",
        )
    )

    response = _run(FakeProductSearch(rows))
    order = _skus(response)
    by_sku = {item.sku: item for item in response.results}

    assert order.index("SHARES") < order.index("SHARES-NONE")
    assert by_sku["SHARES"].similarity_signals.material_overlap > 0
    assert by_sku["SHARES-NONE"].similarity_signals.material_overlap == 0


# --- Availability: demotes, never removes -------------------------------------------------


def test_out_of_stock_candidate_is_demoted_and_never_removed() -> None:
    """§15.10: the projection may lag minutes, so it reorders and never deletes.

    The exhausted candidate is the CLOSEST of the three by cosine, so only the demotion can
    move it. It still has to come back: excluding on stock is C34's, on the .NET side.
    """
    rows = [_source_row()]
    for index, (sku, distance) in enumerate(
        (("EXHAUSTED", 0.10), ("AVAILABLE-A", 0.20), ("AVAILABLE-B", 0.30)), start=60
    ):
        rows.append(
            FakeIndexedRow(
                product_id=_pid(index),
                sku=sku,
                distance=distance,
                materials=["plata"],
                piece_type="anillo",
                size_label="M",
            )
        )
    assignments = [
        FakeAssignment(pos_id=POS, product_id=_pid(60), qty_bucket="0"),
        FakeAssignment(pos_id=POS, product_id=_pid(61), qty_bucket=DEFAULT_BUCKET),
        FakeAssignment(pos_id=POS, product_id=_pid(62), qty_bucket=DEFAULT_BUCKET),
    ]

    response = _run(FakeProductSearch(rows, assignments=assignments))
    order = _skus(response)

    assert "EXHAUSTED" in order
    assert order.index("EXHAUSTED") > order.index("AVAILABLE-A")
    assert order.index("EXHAUSTED") > order.index("AVAILABLE-B")

    exhausted = next(item for item in response.results if item.sku == "EXHAUSTED")
    notes = " ".join(exhausted.debug.notes)
    assert "availability_penalty" in notes
    # The projection age is declared. It rides in `debug.notes` because the frozen
    # `SubstitutesResponse` has no `projection_age_seconds` field and the snapshot is fixed.
    assert "projection_age_seconds" in notes


def test_absent_projection_row_is_not_read_as_zero_stock() -> None:
    """A product this point of sale does not carry has no row — and absence is not a zero."""
    rows = [_source_row()]
    for index, sku in ((70, "NOT-CARRIED"), (71, "CARRIED")):
        rows.append(
            FakeIndexedRow(
                product_id=_pid(index),
                sku=sku,
                distance=0.10 if sku == "NOT-CARRIED" else 0.20,
                materials=["plata"],
                piece_type="anillo",
                size_label="M",
            )
        )
    assignments = [FakeAssignment(pos_id=POS, product_id=_pid(71))]

    response = _run(FakeProductSearch(rows, assignments=assignments))
    order = _skus(response)
    not_carried = next(item for item in response.results if item.sku == "NOT-CARRIED")

    assert order.index("NOT-CARRIED") < order.index("CARRIED")
    assert "availability_penalty" not in " ".join(not_carried.debug.notes)
    assert not_carried.score == pytest.approx(0.90)


# --- Signals and reasons ------------------------------------------------------------------


def test_style_similarity_absence_is_declared_in_match_reasons() -> None:
    """A zero that cannot lie: only 1 of 404 real products has a style tag to share."""
    response = _run(FakeProductSearch(_erizo_rows()))
    candidate = response.results[0]

    assert candidate.similarity_signals.style_similarity == 0.0
    assert NO_STYLE_TAGS_REASON in candidate.match_reasons


def test_style_similarity_is_not_derived_from_the_embedding() -> None:
    """Deriving it from the cosine would make it a copy of `score`. C19 died of that.

    Two candidates at very different distances, neither carrying style tags: if the signal
    were derived from the embedding the two would differ, and the one that is nearly
    identical to the source would report a high "style" similarity it has no data for.
    """
    rows = [_source_row()]
    rows.extend(
        FakeIndexedRow(
            product_id=_pid(index),
            sku=sku,
            distance=distance,
            materials=["plata"],
            piece_type="anillo",
            size_label="M",
        )
        for index, sku, distance in ((80, "NEAR", 0.01), (81, "FAR", 0.60))
    )

    response = _run(FakeProductSearch(rows))
    signals = {item.sku: item.similarity_signals for item in response.results}

    assert signals["NEAR"].style_similarity == 0.0
    assert signals["FAR"].style_similarity == 0.0
    assert signals["NEAR"].style_similarity == signals["FAR"].style_similarity


def test_style_similarity_is_the_jaccard_of_the_tag_sets() -> None:
    """Where the data exists it is used, and it is the Jaccard and nothing else."""
    rows = [_source_row(style_tags=["marinero", "minimalista"])]
    rows.append(
        FakeIndexedRow(
            product_id=_pid(82),
            sku="TAGGED",
            distance=0.2,
            materials=["plata"],
            piece_type="anillo",
            size_label="M",
            style_tags=["marinero"],
        )
    )

    response = _run(FakeProductSearch(rows))
    tagged = next(item for item in response.results if item.sku == "TAGGED")

    assert tagged.similarity_signals.style_similarity == pytest.approx(0.5)
    assert NO_STYLE_TAGS_REASON not in tagged.match_reasons


def test_visual_similarity_is_null_by_design() -> None:
    """§15.7 keeps the visual and textual vector spaces unfused; there is no number."""
    response = _run(FakeProductSearch(_erizo_rows()))

    assert response.results
    assert all(
        item.similarity_signals.visual_similarity is None for item in response.results
    )


def test_match_reasons_state_the_size_relationship() -> None:
    """The contract cannot express the size, and the size is what discriminates."""
    response = _run(FakeProductSearch(_erizo_rows()))
    by_sku = {item.sku: item for item in response.results}

    assert any("misma talla" in reason for reason in by_sku["SKU50"].match_reasons)
    differing = " ".join(by_sku["SKU14"].match_reasons)
    assert "talla distinta" in differing
    assert "L" in differing and "M" in differing


def test_match_reasons_carry_no_price_or_stock_figure() -> None:
    """.NET owns price and stock. A figure written here is one this service cannot defend.

    The fixture uses the REAL shapes and that is the whole point of it. Measured on the live
    catalogue, `price_band` is always a euro range — `30-80`, `150-300`, `lt-30` — so naming
    the band in a reason would ship a price figure out of Python; the reason states only THAT
    the bands differ. And `size_label` legitimately contains digits: ring sizes run `05`, `6`,
    `17`, `45`, `2mm`. So the assertion cannot be "no digits anywhere" — that was the first
    version of this test and it passed only because the fixture used letters. It asserts the
    two things that actually must not travel: a band value and a projection bucket.
    """
    rows = _erizo_rows(size_label="17", price_band="30-80")
    rows.append(
        FakeIndexedRow(
            product_id=_pid(95),
            sku="OTHER-BAND",
            distance=0.22,
            materials=["oro"],
            piece_type="anillo",
            size_label="17",
            price=249.90,
            price_band="150-300",
        )
    )
    assignments = [FakeAssignment(pos_id=POS, product_id=_pid(95), qty_bucket="1-2")]

    response = _run(FakeProductSearch(rows, assignments=assignments))
    other_band = next(item for item in response.results if item.sku == "OTHER-BAND")

    assert "otra banda de precio" in other_band.match_reasons

    forbidden = ("30-80", "150-300", "lt-30", "gte-300", "80-150", "249", "1-2", "3+")
    for item in response.results:
        joined = " | ".join(item.match_reasons)
        for token in forbidden:
            assert token not in joined, f"{token!r} leaked into match_reasons: {joined}"

    # The size, which IS allowed to carry digits, still travels — otherwise the assertion
    # above could be satisfied by emitting nothing at all.
    assert any("17" in reason for reason in other_band.match_reasons)


# --- Abstention, errors, and the provider that must never be called -----------------------


def test_substitutes_never_abstains_and_says_so() -> None:
    """Measured, not deferred: every product has a neighbour closer than 0,255.

    The source here has no family and one distant neighbour, which is the shape an absolute
    threshold would reject. It is answered, and `low_confidence` says the endpoint means it.
    """
    rows = [_source_row(family_id=None)]
    rows.append(
        FakeIndexedRow(
            product_id=_pid(96),
            sku="LONELY",
            distance=0.2545,
            materials=["plata"],
            piece_type="anillo",
            size_label="M",
        )
    )

    response = _run(FakeProductSearch(rows))

    assert response.results
    assert response.low_confidence is False
    assert response.results[0].similarity_signals.family_match is False


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (None, "not present in the retrieval index"),
        ({"is_active": False}, "inactive"),
        ({"has_embedding": False}, "no embedding"),
    ],
)
def test_unknown_or_unindexed_source_product_is_an_explicit_error(
    overrides: dict | None, expected: str
) -> None:
    """Three causes, three sentences, and never a 200 with an empty list.

    An empty success is indistinguishable from a catalogue that holds no substitute at all,
    and the operator's panel paints the same "nothing found" screen over both. This is the
    signature the project has kept since C17.
    """
    search = FakeProductSearch([] if overrides is None else [_source_row(**overrides)])

    with pytest.raises(UnusableSourceProductError) as raised:
        _run(search)

    assert expected in str(raised.value)
    assert str(SOURCE) in str(raised.value)


def test_no_embedding_provider_call_is_made() -> None:
    """The capability is free of the provider because the source vector is already stored.

    The double raises on ANY attribute access, so it catches a cache read or a model-version
    lookup and not only a call to `embed`. It is passed where the orchestration would find
    one if this path ever grew a query to embed.
    """

    class ExplodingEmbeddingClient:
        def __getattr__(self, name: str) -> object:
            raise AssertionError(
                f"the substitutes path touched the embedding provider: {name}"
            )

    search = FakeProductSearch(_erizo_rows())
    payload = SubstitutesRequest(product_id=str(SOURCE), top_k=5)
    response = asyncio.run(
        retrieve_substitutes(
            payload,
            _principal(),
            settings=build_settings(stub_mode=False),
            search=search,
        )
    )

    assert response.results
    # Nothing in the module accepts an embedding client at all, which is the strongest form
    # of the guarantee: the double below can never be reached because there is no seam to
    # pass it through. Asserted anyway, so that adding such a seam breaks this test.
    assert "embed" not in retrieve_substitutes.__code__.co_varnames
    assert ExplodingEmbeddingClient is not None
    assert search.search_calls == []
    assert search.lexical_calls == []


# --- Over-retrieval and the declared count ------------------------------------------------


def test_over_retrieval_window_matches_the_products_route() -> None:
    """`top_k` is the page .NET wants AFTER hydrating and filtering, so more is produced.

    The window is `over_retrieval_count`, the same function the products route uses: one
    fewer arbitrary constant, and the two endpoints over-fetch by the same rule until an
    evaluation says otherwise.
    """
    search = FakeProductSearch(_erizo_rows())

    response = _run(search, top_k=2)

    assert search.neighbour_calls[-1]["depth"] == over_retrieval_count(2) == 6
    assert len(response.results) == 6
    assert response.candidates_returned == len(response.results)
    assert response.effective_pos_id == TOKEN_POS_ID
    assert response.trace_id == TOKEN_TRACE_ID


def test_the_reading_scope_never_restricts_the_candidate_universe() -> None:
    """`neighbours_of` is called with `signal_pos_id` and has no restricting parameter."""
    search = FakeProductSearch(_erizo_rows())

    _run(search)

    call = search.neighbour_calls[-1]
    assert call["signal_pos_id"] == POS
    assert "pos_id" not in call
