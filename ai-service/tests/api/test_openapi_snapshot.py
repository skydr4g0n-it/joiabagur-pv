"""The committed OpenAPI snapshot is the frozen contract with the .NET side."""

from __future__ import annotations

import json

from jbg_ai.api.main import create_app
from jbg_ai.config import canonical_openapi_settings
from support.paths import OPENAPI_SNAPSHOT


def _committed() -> dict:
    return json.loads(OPENAPI_SNAPSHOT.read_text(encoding="utf-8"))


def _live() -> dict:
    return create_app(canonical_openapi_settings()).openapi()


def test_openapi_snapshot_is_stable() -> None:
    """Regenerate with the README one-liner when this fails — and negotiate first."""
    assert _live() == _committed()


def test_snapshot_comparison_detects_drift() -> None:
    drifted = json.loads(json.dumps(_live()))
    drifted["paths"]["/v1/retrieval/products"]["post"]["operationId"] = "drifted"

    assert drifted != _committed()


def test_snapshot_covers_the_frozen_surface() -> None:
    """The published surface, path by path.

    `/v1/families/suggest` is the ninth and the first addition since the surface was
    frozen in C02. `/v1/families/audit` is the tenth, added by C18b. Both moved the
    boundary on purpose — each is the change that first calls its route — and each
    regenerated the snapshot in the same commit. This list is the second gate: the
    snapshot test alone would go green on a regenerated file without anyone noticing
    a path had appeared.

    The audit is a route of its own rather than a mode of `/suggest` because the two
    read disjoint populations and converge differently: suggestion empties itself as
    batches are approved, while the audit is a standing signal over the families that
    exist. Folding it in would have moved this snapshot just the same.
    """
    paths = _committed()["paths"]

    assert sorted(paths) == [
        "/health",
        "/v1/assist/sale",
        "/v1/enrich/products",
        "/v1/evals/runs",
        "/v1/families/audit",
        "/v1/families/suggest",
        "/v1/index/status",
        "/v1/index/sync",
        "/v1/inventory/propose",
        "/v1/retrieval/products",
        "/v1/retrieval/substitutes",
    ]


def test_interactive_docs_stay_disabled() -> None:
    app = create_app(canonical_openapi_settings())

    assert app.docs_url is None
    assert app.redoc_url is None
