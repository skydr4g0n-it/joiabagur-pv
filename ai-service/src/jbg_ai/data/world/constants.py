"""Constants for the C10 synthetic world CLI."""

from __future__ import annotations

from jbg_ai.data.paths import REPO_ROOT

GENERATOR_VERSION = "c10-world/v1"
DEFAULT_SEED = "20260823"
DEFAULT_HORIZON_MONTHS = 16
PINNED_PHONE = "600123456"
ADMIN_USERNAME = "admin"
OPERATOR_ROLE = "Operator"
BCRYPT_ROUNDS = 12
BCRYPT_PREFIX = b"2a"

CENSUS_CODES: tuple[str, ...] = (
    "MAO-TALLER",
    "CIU-CENTRE",
    "MAO-AIR",
    "FORNELLS",
    "BINIBECA",
    "HT-GALDANA",
    "HT-SONBOU",
    "PORT-MAO",
    "PALMA-JAIME3",
    "EIV-MARINA",
    "HT-ALCUDIA",
    "HT-ARTRUTX",
)

SUPPLY_SOURCE_CODE = "MAO-TALLER"
CLOSED_HOTEL_CODE = "HT-ARTRUTX"
MANUAL_PRICE_CODES = frozenset(
    {"MAO-AIR", "HT-GALDANA", "HT-SONBOU", "EIV-MARINA", "HT-ALCUDIA"}
)
OPERATOR_POS: dict[str, str] = {
    "op-ciutadella": "CIU-CENTRE",
    "op-fornells": "FORNELLS",
    "op-aeroport": "MAO-AIR",
}

PAYMENT_CODES: tuple[str, ...] = (
    "CASH",
    "BIZUM",
    "TRANSFER",
    "CARD_OWN",
    "CARD_POS",
    "PAYPAL",
)

DEFAULT_SKU_HOLES: tuple[str, ...] = ("SKU135", "SKU400", "SKU418")

MOVEMENT_SALE = 1
MOVEMENT_RETURN = 2
MOVEMENT_ADJUSTMENT = 3
MOVEMENT_IMPORT = 4

CODE_MAX_LEN = 20
PHONE_MAX_LEN = 20
USERNAME_MAX_LEN = 50
PASSWORD_HASH_MAX_LEN = 128

INVENTORY_MIN = 6500
INVENTORY_MAX = 8000
SALES_MIN = 15_000
SALES_MAX = 25_000

WORLD_DIR = REPO_ROOT / "data" / "world"
PROFILES_PATH = WORLD_DIR / "pos-profiles.yaml"
GENERATED_DIR = WORLD_DIR / "generated"
BACKUPS_DIR = WORLD_DIR / "backups"

INVENTORIES_FILENAME = "inventories.jsonl"
SALES_FILENAME = "sales.jsonl"
MOVEMENTS_FILENAME = "movements.jsonl"
CO_OCCURRENCE_FILENAME = "co-occurrence.jsonl"
META_FILENAME = "world.meta.json"
