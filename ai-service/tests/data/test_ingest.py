"""INSERT ingest: new rows only, rollback on collision. Delivered by C06b."""

from __future__ import annotations

import pytest

from jbg_ai.data.briefs import default_briefs
from jbg_ai.data.errors import IngestAborted
from jbg_ai.data.ingest import FakeCatalogStore, run_ingest
from jbg_ai.data.records import SyntheticRecord


def _records() -> list[SyntheticRecord]:
    briefs = default_briefs()
    return [
        SyntheticRecord(
            sku=f"SKU{437 + index}",
            name=f"Pieza {brief.name}",
            description="Plata.",
            price="89.00",
            collection_name=brief.name,
            text_quality_tier="rich",
        )
        for index, brief in enumerate(briefs)
    ]


def test_ingest_inserts_new_products_without_touching_real_skus() -> None:
    real = {
        "SKU01": {
            "id": "real-1",
            "name": "Pendiente real",
            "description": "Antigua",
            "price": "48.00",
            "collection_id": "col-real",
        }
    }
    store = FakeCatalogStore(
        products=real,
        collections={"Colección Biniacolla": "col-real"},
    )
    records = _records()
    result = run_ingest(
        store,
        records,
        real_skus={"SKU01"},
        real_collections={"Colección Biniacolla"},
    )
    assert result.products_inserted == 10
    assert store.products["SKU01"]["name"] == "Pendiente real"
    assert store.products["SKU01"]["price"] == "48.00"
    assert store.products["SKU01"]["description"] == "Antigua"
    assert "SKU437" in store.products
    assert store.products["SKU437"]["is_active"] is True
    assert store.family_counts == (0, 0)


def test_ingest_creates_new_collections_with_unique_names() -> None:
    store = FakeCatalogStore(
        products={
            "SKU01": {
                "id": "real-1",
                "name": "Pendiente real",
                "description": "",
                "price": "48.00",
                "collection_id": "col-real",
            }
        },
        collections={"Colección Biniacolla": "col-real"},
    )
    result = run_ingest(
        store,
        _records(),
        real_skus={"SKU01"},
        real_collections={"Colección Biniacolla"},
    )
    assert result.collections_inserted == 10
    assert "El Jaleo" in store.collections
    assert "Colección Biniacolla" in store.collections
    assert "Hotel" not in store.collections


def test_ingest_leaves_unassigned_products_without_collection() -> None:
    store = FakeCatalogStore()
    records = _records()
    first = records[0]
    records[0] = SyntheticRecord(
        sku=first.sku,
        name=first.name,
        description=first.description,
        price=first.price,
        collection_name="",
        text_quality_tier=first.text_quality_tier,
    )
    result = run_ingest(
        store,
        records,
        real_skus=set(),
        real_collections={"Colección Biniacolla"},
    )
    assert result.collections_inserted == 9
    assert result.products_inserted == 10
    assert store.products[first.sku]["collection_id"] is None
    assert store.products[records[1].sku]["collection_id"] == store.collections[records[1].collection_name]


def test_ingest_rolls_back_on_sku_or_collection_collision() -> None:
    records = _records()
    store = FakeCatalogStore(
        products={
            "SKU437": {
                "id": "existing",
                "name": "Ya existe",
                "description": "",
                "price": "10.00",
                "collection_id": None,
            }
        }
    )
    snapshot_skus = set(store.products)
    snapshot_collections = set(store.collections)
    with pytest.raises(IngestAborted, match="SKU"):
        run_ingest(
            store,
            records,
            real_skus=set(),
            real_collections=set(),
        )
    assert set(store.products) == snapshot_skus
    assert set(store.collections) == snapshot_collections
    assert store.committed is True or store._tx_products is None

    store = FakeCatalogStore(collections={"El Jaleo": "taken"})
    snapshot_collections = set(store.collections)
    with pytest.raises(IngestAborted, match="Collection"):
        run_ingest(
            store,
            records,
            real_skus=set(),
            real_collections=set(),
        )
    assert set(store.collections) == snapshot_collections
