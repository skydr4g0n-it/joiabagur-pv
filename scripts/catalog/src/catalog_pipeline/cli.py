from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from catalog_pipeline.constants import DEFAULT_SEED, GENERATOR_VERSION
from catalog_pipeline.errors import CatalogError
from catalog_pipeline.generate import generate_corpus
from catalog_pipeline.grouping import group_products, grouping_counts
from catalog_pipeline.identity import assert_identities
from catalog_pipeline.ingest import ingest_records
from catalog_pipeline.quality import assert_ratio_tolerance, ratios_by_tier
from catalog_pipeline.reader import read_export
from catalog_pipeline.schema import read_jsonl, read_sidecar
from catalog_pipeline.validate import assert_sidecar_keys, validate_records


def _print(message: str) -> None:
    sys.stdout.write(message + "\n")


def cmd_generate(args: argparse.Namespace) -> int:
    jsonl_path, meta_path, records = generate_corpus(
        Path(args.source),
        Path(args.out),
        seed=args.seed,
        regenerate_text=args.regenerate_text,
    )
    _print(f"wrote {len(records)} lines -> {jsonl_path}")
    _print(f"wrote sidecar -> {meta_path}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    records = read_jsonl(Path(args.jsonl))
    source_rows = read_export(Path(args.source)) if args.source else None
    validate_records(records, source_rows=source_rows)
    if source_rows is not None:
        assert_identities(source_rows, records)
    if args.enforce_ratios:
        assert_ratio_tolerance(ratios_by_tier([r.text_quality_tier for r in records]))
    if args.meta:
        sidecar = read_sidecar(Path(args.meta))
        assert_sidecar_keys(sidecar)
    _print(f"ok: {len(records)} records")
    return 0


def cmd_spike(args: argparse.Namespace) -> int:
    rows = read_export(Path(args.source))
    counts = grouping_counts(group_products(rows))
    _print(json.dumps(counts, indent=2))
    if args.write:
        Path(args.write).write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    records = read_jsonl(Path(args.jsonl))
    result = ingest_records(records)
    _print(f"updated={result.updated} unmatched={len(result.unmatched)}")
    if result.unmatched:
        _print("unmatched SKUs:")
        for sku in result.unmatched:
            _print(f"  {sku}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="catalog-pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="Build JSONL + sidecar from an export")
    generate.add_argument("--source", required=True)
    generate.add_argument("--out", required=True)
    generate.add_argument("--seed", default=DEFAULT_SEED)
    generate.add_argument("--regenerate-text", action="store_true")
    generate.set_defaults(func=cmd_generate)

    validate = sub.add_parser("validate", help="Validate a JSONL corpus")
    validate.add_argument("--jsonl", required=True)
    validate.add_argument("--source")
    validate.add_argument("--meta")
    validate.add_argument("--enforce-ratios", action="store_true")
    validate.set_defaults(func=cmd_validate)

    spike = sub.add_parser("spike", help="Print grouping counts for an export")
    spike.add_argument("--source", required=True)
    spike.add_argument("--write")
    spike.set_defaults(func=cmd_spike)

    ingest = sub.add_parser("ingest", help="UPDATE Description by SKU (JPV_PG*)")
    ingest.add_argument("--jsonl", required=True)
    ingest.set_defaults(func=cmd_ingest)

    parser.epilog = f"generator_version={GENERATOR_VERSION} default_seed={DEFAULT_SEED}"
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CatalogError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
