"""The sweep's sample and its arithmetic, offline. C30b.

The sweep itself calls a provider and is a dated measurement, so what a test can hold is the
part that must stay true between runs: that the declared sample is the sample, that its arms
name sections the corpus really has, and that the summary partitions by cause instead of
publishing an aggregate that cannot be read.
"""

from __future__ import annotations

from uuid import UUID

from jbg_ai.assist.constants import (
    CAUSE_CLAIM_NOT_IN_PITCH,
    CAUSE_CURRENCY_ADJACENT,
    CAUSE_FIGURE_NOT_IN_CONTEXT,
    DEFAULT_PITCH_SECTIONS,
    PROMPT_VERSION,
)
from jbg_ai.assist.knowledge_scope import canonical_material_sheets
from jbg_ai.evals.assist_sweep import (
    SWEEP_TIMEOUT_SECONDS,
    _punctuation_only,
    load_sample,
    summarise,
)
from jbg_ai.knowledge.corpus import load_corpus
from support.paths import AI_SERVICE_ROOT


def _sample() -> dict:
    return load_sample()


def test_the_sweep_sample_is_declared_and_not_derived_at_run_time() -> None:
    """A sample that is recalculated is a sample that can move between two arms, and two arms
    measured over different pieces are not an ablation of anything."""
    sample = _sample()

    products = [
        item for stratum in sample["strata"].values() for item in stratum["products"]
    ]
    assert len(products) == 40
    assert len({item["product_id"] for item in products}) == 40
    for item in products:
        UUID(item["product_id"])  # every identifier is a real one, not a placeholder
    # **The version this sample was MEASURED against, and not the one the code runs today.**
    # C31 moved `PROMPT_VERSION` to `assist/v2`, and rewriting this line to follow it would
    # have falsified the provenance of 120 generations already published — which is the exact
    # failure D10 exists to prevent, arriving from the direction nobody had written down. A
    # re-run stamps its own `prompt_version` into the provenance block it prints; this field
    # says which text the figures in the C30b report came from, and it is frozen.
    assert sample["prompt_version"] == "assist/v1"
    assert (AI_SERVICE_ROOT / "prompts" / f"{sample['prompt_version']}.md").is_file()
    assert PROMPT_VERSION != sample["prompt_version"]


def test_the_sample_is_stratified_by_declared_materials_and_says_why() -> None:
    """Not proportional, and the measurement that justifies it travels with it: pieces of two
    or more materials are 7,8 % of the index and are the only ones that pull in the mixed-piece
    section, which is where the cross-attribution risk lives."""
    sample = _sample()
    counts = sample["index"]["by_declared_materials"]

    assert set(sample["strata"]) == {"un-material", "dos-o-mas-materiales"}
    assert len(sample["strata"]["un-material"]["products"]) == 20
    assert len(sample["strata"]["dos-o-mas-materiales"]["products"]) == 20
    # The stratum the sweep exists to see is a small minority of the population.
    assert (counts[2] + counts[3]) / sum(counts.values()) < 0.10
    assert 0 not in {stratum.get("declared_materials") for stratum in sample["strata"].values()}


def test_every_swept_section_exists_and_is_general_in_all_nine_material_sheets() -> None:
    """The condition C30a imposed on the two sections it ships, applied to the third the sweep
    adds: a section that only some sheets carry would make the widest arm mean different things
    for different pieces."""
    corpus = load_corpus()
    sheets = set(canonical_material_sheets())
    by_slug = {
        document.slug: {section.slug: section.claim_scope for section in document.sections}
        for document in corpus.documents
    }

    for arm in _sample()["arms"]:
        for section in arm["section_slugs"]:
            for sheet in sheets:
                assert section in by_slug[sheet], (sheet, section)
                assert by_slug[sheet][section] == "general", (sheet, section)


def test_the_served_configuration_is_one_of_the_arms() -> None:
    """The middle arm is literally what the service ships, so the sweep measures the shipped
    value against its neighbours rather than three configurations none of which is live."""
    arms = {arm["sections"]: tuple(arm["section_slugs"]) for arm in _sample()["arms"]}

    assert arms[2] == tuple(DEFAULT_PITCH_SECTIONS)
    assert arms[1] == tuple(DEFAULT_PITCH_SECTIONS[:1])
    assert arms[3][:2] == tuple(DEFAULT_PITCH_SECTIONS)


def test_the_sweep_does_not_measure_through_the_serving_timeout() -> None:
    """Measuring the gate through a three-second cut would produce no measurement of the gate.
    The sweep records latency and reports the cut separately, which answers both questions."""
    from jbg_ai.assist.constants import PITCH_TIMEOUT_SECONDS

    assert SWEEP_TIMEOUT_SECONDS > PITCH_TIMEOUT_SECONDS


def _row(**overrides) -> dict:
    values = {
        "stratum": "un-material",
        "sections": 2,
        "section_slugs": ["a", "b"],
        "product_id": "x",
        "sku": "SKU1",
        "declared_materials": ["plata"],
        "citations_offered": ["d#s"],
        "provider_calls": 1,
        "prompt_tokens": 1500,
        "completion_tokens": 300,
        "total_tokens": 1800,
        "elapsed_ms": 1200.0,
        "call_latencies_ms": [1200.0],
        "calls_over_serving_timeout": 0,
        "provider_error": None,
        "initial_causes": [],
        "initial_figures": [],
        "surviving_causes": [],
        "correspondence_failures": [],
        "published": True,
        "published_citation_ids": ["d#s"],
        "withdrawn_citation_ids": [],
        "pitch_chars": 220,
        "pitch_sentences": 4,
        "generation": {"pitch": "x", "used": []},
        "initial_generation": {"pitch": "x", "used": []},
    }
    values.update(overrides)
    return values


def test_the_summary_partitions_the_rejection_rate_by_cause() -> None:
    """The reading that matters. An aggregate cannot tell a gate that works from a gate that
    gets in the way, so no aggregate is published without its partition."""
    rows = [
        _row(),
        _row(initial_causes=[CAUSE_FIGURE_NOT_IN_CONTEXT], published=False, provider_calls=2),
        _row(initial_causes=[CAUSE_CURRENCY_ADJACENT], published=False, provider_calls=2),
    ]

    summary = summarise(rows)["2-secciones"]

    assert summary["generations"] == 3
    assert summary["first_pass_rejected"] == 2
    assert summary["first_pass_rejection_rate"] == round(2 / 3, 4)
    assert summary["violations_by_cause"] == {
        CAUSE_FIGURE_NOT_IN_CONTEXT: 1,
        CAUSE_CURRENCY_ADJACENT: 1,
    }
    assert summary["repaired"] == 2
    assert summary["withheld"] == 2


def test_the_summary_separates_each_arm() -> None:
    summary = summarise([_row(sections=1), _row(sections=2), _row(sections=2)])

    assert set(summary) == {"1-secciones", "2-secciones"}
    assert summary["1-secciones"]["generations"] == 1
    assert summary["2-secciones"]["generations"] == 2


def test_the_timeout_is_measured_per_call_and_never_per_request() -> None:
    """The bug this metric had on its first pass, pinned so it cannot come back.

    The timeout applies to **one provider call**. A repaired request makes two, so comparing its
    total wall time against a one-call limit counts every repair as a cut — which is how a five
    per cent rate reads as seventy.
    """
    repaired = _row(
        provider_calls=2,
        elapsed_ms=4400.0,  # over the limit as a REQUEST
        call_latencies_ms=[2200.0, 2200.0],  # and under it in both CALLS
        calls_over_serving_timeout=0,
    )

    summary = summarise([_row(), repaired])["2-secciones"]

    assert summary["request_ms_max"] == 4400.0
    assert summary["calls_measured"] == 3
    assert summary["calls_over_serving_timeout"] == 0


def test_the_summary_counts_the_calls_the_serving_timeout_would_have_cut() -> None:
    """Reported and not applied: it is the figure that would justify moving the timeout, and
    this project does not move a threshold without one in front of it."""
    rows = [_row(), _row(call_latencies_ms=[8000.0], calls_over_serving_timeout=1)]

    summary = summarise(rows)["2-secciones"]

    assert summary["calls_over_serving_timeout"] == 1
    assert summary["call_ms_max"] == 8000.0


def test_correspondence_failures_are_classified_as_punctuation_or_not() -> None:
    """The one question the sweep has to answer about the correspondence check, with its
    threshold declared in advance at more than one failure in ten."""
    rows = [
        _row(
            initial_causes=[CAUSE_CLAIM_NOT_IN_PITCH],
            correspondence_failures=[{"citation_id": "d#s", "punctuation_only": True}],
        ),
        _row(
            initial_causes=[CAUSE_CLAIM_NOT_IN_PITCH],
            correspondence_failures=[{"citation_id": "d#t", "punctuation_only": False}],
        ),
    ]

    summary = summarise(rows)["2-secciones"]

    assert summary["correspondence_failures"] == 2
    assert summary["correspondence_failures_punctuation_only"] == 1


def test_the_punctuation_classifier_does_not_soften_the_check_itself() -> None:
    """It answers "would folding have saved this", and the check stays exactly as strict."""
    assert _punctuation_only("el oro, de ley", "El oro de ley envejece bien")
    assert not _punctuation_only("resiste el cloro", "El oro de ley envejece bien")
    assert not _punctuation_only("", "El oro de ley")
