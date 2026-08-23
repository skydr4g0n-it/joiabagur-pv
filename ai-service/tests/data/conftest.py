"""C06b data tests stay offline."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_provider_network(forbid_network: None) -> None:
    """Any socket in tests/data/ is a failure (plan §1)."""
    return None
