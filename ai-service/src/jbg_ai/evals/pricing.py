"""Cost per query, from a versioned price list. C24.

**Zero is a value that gets recorded, never a blank.** A configuration that calls no paid
provider costs nothing, and printing an empty cell there would read as "not measured" — which
is the opposite of what the table is for. The whole point of the column is that the comparison
between retrieval and putting the catalogue in the prompt is a figure and not an assertion.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from jbg_ai.evals.errors import ConfigurationError
from jbg_ai.evals.golden import GOLDEN_DIR, PRICING_FILE

UNKNOWN = "unknown"


@dataclass(frozen=True)
class PriceList:
    as_of: str
    source: str
    verified: bool
    models: dict[str, dict[str, float]]

    def input_per_token(self, model: str) -> float:
        entry = self.models.get(model)
        if entry is None:
            raise ConfigurationError(
                f"no price for {model!r} in the price list of {self.as_of}. Add it with its "
                "source rather than letting the cost column silently read zero"
            )
        return float(entry.get("input_per_1m_usd", 0.0)) / 1_000_000

    def output_per_token(self, model: str) -> float:
        entry = self.models.get(model) or {}
        return float(entry.get("output_per_1m_usd", 0.0)) / 1_000_000

    def cost(self, model: str, *, input_tokens: int, output_tokens: int = 0) -> float:
        return (
            input_tokens * self.input_per_token(model)
            + output_tokens * self.output_per_token(model)
        )


def load_prices(root: Path | None = None) -> PriceList:
    path = (root or GOLDEN_DIR) / PRICING_FILE
    if not path.is_file():
        raise ConfigurationError(f"{path} does not exist")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return PriceList(
        as_of=str(payload.get("as_of") or UNKNOWN),
        source=str(payload.get("source") or UNKNOWN),
        verified=bool(payload.get("verified", False)) and str(payload.get("as_of")) != UNKNOWN,
        models={str(k): dict(v or {}) for k, v in (payload.get("models") or {}).items()},
    )
