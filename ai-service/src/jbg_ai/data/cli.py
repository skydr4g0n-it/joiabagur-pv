"""CLI: `python -m jbg_ai.data generate|ingest`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jbg_ai.data.constants import (
    DEFAULT_LLM_MODEL,
    DEFAULT_SEED,
    DEFAULT_SYNTHETIC_COUNT,
    GENERATOR_VERSION,
    PROMPT_VERSION,
)
from jbg_ai.data.errors import CatalogDataError
from jbg_ai.data.generate import generate_corpus
from jbg_ai.data.ingest import ingest_records
from jbg_ai.data.io import collection_names_from_jsonl, read_jsonl
from jbg_ai.data.paths import REAL_JSONL, SYNTHETIC_DIR, default_output_paths
from jbg_ai.data.sku import occupied_skus_from_jsonl


def _print(message: str) -> None:
    sys.stdout.write(message + "\n")


def _require_catalog_llm_key() -> tuple[str, str, str | None]:
    import os

    from jbg_ai.data.envload import load_local_env

    load_local_env()
    key = (os.environ.get("JPV_CATALOG_LLM_API_KEY") or "").strip()
    if not key:
        raise CatalogDataError(
            "generate requires JPV_CATALOG_LLM_API_KEY in backend/.env "
            "(copy backend/.env.example). Distinct from JPV_RAG_LLM_API_KEY. "
            "GET /health does not need either key."
        )
    model = (os.environ.get("JPV_CATALOG_LLM_MODEL") or DEFAULT_LLM_MODEL).strip()
    base = (os.environ.get("JPV_CATALOG_LLM_BASE_URL") or "").strip() or None
    return key, model, base


def cmd_generate(args: argparse.Namespace) -> int:
    from jbg_ai.data.llm import OpenAICatalogLlm

    key, model, base_url = _require_catalog_llm_key()
    llm = OpenAICatalogLlm(api_key=key, model=model, base_url=base_url)
    jsonl_path, meta_path, records = generate_corpus(
        output_dir=Path(args.out),
        llm=llm,
        real_jsonl=Path(args.real_jsonl),
        seed=args.seed,
        product_count=args.count,
        regenerate_text=args.regenerate_text,
    )
    _print(f"wrote {len(records)} lines -> {jsonl_path}")
    _print(f"wrote sidecar -> {meta_path}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from jbg_ai.data.envload import load_local_env

    load_local_env()
    jsonl_path = Path(args.jsonl)
    real_path = Path(args.real_jsonl)
    records = read_jsonl(jsonl_path)
    result = ingest_records(
        records,
        real_skus=occupied_skus_from_jsonl(real_path),
        real_collections=collection_names_from_jsonl(real_path),
    )
    _print(
        f"collections={result.collections_inserted} products={result.products_inserted}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m jbg_ai.data",
        description="C06b synthetic catalog CLI (generate + local ingest).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="Call OpenAI and write JSONL + sidecar")
    generate.add_argument("--out", default=str(SYNTHETIC_DIR))
    generate.add_argument("--real-jsonl", default=str(REAL_JSONL))
    generate.add_argument("--seed", default=DEFAULT_SEED)
    generate.add_argument("--count", type=int, default=DEFAULT_SYNTHETIC_COUNT)
    generate.add_argument("--regenerate-text", action="store_true")
    generate.set_defaults(func=cmd_generate)

    ingest = sub.add_parser("ingest", help="INSERT collections + products (JPV_PG*)")
    default_jsonl, _ = default_output_paths()
    ingest.add_argument("--jsonl", default=str(default_jsonl))
    ingest.add_argument("--real-jsonl", default=str(REAL_JSONL))
    ingest.set_defaults(func=cmd_ingest)

    parser.epilog = (
        f"generator_version={GENERATOR_VERSION} prompt_version={PROMPT_VERSION} "
        f"default_seed={DEFAULT_SEED}"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CatalogDataError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
