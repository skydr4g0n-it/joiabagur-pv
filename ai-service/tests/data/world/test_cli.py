"""CLI flags for catalog generate/ingest stay intact when world is added."""

from __future__ import annotations

from jbg_ai.data.cli import build_parser


def test_world_cli_does_not_change_catalog_generate_ingest_flags() -> None:
    parser = build_parser()
    generate = parser.parse_args(["generate", "--help"] if False else ["generate"])
    assert hasattr(generate, "out")
    assert hasattr(generate, "real_jsonl")
    assert hasattr(generate, "seed")
    assert hasattr(generate, "count")
    assert hasattr(generate, "regenerate_text")

    ingest = parser.parse_args(["ingest"])
    assert hasattr(ingest, "jsonl")
    assert hasattr(ingest, "real_jsonl")

    world_sim = parser.parse_args(["world", "simulate"])
    assert hasattr(world_sim, "profiles")
    assert hasattr(world_sim, "out")
    world_ingest = parser.parse_args(["world", "ingest"])
    assert hasattr(world_ingest, "dir")
    assert hasattr(world_ingest, "profiles")
