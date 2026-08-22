DEFAULT_SEED = "20260822"
GENERATOR_VERSION = "c06a-assist/v2"
DESCRIPTION_MAX_LEN = 1000
RICH_CUTOFF = 0.70
SPARSE_CUTOFF = 0.90
RATIO_TOLERANCE_PP = 3.0
TARGET_RATIOS = {"rich": 70.0, "sparse": 20.0, "original": 10.0}

REQUIRED_COLUMNS = ("SKU", "Name", "Description", "Price", "Collection")
IDENTITY_FIELDS = ("sku", "name", "price", "collection_name")
FAMILY_JSON_KEYS = ("variant_group_key", "variant_label", "family_seed")

JSONL_FILENAME = "catalog-real-enriched.jsonl"
META_FILENAME = "catalog-real-enriched.meta.json"
