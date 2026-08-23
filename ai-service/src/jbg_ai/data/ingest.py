"""INSERT new collections and products; never touch real SKUs. Delivered by C06b."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from jbg_ai.data.errors import IngestAborted, IngestError
from jbg_ai.data.records import SyntheticRecord
from jbg_ai.data.validate import validate_records

ENV_HOST = "JPV_PGHOST"
ENV_PORT = "JPV_PGPORT"
ENV_DB = "JPV_PGDATABASE"
ENV_USER = "JPV_PGUSER"
ENV_PASSWORD = "JPV_PGPASSWORD"


@dataclass(frozen=True)
class ProductSnapshot:
    id: str
    sku: str
    name: str
    price: Decimal
    collection_id: str | None


@dataclass(frozen=True)
class IngestResult:
    collections_inserted: int
    products_inserted: int
    rolled_back: bool = False


class CatalogStore(Protocol):
    def existing_skus(self) -> set[str]: ...

    def existing_collection_names(self) -> set[str]: ...

    def snapshot_products(self, skus: list[str]) -> dict[str, ProductSnapshot]: ...

    def family_row_counts(self) -> tuple[int, int]: ...

    def begin(self) -> None: ...

    def insert_collection(self, name: str) -> str: ...

    def insert_product(
        self,
        *,
        sku: str,
        name: str,
        description: str,
        price: str,
        collection_id: str | None,
    ) -> str: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


def run_ingest(
    store: CatalogStore,
    records: list[SyntheticRecord],
    *,
    real_skus: set[str],
    real_collections: set[str],
) -> IngestResult:
    validate_records(records, real_skus=real_skus, real_collections=real_collections)
    existing_skus = {sku.casefold() for sku in store.existing_skus()}
    existing_collections = {name.casefold() for name in store.existing_collection_names()}
    family_before = store.family_row_counts()
    real_snapshot = store.snapshot_products(sorted(real_skus))

    colliding_skus = [record.sku for record in records if record.sku.casefold() in existing_skus]
    if colliding_skus:
        raise IngestAborted(f"Synthetic SKU already exists: {colliding_skus[0]!r}.")

    collection_names = {record.collection_name.strip() for record in records if record.collection_name.strip()}
    colliding_names = [name for name in collection_names if name.casefold() in existing_collections]
    if colliding_names:
        raise IngestAborted(f"Collection name already exists: {colliding_names[0]!r}.")

    store.begin()
    try:
        collection_ids: dict[str, str] = {}
        for name in sorted(collection_names):
            collection_ids[name] = store.insert_collection(name)
        for record in records:
            assigned = record.collection_name.strip()
            store.insert_product(
                sku=record.sku,
                name=record.name,
                description=record.description,
                price=record.price,
                collection_id=collection_ids[assigned] if assigned else None,
            )
        after_real = store.snapshot_products(sorted(real_skus))
        if after_real != real_snapshot:
            raise IngestAborted("Ingest mutated a real product row.")
        if store.family_row_counts() != family_before:
            raise IngestAborted("Ingest must not write ProductFamily tables.")
        store.commit()
    except Exception:
        store.rollback()
        raise

    return IngestResult(
        collections_inserted=len(collection_names),
        products_inserted=len(records),
        rolled_back=False,
    )


class FakeCatalogStore:
    """In-memory stand-in used when Docker is not available."""

    def __init__(
        self,
        *,
        products: dict[str, dict] | None = None,
        collections: dict[str, str] | None = None,
        family_counts: tuple[int, int] = (0, 0),
    ) -> None:
        self.products = {sku: dict(row) for sku, row in (products or {}).items()}
        self.collections = dict(collections or {})
        self.family_counts = family_counts
        self._tx_products: dict[str, dict] | None = None
        self._tx_collections: dict[str, str] | None = None
        self.committed = True
        self.update_attempts = 0

    def existing_skus(self) -> set[str]:
        return set(self._working_products())

    def existing_collection_names(self) -> set[str]:
        return set(self._working_collections())

    def snapshot_products(self, skus: list[str]) -> dict[str, ProductSnapshot]:
        target = self._working_products()
        return {sku: self._snapshot(sku, target[sku]) for sku in skus if sku in target}

    def family_row_counts(self) -> tuple[int, int]:
        return self.family_counts

    def begin(self) -> None:
        self._tx_products = {sku: dict(row) for sku, row in self.products.items()}
        self._tx_collections = dict(self.collections)
        self.committed = False

    def insert_collection(self, name: str) -> str:
        target = self._working_collections()
        if name in target:
            raise IngestAborted(f"Collection name already exists: {name!r}.")
        new_id = str(uuid.uuid4())
        target[name] = new_id
        return new_id

    def insert_product(
        self,
        *,
        sku: str,
        name: str,
        description: str,
        price: str,
        collection_id: str | None,
    ) -> str:
        target = self._working_products()
        if sku in target:
            raise IngestAborted(f"SKU already exists: {sku!r}.")
        new_id = str(uuid.uuid4())
        target[sku] = {
            "id": new_id,
            "name": name,
            "description": description,
            "price": price,
            "collection_id": collection_id,
            "is_active": True,
        }
        return new_id

    def commit(self) -> None:
        if self._tx_products is not None:
            self.products = self._tx_products
        if self._tx_collections is not None:
            self.collections = self._tx_collections
        self._tx_products = None
        self._tx_collections = None
        self.committed = True

    def rollback(self) -> None:
        self._tx_products = None
        self._tx_collections = None
        self.committed = False

    def _working_products(self) -> dict[str, dict]:
        return self.products if self._tx_products is None else self._tx_products

    def _working_collections(self) -> dict[str, str]:
        return self.collections if self._tx_collections is None else self._tx_collections

    @staticmethod
    def _snapshot(sku: str, row: dict) -> ProductSnapshot:
        return ProductSnapshot(
            id=str(row["id"]),
            sku=sku,
            name=str(row["name"]),
            price=Decimal(str(row["price"])).quantize(Decimal("0.01")),
            collection_id=None if row.get("collection_id") is None else str(row["collection_id"]),
        )


def pg_connect_kwargs_from_env(env: dict[str, str] | None = None) -> dict[str, str]:
    source = os.environ if env is None else env
    missing = [name for name in (ENV_HOST, ENV_PORT, ENV_DB, ENV_USER, ENV_PASSWORD) if not source.get(name)]
    if missing:
        raise IngestError("Missing environment variables: " + ", ".join(missing))
    return {
        "host": source[ENV_HOST],
        "port": source[ENV_PORT],
        "dbname": source[ENV_DB],
        "user": source[ENV_USER],
        "password": source[ENV_PASSWORD],
    }


class PostgresCatalogStore:
    def __init__(self, connection) -> None:
        self.connection = connection

    def existing_skus(self) -> set[str]:
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT "SKU" FROM public."Products"')
            return {str(row[0]) for row in cursor.fetchall()}

    def existing_collection_names(self) -> set[str]:
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT "Name" FROM public."Collections"')
            return {str(row[0]) for row in cursor.fetchall()}

    def snapshot_products(self, skus: list[str]) -> dict[str, ProductSnapshot]:
        if not skus:
            return {}
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT "Id", "SKU", "Name", "Price", "CollectionId"
                FROM public."Products"
                WHERE "SKU" = ANY(%s)
                """,
                (skus,),
            )
            rows = cursor.fetchall()
        return {str(row[1]): _row_to_snapshot(row) for row in rows}

    def family_row_counts(self) -> tuple[int, int]:
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM public."ProductFamilies"')
            families = int(cursor.fetchone()[0])
            cursor.execute('SELECT COUNT(*) FROM public."ProductFamilyMembers"')
            members = int(cursor.fetchone()[0])
        return families, members

    def begin(self) -> None:
        return None

    def insert_collection(self, name: str) -> str:
        new_id = uuid.uuid4()
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public."Collections" ("Id", "Name", "CreatedAt", "UpdatedAt")
                VALUES (%s, %s, NOW(), NOW())
                """,
                (new_id, name),
            )
        return str(new_id)

    def insert_product(
        self,
        *,
        sku: str,
        name: str,
        description: str,
        price: str,
        collection_id: str | None,
    ) -> str:
        new_id = uuid.uuid4()
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public."Products"
                    ("Id", "SKU", "Name", "Description", "Price", "CollectionId",
                     "IsActive", "CreatedAt", "UpdatedAt")
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                """,
                (
                    new_id,
                    sku,
                    name,
                    description,
                    Decimal(price),
                    None if collection_id is None else UUID(collection_id),
                ),
            )
        return str(new_id)

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()


def _row_to_snapshot(row) -> ProductSnapshot:
    return ProductSnapshot(
        id=str(row[0]),
        sku=str(row[1]),
        name=str(row[2]),
        price=Decimal(str(row[3])).quantize(Decimal("0.01")),
        collection_id=None if row[4] is None else str(row[4]),
    )


def ingest_records(
    records: list[SyntheticRecord],
    *,
    real_skus: set[str],
    real_collections: set[str],
    env: dict[str, str] | None = None,
) -> IngestResult:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise IngestError("psycopg is required for live ingest.") from exc

    kwargs = pg_connect_kwargs_from_env(env)
    with psycopg.connect(**kwargs) as connection:
        store = PostgresCatalogStore(connection)
        return run_ingest(
            store,
            records,
            real_skus=real_skus,
            real_collections=real_collections,
        )
