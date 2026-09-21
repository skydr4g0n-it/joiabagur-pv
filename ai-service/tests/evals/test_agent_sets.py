"""The two measurement instruments of the agent loop, and the wall between them. C32b.

Offline and free: nothing here calls a provider, opens a socket or reads a database. That is
what lets the instruments be checked **before** the pass that costs money runs against them —
a calibration set discovered to be malformed halfway through a paid run is a paid run thrown
away.

The test this module exists for is `test_no_transcript_of_either_agent_set_reuses_a_golden_
query`. HU-AIENG-032b escenario 14 ends with «el golden set de C24 **no se ha usado** para
calibrar ni para iterar ningún prompt», and a sentence in a report is not evidence of that.
This walks it in both directions.
"""

from __future__ import annotations

import json
import re
import unicodedata

import yaml

from jbg_ai.assist.constants import (
    AVAILABILITY_LABELS,
    MAX_TRANSCRIPT_CHARS,
    MAX_TRANSCRIPT_TURNS,
    MAX_TURN_CHARS,
    TOOL_NAMES,
    TURN_ROLE_OPERATOR,
    TURN_ROLES,
)
from jbg_ai.data.paths import AI_SERVICE_ROOT
from jbg_ai.evals.agent_sets import (
    LOAD_SET,
    PIECE_SPANISH,
    SET_ID,
    VOCABULARIES,
    build,
    render,
)

CALIBRATION = AI_SERVICE_ROOT / "evals" / "agent" / "calibration.yaml"
GOLDEN_QUERIES = AI_SERVICE_ROOT / "evals" / "golden" / "queries.jsonl"


def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def normalise(text: str) -> str:
    """Case, accents and punctuation folded away, so «overlap» is not defeated by an accent."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9 ]+", " ", stripped).strip()


def operator_lines(document, key: str) -> list[str]:
    return [
        turn["text"]
        for item in document[key]
        for turn in item["turns"]
        if turn["role"] == TURN_ROLE_OPERATOR
    ]


# --- 12.4 · the wall. The golden set is not touched, and this is the evidence --------------


def test_no_transcript_of_either_agent_set_reuses_a_golden_query() -> None:
    """HU escenario 14, last clause. **Walked in both directions and not asserted.**

    The comparison this capability exists to enable is run over the golden set by a later
    change. A prompt iterated against that set, or an instrument seeded from it, would make its
    own verdict meaningless — which is the same reason the classifier's prompt is already
    required to derive from the catalogue's vocabulary rather than from the evaluation sets.

    Normalised on both sides, so an accent or a capital cannot be what makes an overlap
    invisible.
    """
    golden = {
        normalise(json.loads(line)["text"])
        for line in GOLDEN_QUERIES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    assert len(golden) >= 48, "the golden set must actually have been read"

    load_lines = {normalise(text) for text in operator_lines(load(LOAD_SET), "transcripts")}
    calibration_lines = {
        normalise(text) for text in operator_lines(load(CALIBRATION), "scenarios")
    }

    assert not (golden & load_lines), sorted(golden & load_lines)
    assert not (golden & calibration_lines), sorted(golden & calibration_lines)


def test_the_golden_set_is_unreferenced_by_the_agents_instruments_and_their_generator() -> None:
    """Not even by name: a set that is read «only for inspiration» is a set that leaked."""
    sources = [
        LOAD_SET,
        CALIBRATION,
        AI_SERVICE_ROOT / "src" / "jbg_ai" / "evals" / "agent_sets.py",
    ]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        assert "queries.jsonl" not in text, path.name
        assert "judgements" not in text, path.name


# --- 12.1 · the load set: generated, declared as load, and reproducible --------------------


def test_the_committed_load_set_is_what_the_generator_produces() -> None:
    """An artefact in git that nobody can regenerate is an artefact nobody can trust.

    The seed is fixed for exactly this: two people running the generator get the same file,
    byte for byte, so a diff on it always means somebody changed the generator.
    """
    assert LOAD_SET.read_text(encoding="utf-8") == render(build())


def test_the_generator_is_deterministic_for_one_seed_and_moves_with_another() -> None:
    assert build() == build()
    assert build(seed="another") != build()


def test_the_load_set_declares_that_it_measures_load_and_carries_no_ground_truth() -> None:
    """Task 12.1. Declared **in the file**, because the file is what a later reader opens."""
    document = load(LOAD_SET)

    assert document["id"] == SET_ID
    assert document["measures"] == "load"
    assert document["carries_ground_truth"] is False
    # And it annotates no expected tool anywhere: that is the other instrument's job.
    assert "expects" not in LOAD_SET.read_text(encoding="utf-8")

    header = LOAD_SET.read_text(encoding="utf-8").splitlines()[0]
    assert "CARGA" in header and "GENERADO" in header


def test_the_load_set_is_between_sixty_and_a_hundred_transcripts() -> None:
    """The size the design fixes, and the reason: a p95 needs variety of transcripts."""
    document = load(LOAD_SET)

    assert 60 <= document["size"] <= 100
    assert document["size"] == len(document["transcripts"])
    assert len({item["id"] for item in document["transcripts"]}) == document["size"]


def test_the_load_set_spreads_its_lengths_so_a_growth_curve_has_points() -> None:
    """A set of uniform length would produce one point of the curve it exists to publish."""
    document = load(LOAD_SET)
    spread = document["by_operator_turns"]

    assert set(spread) == {"1", "2", "3", "4", "5"}
    assert all(count > 0 for count in spread.values())
    # A transcript of n operator turns carries n-1 attributed assistant turns between them.
    for item in document["transcripts"]:
        assert len(item["turns"]) == item["operator_turns"] * 2 - 1


def test_the_load_set_is_seeded_from_the_catalogues_own_closed_vocabulary() -> None:
    """Not from the synthetic world simulator, which would drag its model of the world into an
    instrument that only measures accumulation. Q-3, checked rather than restated."""
    vocabulary = yaml.safe_load(VOCABULARIES.read_text(encoding="utf-8"))
    materials = set(vocabulary["materials"]["terms"])
    text = " ".join(operator_lines(load(LOAD_SET), "transcripts"))

    assert sum(1 for term in materials if term in text) >= 5, "real materials are used"
    assert "simulate" not in (
        AI_SERVICE_ROOT / "src" / "jbg_ai" / "evals" / "agent_sets.py"
    ).read_text(encoding="utf-8")


def test_every_piece_type_of_the_vocabulary_has_its_spanish() -> None:
    """A thirteenth piece type breaks this rather than producing «busco un cadena».

    The same shape C32a gave the bucket-to-label map: the duplication is not removed, it is
    moved to where it fails loudly. Broken Spanish in a load set is not cosmetic — it invites a
    clarification the model would not otherwise ask for, and a clarification is a turn that
    lands in the token and latency distributions with nothing to attribute it to.
    """
    vocabulary = yaml.safe_load(VOCABULARIES.read_text(encoding="utf-8"))

    assert set(PIECE_SPANISH) == set(vocabulary["piece_type"]["terms"])


# --- 12.2 and 12.3 · the calibration set: hand-written, annotated, calibration-only --------


def test_the_calibration_set_declares_itself_calibration_only() -> None:
    """Task 12.3. So the evaluation change cannot reuse it without noticing.

    A set a prompt was tuned against cannot afterwards arbitrate that prompt, and the label is
    what makes reuse a deliberate act rather than an accident.
    """
    document = load(CALIBRATION)

    assert document["usage"] == "calibration-only"
    assert document["carries_ground_truth"] is True
    assert document["measures"] == "ground-truth"
    assert document["golden_set_used"] is False
    assert document["not_for_evaluation"].strip()

    header = CALIBRATION.read_text(encoding="utf-8").splitlines()[0]
    assert "CALIBRATION-ONLY" in header


def test_the_calibration_set_is_fifteen_to_twenty_annotated_scenarios() -> None:
    document = load(CALIBRATION)
    scenarios = document["scenarios"]

    assert 15 <= len(scenarios) <= 20
    assert len({item["id"] for item in scenarios}) == len(scenarios)
    for item in scenarios:
        assert item["why"].strip(), item["id"]
        assert "expects" in item or "expects_any" in item, item["id"]


def test_every_tool_the_calibration_set_names_belongs_to_the_frozen_set() -> None:
    """An expectation naming a tool that does not exist would be unmeasurable and green."""
    for item in load(CALIBRATION)["scenarios"]:
        named = (
            list(item.get("expects", []))
            + list(item.get("expects_any", []))
            + list(item.get("forbids", []))
        )
        for name in named:
            assert name in TOOL_NAMES, f"{item['id']}: {name}"


def test_the_calibration_set_covers_every_tool_of_the_frozen_set() -> None:
    """Otherwise «this tool was never chosen» could be an artefact of never having asked.

    A dead tool is one of the four things the granularity question reads off the trace, and it
    is only readable if the set gave the model a reason to reach for each of the six.
    """
    named = {
        name
        for item in load(CALIBRATION)["scenarios"]
        for name in list(item.get("expects", [])) + list(item.get("expects_any", []))
    }

    assert named == set(TOOL_NAMES), sorted(set(TOOL_NAMES) - named)


def test_the_four_availability_labels_are_each_calibrated_and_the_three_forbid_the_pivot() -> None:
    """D-18, and the separation of over-pivot from under-pivot made concrete.

    A set that only declared what must happen would measure under-pivoting and be blind to
    over-pivoting, which is the expensive failure: turning a customer away from a piece the
    shop can actually sell.
    """
    scenarios = [
        item
        for item in load(CALIBRATION)["scenarios"]
        if "availability" in (item.get("fixture") or {})
    ]
    # Grouped rather than keyed: three scenarios share the out-of-stock label, and a dict
    # comprehension would silently check only the last of them — the kind of vacuity that let
    # a hardcoded flag pass its first review in C32a.
    by_label: dict[str, list[dict]] = {}
    for item in scenarios:
        by_label.setdefault(item["fixture"]["availability"], []).append(item)

    assert set(by_label) == set(AVAILABILITY_LABELS), sorted(by_label)

    # Out of stock is the only one that must pivot, and every one of its scenarios says so.
    for item in by_label["sin_existencias"]:
        assert "buscar_sustitutos" in item["expects"], item["id"]
    for label in ("ultimas_unidades", "disponible", "sin_ambito"):
        for item in by_label[label]:
            assert "buscar_sustitutos" in item["forbids"], item["id"]
            assert "buscar_sustitutos" not in item.get("expects", []), item["id"]


def test_every_fixture_scenario_carries_the_placeholder_the_harness_resolves() -> None:
    """Without it the pivot scenarios measure nothing, and they measure it silently.

    «El cliente quiere esta pieza» gives the model no reference to hand to the availability
    tool, so it would search first and end up checking whatever it found — not the piece whose
    label the scenario declares. The pivot rate per label would then be computed over pieces
    chosen at random, and nothing would say so. Both directions are pinned: the marker is
    required wherever there is a fixture and forbidden wherever there is not.
    """
    for item in load(CALIBRATION)["scenarios"]:
        text = " ".join(turn["text"] for turn in item["turns"])
        if "fixture" in item:
            assert "{pieza}" in text, f"{item['id']} declares a fixture and anchors nothing"
        else:
            assert "{pieza}" not in text, f"{item['id']} has nothing to resolve it with"


def test_a_scenario_that_admits_alternatives_says_so_in_the_format_and_not_in_its_prose() -> None:
    """The defect the first pass exposed, turned into a rule the next author cannot repeat.

    Two scenarios wrote «se admite cualquiera de las dos» in their prose and encoded it with
    `expects`, which is a **conjunction**: the harness counted them as failures for doing
    exactly what their own text allowed. A format without a disjunction forces expectations
    stricter than the author means, and the mismatch is invisible until a paid run reads them.

    So: a scenario whose prose offers a choice must use `expects_any`, and the two fields are
    mutually exclusive — declaring both would leave «all of these, or any of those» for a
    reader to resolve.
    """
    offers_a_choice = ("cualquiera de", "alguna de", "una de las dos", "o bien")

    for item in load(CALIBRATION)["scenarios"]:
        assert not ("expects" in item and "expects_any" in item), (
            f"{item['id']} declares both; pick the conjunction or the disjunction"
        )
        prose = item["why"].casefold()
        if any(phrase in prose for phrase in offers_a_choice):
            assert "expects_any" in item, (
                f"{item['id']} offers a choice in its prose and encodes a conjunction"
            )


def test_no_scenario_hard_codes_a_piece_reference() -> None:
    """The availability projection moves with every sync, so a SKU written today calibrates
    against a label that is something else tomorrow — and the scenario would stop measuring
    what it says it measures with nothing failing. The label travels in `fixture` and the
    harness resolves a piece that satisfies it at run time."""
    text = CALIBRATION.read_text(encoding="utf-8")

    assert not re.search(r"JBG-\d{4}", text)
    for item in load(CALIBRATION)["scenarios"]:
        fixture = item.get("fixture")
        if fixture:
            # Two kinds, and both are resolved at run time rather than written down: an
            # availability label, or a piece whose family holds several variants.
            assert set(fixture) in ({"availability"}, {"family"}), item["id"]
            if "family" in fixture:
                assert fixture["family"] == "con_variantes", item["id"]


# --- both sets are servable: the contract's caps hold for every transcript -----------------


def test_every_transcript_of_both_sets_fits_the_contracts_declared_caps() -> None:
    """A transcript the route would refuse with a 422 is a transcript that measures nothing,
    and finding that out during a paid run is finding it out too late."""
    documents = ((load(LOAD_SET), "transcripts"), (load(CALIBRATION), "scenarios"))

    for document, key in documents:
        for item in document[key]:
            turns = item["turns"]
            assert 1 <= len(turns) <= MAX_TRANSCRIPT_TURNS, item["id"]
            assert any(turn["role"] == TURN_ROLE_OPERATOR for turn in turns), item["id"]
            assert sum(len(turn["text"]) for turn in turns) <= MAX_TRANSCRIPT_CHARS, item["id"]
            for turn in turns:
                assert turn["role"] in TURN_ROLES, item["id"]
                assert 1 <= len(turn["text"]) <= MAX_TURN_CHARS, item["id"]


def test_both_sets_are_accepted_by_the_request_model_of_the_route() -> None:
    """Validated against the contract itself rather than against a restatement of its caps: the
    two cannot drift, and a cap tightened later fails here instead of in the middle of a run."""
    from jbg_ai.api.schemas.assist import AgentAssistRequest

    for document, key in ((load(LOAD_SET), "transcripts"), (load(CALIBRATION), "scenarios")):
        for item in document[key]:
            AgentAssistRequest(turns=item["turns"])
