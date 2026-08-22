from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from catalog_pipeline.errors import IngestAborted, IngestError
from catalog_pipeline.models import EnrichedRecord, ProductIdentity
from catalog_pipeline.validate import validate_records

ENV_HOST = "JPV_PGHOST"
ENV_PORT = "JPV_PGPORT"
ENV_DB = "JPV_PGDATABASE"
ENV_USER = "JPV_PGUSER"
ENV_PASSWORD = "JPV_PGPASSWORD"


@dataclass(frozen=True)
class IngestResult:
    updated: int
    unmatched: tuple[str, ...]
    rolled_back: bool = False


class CatalogStore(Protocol):
    def snapshot_by_skus(self, skus: list[str]) -> dict[str, ProductIdentity]: ...

    def begin(self) -> None: ...

    def update_description(self, sku: str, description: str) -> int: ...

    def reread_identity(self, sku: str) -> ProductIdentity: ...

    def row_count(self) -> int: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


def identities_unchanged(before: ProductIdentity, after: ProductIdentity) -> bool:
    return (
        before.id == after.id
        and before.sku == after.sku
        and before.name == after.name
        and before.price == after.price
        and before.collection_id == after.collection_id
    )


def run_ingest(store: CatalogStore, records: list[EnrichedRecord]) -> IngestResult:
    validate_records(records)
    skus = [record.sku for record in records]
    snapshot = store.snapshot_by_skus(skus)
    unmatched = tuple(sku for sku in skus if sku not in snapshot)
    matched = [record for record in records if record.sku in snapshot]
    prior_count = store.row_count()

    store.begin()
    try:
        for record in matched:
            affected = store.update_description(record.sku, record.description)
            if affected != 1:
                raise IngestAborted(f"UPDATE for {record.sku!r} affected {affected} rows.")
        for record in matched:
            current = store.reread_identity(record.sku)
            if not identities_unchanged(snapshot[record.sku], current):
                raise IngestAborted(
                    f"Identity changed after UPDATE for {record.sku!r}: "
                    f"{snapshot[record.sku]} -> {current}"
                )
        if store.row_count() != prior_count:
            raise IngestAborted("Ingest must not insert or delete Products rows.")
        store.commit()
    except Exception:
        store.rollback()
        raise

    return IngestResult(updated=len(matched), unmatched=unmatched, rolled_back=False)


class FakeCatalogStore:
    """In-memory stand-in used when Docker is not available."""

    def __init__(
        self,
        rows: dict[str, dict],
        *,
        tamper_name_on_reread: bool = False,
    ) -> None:
        self.rows = {sku: dict(row) for sku, row in rows.items()}
        self.tamper_name_on_reread = tamper_name_on_reread
        self._tx: dict[str, dict] | None = None
        self.committed = True
        self.insert_attempts = 0

    def snapshot_by_skus(self, skus: list[str]) -> dict[str, ProductIdentity]:
        return {sku: self._identity(sku) for sku in skus if sku in self.rows}

    def begin(self) -> None:
        self._tx = {sku: dict(row) for sku, row in self.rows.items()}
        self.committed = False

    def update_description(self, sku: str, description: str) -> int:
        target = self.rows if self._tx is None else self._tx
        if sku not in target:
            return 0
        target[sku]["description"] = description
        return 1

    def reread_identity(self, sku: str) -> ProductIdentity:
        identity = self._identity(sku, working=True)
        if self.tamper_name_on_reread:
            return ProductIdentity(
                id=identity.id,
                sku=identity.sku,
                name=identity.name + " TAMPERED",
                price=identity.price,
                collection_id=identity.collection_id,
            )
        return identity

    def row_count(self) -> int:
        target = self.rows if self._tx is None else self._tx
        return len(target)

    def commit(self) -> None:
        if self._tx is not None:
            self.rows = self._tx
        self._tx = None
        self.committed = True

    def rollback(self) -> None:
        self._tx = None
        self.committed = False

    def _identity(self, sku: str, *, working: bool = False) -> ProductIdentity:
        target = self._tx if working and self._tx is not None else self.rows
        row = target[sku]
        return ProductIdentity(
            id=str(row["id"]),
            sku=sku,
            name=str(row["name"]),
            price=Decimal(str(row["price"])).quantize(Decimal("0.01")),
            collection_id=row.get("collection_id"),
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
        self._in_tx = False

    def snapshot_by_skus(self, skus: list[str]) -> dict[str, ProductIdentity]:
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
        return {str(row[1]): _row_to_identity(row) for row in rows}

    def begin(self) -> None:
        # psycopg opens a transaction on the first statement when autocommit is off.
        self._in_tx = True

    def update_description(self, sku: str, description: str) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public."Products"
                SET "Description" = %s, "UpdatedAt" = NOW()
                WHERE "SKU" = %s
                """,
                (description, sku),
            )
            return cursor.rowcount

    def reread_identity(self, sku: str) -> ProductIdentity:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT "Id", "SKU", "Name", "Price", "CollectionId"
                FROM public."Products"
                WHERE "SKU" = %s
                """,
                (sku,),
            )
            row = cursor.fetchone()
        if row is None:
            raise IngestAborted(f"SKU {sku!r} disappeared during ingest.")
        return _row_to_identity(row)

    def row_count(self) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM public."Products"')
            return int(cursor.fetchone()[0])

    def commit(self) -> None:
        self.connection.commit()
        self._in_tx = False

    def rollback(self) -> None:
        self.connection.rollback()
        self._in_tx = False


def _row_to_identity(row) -> ProductIdentity:
    collection_id = None if row[4] is None else str(row[4])
    return ProductIdentity(
        id=str(row[0]),
        sku=str(row[1]),
        name=str(row[2]),
        price=Decimal(str(row[3])).quantize(Decimal("0.01")),
        collection_id=collection_id,
    )


def ingest_records(records: list[EnrichedRecord], env: dict[str, str] | None = None) -> IngestResult:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise IngestError("psycopg is required for live ingest.") from exc

    kwargs = pg_connect_kwargs_from_env(env)
    with psycopg.connect(**kwargs) as connection:
        store = PostgresCatalogStore(connection)
        try:
            return run_ingest(store, records)
        except IngestAborted:
            raise
