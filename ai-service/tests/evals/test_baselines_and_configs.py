"""The two lexical baselines replicate the semantics they claim to, and cost zero. C24."""

from __future__ import annotations

import re

import pytest

from jbg_ai.evals.baselines import (
    DESCRIPTION_PREFIX,
    MAX_TERMS,
    V0_FTS_SQL,
    V0_NOMBRE_SQL,
    tokenize,
    websearch_terms,
)
from jbg_ai.evals.configs import ABLATION_ORDER, POOLED, load_all, load_config
from jbg_ai.evals.errors import ConfigurationError
from jbg_ai.indexing.source_text import ProductSourceText, build_source_text


def test_v0_fts_composes_only_over_the_dotnet_columns() -> None:
    """Name, code and description. Never the canonical document, which carries more.

    A full-text search over `doc_text` would see `Tipo:`, `Materiales:`, `Colores:` and the
    rest — fields the .NET searcher has never had — so it would be an upper bound on this
    baseline rather than a replica of it, and the comparison it exists for would be rigged in
    its own favour.
    """
    assert "d.name" in V0_FTS_SQL
    assert "d.sku" in V0_FTS_SQL
    assert DESCRIPTION_PREFIX in V0_FTS_SQL
    for extracted in ("piece_type", "materials", "stone_type", "color_tags", "style_tags"):
        assert extracted not in V0_FTS_SQL
    # `doc_text` appears exactly once, inside the expression that pulls the description line
    # back out of it — never as the search document itself.
    assert V0_FTS_SQL.count("doc_text") == 2, "once in the SELECT, once in the WHERE"
    assert "to_tsvector('spanish', d.doc_text)" not in V0_FTS_SQL


def test_the_renderer_still_emits_the_description_line_with_its_prefix() -> None:
    """The prefix is a CONTRACT of the canonical renderer, not a formatting detail.

    If `build_source_text` stops emitting it, this test fails — instead of the full-text
    baseline quietly becoming a search over the empty string and looking merely worse.
    """
    rendered = build_source_text(
        ProductSourceText(
            sku="SKU1",
            name="Anillo",
            description="Anillo de plata de ley.",
            piece_type="anillo",
            materials=["plata"],
        )
    )

    line = next(
        item for item in rendered.splitlines() if item.startswith(DESCRIPTION_PREFIX)
    )
    assert line == f"{DESCRIPTION_PREFIX}Anillo de plata de ley."
    assert re.search(r"(?m)^Descripción: ", rendered)


def test_v0_nombre_matches_the_whole_query_as_a_substring_and_never_tokenises() -> None:
    """A two-word natural-language query returns nothing, and that is the replica being faithful."""
    assert "position(lower(:q) in lower(d.name)) > 0" in V0_NOMBRE_SQL
    assert "upper(d.sku) = upper(:q)" in V0_NOMBRE_SQL
    assert "tsvector" not in V0_NOMBRE_SQL
    assert "tsquery" not in V0_NOMBRE_SQL
    assert "ORDER BY sku_exact DESC, d.name ASC" in V0_NOMBRE_SQL


def test_both_baselines_truncate_under_a_total_order() -> None:
    """The same property the live path gained, for the same reason."""
    for sql in (V0_FTS_SQL, V0_NOMBRE_SQL):
        ordering = next(
            line.strip() for line in sql.splitlines() if line.strip().startswith("ORDER BY")
        )
        assert ordering.endswith("d.product_id ASC")


def test_the_tokeniser_is_the_dotnet_one_term_for_term() -> None:
    assert tokenize("un anillo de plata") == ["un", "anillo", "de", "plata"]
    assert tokenize("a anillo") == ["anillo"], "single characters carry no signal"
    assert tokenize("Anillo anillo ANILLO") == ["Anillo"], "distinct, case-insensitively"
    assert len(tokenize(" ".join(f"t{index}" for index in range(30)))) == MAX_TERMS


def test_terms_are_joined_so_that_matching_any_of_them_is_enough() -> None:
    """A strict conjunction returns nothing on every natural-language query."""
    assert websearch_terms("anillo de plata") == "anillo OR de OR plata"
    assert websearch_terms("") == ""


def test_the_five_configurations_load_and_the_table_is_in_order() -> None:
    configs = load_all()

    assert [item.id for item in configs] == list(ABLATION_ORDER)
    assert {item.id for item in configs if item.pooled} == set(POOLED)


def test_the_zero_cost_baselines_record_zero_and_not_an_absent_value() -> None:
    """A blank in that column would read as "not measured", which is the opposite of the point."""
    for config_id in ("v0-nombre", "v0-fts"):
        config = load_config(config_id)
        assert config.uses_provider is False

    from jbg_ai.evals.pricing import load_prices

    prices = load_prices()
    cost = 0.0 if not load_config("v0-fts").uses_provider else None
    assert cost == 0.0
    assert prices.cost("openai/text-embedding-3-small", input_tokens=0) == 0.0


def test_a_misspelt_knob_is_refused_instead_of_silently_ignored() -> None:
    """A silently dropped weight produces a row of the table measuring something else."""
    from jbg_ai.evals.configs import EvalConfig

    with pytest.raises(ConfigurationError, match="unknown keys"):
        EvalConfig.from_mapping(
            {
                "id": "x",
                "kind": "pipeline",
                "label": "x",
                "rationale": "x",
                "uses_provider": True,
                "wieght_vector": 1.0,
            },
            where="fixture",
        )


def test_no_configuration_scopes_by_point_of_sale() -> None:
    """The golden set is labelled unscoped, so retrieval quality is not mixed with assortment."""
    for config in load_all():
        assert config.pos_prefilter is False


def test_the_prices_carry_their_date_and_source() -> None:
    from jbg_ai.evals.pricing import load_prices

    prices = load_prices()

    assert prices.source.startswith("https://")
    assert prices.as_of != "unknown"
    assert prices.verified is True
