"""Load and validate curated POS YAML. Delivered by C10."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from jbg_ai.data.errors import ValidationError
from jbg_ai.data.world.constants import (
    CENSUS_CODES,
    CLOSED_HOTEL_CODE,
    CODE_MAX_LEN,
    DEFAULT_HORIZON_MONTHS,
    DEFAULT_SEED,
    DEFAULT_SKU_HOLES,
    GENERATOR_VERSION,
    MANUAL_PRICE_CODES,
    OPERATOR_POS,
    PHONE_MAX_LEN,
    PINNED_PHONE,
    SUPPLY_SOURCE_CODE,
)
from jbg_ai.data.world.records import OperatorProfile, PosProfile, WorldProfiles

_UUID_KEYS = frozenset(
    {
        "id",
        "uuid",
        "product_id",
        "point_of_sale_id",
        "pos_id",
        "userid",
        "user_id",
    }
)


def load_profiles(path: Path | str) -> WorldProfiles:
    source = Path(path)
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValidationError(f"{source}: YAML root must be a mapping.")
    _reject_uuids(payload, source.name)
    return parse_profiles(payload)


def parse_profiles(payload: dict[str, Any]) -> WorldProfiles:
    generator_version = str(payload.get("generator_version") or "").strip()
    seed = str(payload.get("seed") or "").strip()
    if not generator_version:
        raise ValidationError("profiles must declare generator_version.")
    if not seed:
        raise ValidationError("profiles must declare seed.")

    phone = str(payload.get("phone") or PINNED_PHONE).strip()
    if phone != PINNED_PHONE or len(phone) > PHONE_MAX_LEN:
        raise ValidationError(f"phone must be {PINNED_PHONE!r} (varchar 20).")

    horizon = int(payload.get("horizon_months") or DEFAULT_HORIZON_MONTHS)
    if horizon < 14 or horizon > 18:
        raise ValidationError("horizon_months must be in 14–18.")

    holes = tuple(
        str(item).strip()
        for item in (payload.get("catalog_sku_holes") or DEFAULT_SKU_HOLES)
        if str(item).strip()
    )
    operators = tuple(_parse_operator(item) for item in payload.get("operators") or [])
    pos_rows = tuple(_parse_pos(item) for item in payload.get("pos") or [])
    _validate_census(pos_rows)
    _validate_operators(operators, pos_rows)

    return WorldProfiles(
        generator_version=generator_version,
        seed=seed,
        horizon_months=horizon,
        phone=phone,
        inactive_inventory_ratio_live_pos=float(
            payload.get("inactive_inventory_ratio_live_pos") or 0.08
        ),
        bulk_checkout_ratio=float(payload.get("bulk_checkout_ratio") or 0.15),
        catalog_sku_holes=holes,
        operators=operators,
        pos=pos_rows,
    )


def _parse_operator(raw: Any) -> OperatorProfile:
    if not isinstance(raw, dict):
        raise ValidationError("operator entries must be mappings.")
    username = str(raw.get("username") or "").strip()
    pos_code = str(raw.get("pos_code") or "").strip()
    if not username or not pos_code:
        raise ValidationError("operator requires username and pos_code.")
    expected = OPERATOR_POS.get(username)
    if expected and expected != pos_code:
        raise ValidationError(f"{username} must be assigned to {expected}.")
    return OperatorProfile(
        username=username,
        first_name=str(raw.get("first_name") or "").strip(),
        last_name=str(raw.get("last_name") or "").strip(),
        password=str(raw.get("password") or "Operator123!"),
        pos_code=pos_code,
    )


def _parse_pos(raw: Any) -> PosProfile:
    if not isinstance(raw, dict):
        raise ValidationError("pos entries must be mappings.")
    code = str(raw.get("code") or "").strip()
    if not code:
        raise ValidationError("pos.code is required.")
    if len(code) > CODE_MAX_LEN:
        raise ValidationError(f"pos.code {code!r} exceeds varchar(20).")
    seasonality = _parse_seasonality(raw.get("seasonality"))
    weights_raw = raw.get("collection_weights") or {}
    if not isinstance(weights_raw, dict):
        raise ValidationError(f"{code}: collection_weights must be a mapping.")
    weights = {str(key): float(value) for key, value in weights_raw.items()}
    closed_after = _parse_optional_date(raw.get("closed_after"))
    operator = raw.get("operator")
    operator_name = None if operator in (None, "", "null") else str(operator).strip()
    return PosProfile(
        code=code,
        name=str(raw.get("name") or "").strip(),
        island=str(raw.get("island") or "").strip(),
        address=str(raw.get("address") or "").strip(),
        is_supply_source=bool(raw.get("is_supply_source")),
        is_active=bool(raw.get("is_active", True)),
        allow_manual_price_edit=bool(raw.get("allow_manual_price_edit")),
        lambda_retail=float(raw.get("lambda_retail") or 0.0),
        coverage=float(raw.get("coverage") or 0.3),
        qty_min=int(raw.get("qty_min") or 4),
        qty_max=int(raw.get("qty_max") or 12),
        seasonality=seasonality,
        collection_weights=weights,
        operator=operator_name,
        closed_after=closed_after,
    )


def _parse_seasonality(raw: Any) -> dict[int, float]:
    if not isinstance(raw, dict) or not raw:
        raise ValidationError("each POS needs seasonality with months 1–12.")
    parsed: dict[int, float] = {}
    for key, value in raw.items():
        month = int(key)
        if month < 1 or month > 12:
            raise ValidationError(f"seasonality month {month} is out of range.")
        parsed[month] = float(value)
    if set(parsed) != set(range(1, 13)):
        raise ValidationError("seasonality must include all twelve months.")
    return parsed


def _parse_optional_date(raw: Any) -> date | None:
    if raw in (None, "", "null"):
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    return date.fromisoformat(str(raw))


def _validate_census(pos_rows: tuple[PosProfile, ...]) -> None:
    codes = [row.code for row in pos_rows]
    if sorted(codes) != sorted(CENSUS_CODES):
        raise ValidationError(
            "YAML must list exactly the twelve census codes: "
            + ", ".join(CENSUS_CODES)
        )
    if len(set(codes)) != len(codes):
        raise ValidationError("POS codes must be unique.")
    supply = [row.code for row in pos_rows if row.is_supply_source]
    if supply != [SUPPLY_SOURCE_CODE]:
        raise ValidationError(f"exactly one is_supply_source: {SUPPLY_SOURCE_CODE}.")
    closed = next(row for row in pos_rows if row.code == CLOSED_HOTEL_CODE)
    if closed.is_active:
        raise ValidationError(f"{CLOSED_HOTEL_CODE} must have is_active: false.")
    if closed.closed_after is None or closed.closed_after < date(2025, 9, 1):
        raise ValidationError(
            f"{CLOSED_HOTEL_CODE} closed_after must be on or after 2025-09-01."
        )
    for row in pos_rows:
        expected_manual = row.code in MANUAL_PRICE_CODES
        if row.allow_manual_price_edit != expected_manual:
            raise ValidationError(
                f"{row.code}: allow_manual_price_edit must be {expected_manual}."
            )
        if not row.name:
            raise ValidationError(f"{row.code}: name is required.")


def _validate_operators(
    operators: tuple[OperatorProfile, ...], pos_rows: tuple[PosProfile, ...]
) -> None:
    expected = set(OPERATOR_POS)
    found = {op.username for op in operators}
    if found != expected:
        raise ValidationError(f"operators must be exactly {sorted(expected)}.")
    live_codes = {row.code for row in pos_rows}
    for op in operators:
        if op.pos_code not in live_codes:
            raise ValidationError(f"operator {op.username} POS {op.pos_code} missing.")
        if not op.first_name or not op.last_name:
            raise ValidationError(f"operator {op.username} needs first_name/last_name.")


def _reject_uuids(node: Any, where: str) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            folded = str(key).casefold()
            if folded in _UUID_KEYS:
                raise ValidationError(f"{where}: UUID field {key!r} is not allowed.")
            if isinstance(value, str):
                try:
                    uuid.UUID(value)
                except ValueError:
                    pass
                else:
                    if folded.endswith("_id") or folded in {"id", "uuid"}:
                        raise ValidationError(f"{where}: UUID value for {key!r}.")
            _reject_uuids(value, where)
    elif isinstance(node, list):
        for item in node:
            _reject_uuids(item, where)
