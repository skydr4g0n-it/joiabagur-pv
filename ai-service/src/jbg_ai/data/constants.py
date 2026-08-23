"""Constants for the C06b synthetic catalog CLI."""

from __future__ import annotations

DEFAULT_SEED = "20260822"
GENERATOR_VERSION = "c06b-synth/v3"
PROMPT_VERSION = "catalog-synth/v3"
DEFAULT_LLM_MODEL = "gpt-4o"
# gpt-4o structured-output batches: ~76 pieces/colección reventaría el JSON.
LLM_DRAFT_BATCH_SIZE = 12

DESCRIPTION_MAX_LEN = 1000
NAME_MAX_LEN = 200
COLLECTION_NAME_MAX_LEN = 100
SKU_MAX_LEN = 50
PRICE_MAX = 50_000
SKU_START = 437
TARGET_HYBRID_TOTAL = 1200
REAL_CORPUS_COUNT = 436
DEFAULT_SYNTHETIC_COUNT = TARGET_HYBRID_TOTAL - REAL_CORPUS_COUNT

RICH_CUTOFF = 0.70
SPARSE_CUTOFF = 0.90
RATIO_TOLERANCE_PP = 5.0
TARGET_RATIOS = {"rich": 70.0, "sparse": 20.0, "short": 10.0}

# Calibrated to C06a ai_enriched means: rich ~289, sparse ~115, original ~14 (some empty).
SHORT_MAX_CHARS = 32
SPARSE_MAX_CHARS = 115
SPARSE_OVERFLOW_CHARS = 140
SPARSE_MAX_SENTENCES = 2
RICH_MIN_CHARS = 150
RICH_MIN_SENTENCES = 3
RICH_MAX_SENTENCES = 5
SHORT_EMPTY_RATIO = 0.20

UNASSIGNED_RATIO = 0.20
FAMILY_MEMBER_RATIO = 0.40
COMPLETE_FAMILY_PRODUCT_RATIO = 0.60
FAMILY_SIZES = ("S", "M", "L", "XL")
SIZE_PRICE_FACTORS = {"S": "1.00", "M": "1.15", "L": "1.30", "XL": "1.50"}

JSONL_FILENAME = "catalog-synthetic.jsonl"
META_FILENAME = "catalog-synthetic.meta.json"

FORBIDDEN_JSON_KEYS = (
    "variant_group_key",
    "variant_label",
    "family_seed",
    "materials",
    "product_id",
)

CHANNEL_COLLECTION_NAMES = frozenset(
    {
        "hotel",
        "aeropuerto",
        "airport",
        "turista",
        "tourist",
        "atelier",
        "atelier clasico",
        "atelier clásico",
        "pos",
        "canal",
        "coleccion hotel",
        "colección hotel",
        "coleccion aeropuerto",
        "colección aeropuerto",
        "coleccion turista",
        "colección turista",
        "coleccion atelier",
        "colección atelier",
    }
)

JSONL_FIELDS = (
    "sku",
    "name",
    "description",
    "price",
    "collection_name",
    "data_origin",
    "text_provenance",
    "text_quality_tier",
)
