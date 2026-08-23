"""Name-stem grouping and 70/20/10 tiers. Delivered by C06b."""

from __future__ import annotations

from jbg_ai.data.errors import RatioError
from jbg_ai.data.quality import (
    apply_empty_short_descriptions,
    assert_no_mixed_tiers,
    assert_ratio_tolerance,
    assign_quality,
    description_is_complete,
    description_matches_tier,
    fit_description_to_tier,
    name_stem,
    rebalance_assignments,
    ratios_by_tier,
    stems_for,
)
from jbg_ai.data.records import SyntheticRecord


def test_name_stem_siblings_share_stem() -> None:
    assert name_stem("Colgante erizo S") == name_stem("Colgante erizo M")
    assert name_stem("Pendiente único") == "pendiente-unico"


def test_name_stem_siblings_share_text_quality_tier() -> None:
    names = {
        "SKU437": "Colgante erizo S",
        "SKU438": "Colgante erizo M",
        "SKU439": "Anillo solitario",
    }
    stems = stems_for(names)
    assert stems["SKU437"] == stems["SKU438"]
    assert stems["SKU439"] != stems["SKU437"]
    tiers = assign_quality(stems, seed="20260822", rebalance=False)
    assert tiers["SKU437"] == tiers["SKU438"]
    assert_no_mixed_tiers(stems, tiers)


def test_quality_assignment_is_deterministic_for_same_seed() -> None:
    stems = {"SKU437": "colgante-erizo", "SKU438": "colgante-erizo", "SKU439": "anillo"}
    first = assign_quality(stems, seed="20260822", rebalance=False)
    second = assign_quality(stems, seed="20260822", rebalance=False)
    assert first == second


def test_rebalance_moves_whole_stems_into_ratio_window() -> None:
    sku_to_stem = {f"SKU{i}": f"stem-{i}" for i in range(100)}
    lopsided = {sku: "rich" for sku in sku_to_stem}
    balanced = rebalance_assignments(sku_to_stem, lopsided)  # type: ignore[arg-type]
    assert_no_mixed_tiers(sku_to_stem, balanced)
    assert_ratio_tolerance(ratios_by_tier(list(balanced.values())))


def test_fit_description_matches_declared_tier() -> None:
    long_copy = (
        "Plata. "
        "Segunda frase de uso y gesto en vitrina con metal trabajado. "
        "Tercera frase de escaparate con presencia clara. "
        "Cuarta frase de cierre para el catálogo."
    )
    short = fit_description_to_tier(long_copy, "short")
    sparse = fit_description_to_tier(long_copy, "sparse")
    rich = fit_description_to_tier(long_copy, "rich")
    assert short == "Plata."
    assert description_matches_tier(short, "short")
    assert description_matches_tier(sparse, "sparse")
    assert description_matches_tier(rich, "rich")
    assert 0 < len(short) <= 32
    assert 32 < len(sparse) <= 140
    assert len(rich) >= 150
    assert len(short) < len(sparse) < len(rich)
    assert description_is_complete(short)
    assert description_is_complete(sparse)
    assert description_is_complete(rich)


def test_fit_does_not_leave_half_a_sentence() -> None:
    long_first = (
        "Una pulsera que cruza el pulso con un hilo de plata y ónix. "
        "Segunda frase de vitrina con más cuerpo."
    )
    short = fit_description_to_tier(long_first, "short")
    sparse = fit_description_to_tier(long_first, "sparse")
    assert short == ""
    assert "que." not in sparse
    assert sparse.startswith("Una pulsera que cruza el pulso")
    assert description_is_complete(sparse)
    assert not description_is_complete("El contraste entre.")
    assert not description_is_complete("Perfectos para añadir un toque de.")


def test_sparse_keeps_one_complete_sentence_just_over_115() -> None:
    over = (
        "Pendientes de plata de ley que recogen la luz menorquina al atardecer "
        "sin perder el gesto de joyero ni la presencia en vitrina."
    )
    assert 115 < len(over) <= 140
    sparse = fit_description_to_tier(over, "sparse")
    assert sparse == over
    assert description_matches_tier(sparse, "sparse")


def test_about_one_fifth_of_short_descriptions_are_emptied() -> None:
    records = [
        SyntheticRecord(
            sku=f"SKU{440 + index}",
            name=f"Pieza {index}",
            description="Plata.",
            price="10.00",
            collection_name="Fuego",
            text_quality_tier="short",
        )
        for index in range(10)
    ]
    emptied = apply_empty_short_descriptions(records, seed="20260822")
    blanks = sum(1 for record in emptied if record.description == "")
    assert blanks == 2
    assert all(record.text_quality_tier == "short" for record in emptied)


def test_lopsided_ratios_fail_tolerance_assertion() -> None:
    ratios = {"rich": 100.0, "sparse": 0.0, "short": 0.0}
    try:
        assert_ratio_tolerance(ratios)
    except RatioError:
        return
    raise AssertionError("expected RatioError")
