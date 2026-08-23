"""YAML census and profile validation."""

from __future__ import annotations

from copy import deepcopy

import pytest

from jbg_ai.data.errors import ValidationError
from jbg_ai.data.world.constants import (
    CENSUS_CODES,
    CLOSED_HOTEL_CODE,
    CODE_MAX_LEN,
    MANUAL_PRICE_CODES,
    PINNED_PHONE,
    PROFILES_PATH,
    SUPPLY_SOURCE_CODE,
)
from jbg_ai.data.world.profiles import load_profiles, parse_profiles
from tests.data.world.helpers import profiles_payload


def test_yaml_census_has_twelve_codes() -> None:
    profiles = load_profiles(PROFILES_PATH)
    codes = [row.code for row in profiles.pos]
    assert sorted(codes) == sorted(CENSUS_CODES)
    assert len(set(codes)) == 12
    supply = [row for row in profiles.pos if row.is_supply_source]
    assert [row.code for row in supply] == [SUPPLY_SOURCE_CODE]
    closed = next(row for row in profiles.pos if row.code == CLOSED_HOTEL_CODE)
    assert closed.is_active is False
    assert closed.closed_after is not None
    assert closed.closed_after.isoformat() >= "2025-09-01"
    assert profiles.seed
    assert profiles.generator_version
    for row in profiles.pos:
        assert row.allow_manual_price_edit is (row.code in MANUAL_PRICE_CODES)


def test_phone_is_pinned_and_code_fits_varchar20() -> None:
    profiles = load_profiles(PROFILES_PATH)
    assert profiles.phone == PINNED_PHONE
    assert len(profiles.phone) <= 20
    for row in profiles.pos:
        assert 1 <= len(row.code) <= CODE_MAX_LEN


def test_profiles_reject_long_code() -> None:
    payload = deepcopy(profiles_payload())
    payload["pos"][0]["code"] = "THIS-CODE-IS-WAY-TOO-LONG"
    with pytest.raises(ValidationError, match="varchar\\(20\\)"):
        parse_profiles(payload)


def test_profiles_reject_wrong_phone() -> None:
    payload = deepcopy(profiles_payload())
    payload["phone"] = "600123456789012345678"
    with pytest.raises(ValidationError, match="phone"):
        parse_profiles(payload)


def test_profiles_reject_two_supply_sources() -> None:
    payload = deepcopy(profiles_payload())
    payload["pos"][1]["is_supply_source"] = True
    with pytest.raises(ValidationError, match="is_supply_source"):
        parse_profiles(payload)
