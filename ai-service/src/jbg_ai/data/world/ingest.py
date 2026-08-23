"""Transactional world ingest. Natural keys in, UUIDs minted here. Never touches catalog."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from jbg_ai.data.errors import IngestAborted, IngestError
from jbg_ai.data.ingest import pg_connect_kwargs_from_env
from jbg_ai.data.world.constants import (
    ADMIN_USERNAME,
    BCRYPT_PREFIX,
    BCRYPT_ROUNDS,
    CLOSED_HOTEL_CODE,
    CENSUS_CODES,
    GENERATED_DIR,
    INVENTORIES_FILENAME,
    MOVEMENT_IMPORT,
    MOVEMENT_SALE,
    MOVEMENTS_FILENAME,
    OPERATOR_ROLE,
    PAYMENT_CODES,
    SALES_FILENAME,
)
from jbg_ai.data.world.profiles import load_profiles
from jbg_ai.data.world.records import (
    InventoryRow,
    MovementRow,
    SaleRow,
    WorldProfiles,
)


def hash_operator_password(password: str) -> str:
    import bcrypt

    hashed = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=BCRYPT_ROUNDS, prefix=BCRYPT_PREFIX),
    )
    return hashed.decode("ascii")


def password_matches(password: str, hashed: str) -> bool:
    import bcrypt

    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))


@dataclass(frozen=True)
class ProductRef:
    id: str
    sku: str
    price: Decimal


@dataclass(frozen=True)
class IngestCounts:
    pos: int
    users: int
    user_pos: int
    payments: int
    inventories: int
    sales: int
    movements: int
    rolled_back: bool = False


class WorldStore(Protocol):
    def begin(self) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def existing_pos_codes(self) -> set[str]: ...

    def product_map(self) -> dict[str, ProductRef]: ...

    def snapshot_product_skus(self) -> dict[str, tuple[str, str]]: ...

    def collection_names(self) -> set[str]: ...

    def family_row_counts(self) -> tuple[int, int]: ...

    def ai_row_count(self) -> int: ...

    def admin_user_id(self) -> str: ...

    def payment_method_ids(self) -> dict[str, str]: ...

    def insert_pos(
        self,
        *,
        code: str,
        name: str,
        address: str,
        phone: str,
        is_active: bool,
        allow_manual_price_edit: bool,
        created_at: datetime,
    ) -> str: ...

    def insert_user(
        self,
        *,
        username: str,
        password_hash: str,
        first_name: str,
        last_name: str,
        created_at: datetime,
    ) -> str: ...

    def insert_user_pos(
        self, *, user_id: str, pos_id: str, assigned_at: datetime
    ) -> None: ...

    def insert_pos_payments(
        self, *, pos_id: str, payment_ids: list[str], created_at: datetime
    ) -> int: ...

    def insert_inventories(self, rows: list[dict[str, Any]]) -> dict[tuple[str, str], str]: ...

    def insert_sales(self, rows: list[dict[str, Any]]) -> None: ...

    def insert_movements(self, rows: list[dict[str, Any]]) -> None: ...


def _parse_ts(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def load_generated(directory: Path) -> tuple[list[InventoryRow], list[SaleRow], list[MovementRow]]:
    inventories = [
        InventoryRow(
            sku=row["sku"],
            pos_code=row["pos_code"],
            quantity=int(row["quantity"]),
            is_active=bool(row["is_active"]),
            last_updated_at=row["last_updated_at"],
        )
        for row in _read_jsonl(directory / INVENTORIES_FILENAME)
    ]
    sales = [
        SaleRow(
            sale_key=row["sale_key"],
            sku=row["sku"],
            pos_code=row["pos_code"],
            username=row["username"],
            quantity=int(row["quantity"]),
            occurred_at=row["occurred_at"],
            bulk_operation_id=row.get("bulk_operation_id"),
            payment_method_code=row["payment_method_code"],
            price_was_overridden=bool(row.get("price_was_overridden", False)),
            notes=row.get("notes"),
            search_event_id=row.get("search_event_id"),
        )
        for row in _read_jsonl(directory / SALES_FILENAME)
    ]
    movements = [
        MovementRow(
            sku=row["sku"],
            pos_code=row["pos_code"],
            username=row["username"],
            movement_type=int(row["movement_type"]),
            quantity_change=int(row["quantity_change"]),
            quantity_before=int(row["quantity_before"]),
            quantity_after=int(row["quantity_after"]),
            occurred_at=row["occurred_at"],
            sale_key=row.get("sale_key"),
            reason=row.get("reason"),
        )
        for row in _read_jsonl(directory / MOVEMENTS_FILENAME)
    ]
    return inventories, sales, movements


def run_ingest(
    store: WorldStore,
    profiles: WorldProfiles,
    inventories: list[InventoryRow],
    sales: list[SaleRow],
    movements: list[MovementRow],
    *,
    hash_password=hash_operator_password,
) -> IngestCounts:
    existing = store.existing_pos_codes()
    colliding = [code for code in CENSUS_CODES if code in existing]
    if colliding:
        raise IngestAborted(f"World POS already present: {colliding[0]}. Restore a dump instead of re-ingest.")

    now = datetime.now(timezone.utc)
    payments = 0

    store.begin()
    try:
        product_map = store.product_map()
        needed = {row.sku for row in inventories} | {row.sku for row in sales}
        unmatched = sorted(sku for sku in needed if sku not in product_map)
        if unmatched:
            raise IngestAborted("Unmatched SKUs: " + ", ".join(unmatched[:20]))

        products_before = store.snapshot_product_skus()
        collections_before = store.collection_names()
        families_before = store.family_row_counts()
        ai_before = store.ai_row_count()
        admin_id = store.admin_user_id()
        pay_ids = store.payment_method_ids()
        missing_pay = [code for code in PAYMENT_CODES if code not in pay_ids]
        if missing_pay:
            raise IngestAborted("Missing payment methods: " + ", ".join(missing_pay))
        pos_ids: dict[str, str] = {}
        for pos in profiles.pos:
            pos_ids[pos.code] = store.insert_pos(
                code=pos.code,
                name=pos.name,
                address=pos.address,
                phone=profiles.phone,
                is_active=pos.is_active,
                allow_manual_price_edit=pos.allow_manual_price_edit,
                created_at=now,
            )

        user_ids: dict[str, str] = {ADMIN_USERNAME: admin_id}
        for operator in profiles.operators:
            user_ids[operator.username] = store.insert_user(
                username=operator.username,
                password_hash=hash_password(operator.password),
                first_name=operator.first_name,
                last_name=operator.last_name,
                created_at=now,
            )
            store.insert_user_pos(
                user_id=user_ids[operator.username],
                pos_id=pos_ids[operator.pos_code],
                assigned_at=now,
            )

        payments = 0
        for pos in profiles.pos:
            if pos.code == CLOSED_HOTEL_CODE:
                continue
            payments += store.insert_pos_payments(
                pos_id=pos_ids[pos.code],
                payment_ids=[pay_ids[code] for code in PAYMENT_CODES],
                created_at=now,
            )

        inventory_payload = []
        for row in inventories:
            stamp = _parse_ts(row.last_updated_at)
            inventory_payload.append(
                {
                    "id": str(uuid.uuid4()),
                    "product_id": product_map[row.sku].id,
                    "pos_id": pos_ids[row.pos_code],
                    "sku": row.sku,
                    "pos_code": row.pos_code,
                    "quantity": row.quantity,
                    "is_active": row.is_active,
                    "last_updated_at": stamp,
                    "created_at": stamp,
                    "updated_at": stamp,
                }
            )
        inventory_ids = store.insert_inventories(inventory_payload)

        bulk_ids: dict[str, str] = {}
        sales_payload = []
        sale_ids: dict[str, str] = {}
        for row in sales:
            sale_id = str(uuid.uuid4())
            sale_ids[row.sale_key] = sale_id
            bulk = None
            if row.bulk_operation_id:
                bulk = bulk_ids.setdefault(row.bulk_operation_id, str(uuid.uuid4()))
            stamp = _parse_ts(row.occurred_at)
            user_id = user_ids.get(row.username)
            if user_id is None:
                raise IngestAborted(f"Unknown username {row.username!r}.")
            sales_payload.append(
                {
                    "id": sale_id,
                    "product_id": product_map[row.sku].id,
                    "pos_id": pos_ids[row.pos_code],
                    "user_id": user_id,
                    "payment_method_id": pay_ids[row.payment_method_code],
                    "price": product_map[row.sku].price,
                    "quantity": row.quantity,
                    "notes": None,
                    "price_was_overridden": False,
                    "original_product_price": None,
                    "bulk_operation_id": bulk,
                    "search_event_id": None,
                    "sale_date": stamp,
                    "created_at": stamp,
                    "updated_at": stamp,
                }
            )
        store.insert_sales(sales_payload)

        movement_payload = []
        for row in movements:
            stamp = _parse_ts(row.occurred_at)
            user_id = user_ids.get(row.username, admin_id)
            if row.movement_type == MOVEMENT_IMPORT:
                user_id = admin_id
            sale_id = sale_ids.get(row.sale_key) if row.sale_key else None
            movement_payload.append(
                {
                    "id": str(uuid.uuid4()),
                    "inventory_id": inventory_ids[(row.pos_code, row.sku)],
                    "sale_id": sale_id,
                    "user_id": user_id,
                    "movement_type": row.movement_type,
                    "quantity_change": row.quantity_change,
                    "quantity_before": row.quantity_before,
                    "quantity_after": row.quantity_after,
                    "reason": row.reason,
                    "movement_date": stamp,
                    "created_at": stamp,
                    "updated_at": stamp,
                }
            )
        store.insert_movements(movement_payload)

        if store.snapshot_product_skus() != products_before:
            raise IngestAborted("Ingest mutated Products.")
        if store.collection_names() != collections_before:
            raise IngestAborted("Ingest mutated Collections.")
        if store.family_row_counts() != families_before:
            raise IngestAborted("Ingest wrote ProductFamily tables.")
        if store.ai_row_count() != ai_before:
            raise IngestAborted("Ingest wrote schema ai.")

        store.commit()
    except Exception:
        store.rollback()
        raise

    return IngestCounts(
        pos=len(profiles.pos),
        users=len(profiles.operators),
        user_pos=len(profiles.operators),
        payments=payments,
        inventories=len(inventories),
        sales=len(sales),
        movements=len(movements),
    )


class FakeWorldStore:
    def __init__(
        self,
        *,
        products: dict[str, dict] | None = None,
        collections: set[str] | None = None,
        family_counts: tuple[int, int] = (0, 0),
        ai_rows: int = 0,
        existing_codes: set[str] | None = None,
        admin_id: str = "admin-id",
        payment_ids: dict[str, str] | None = None,
    ) -> None:
        self.products = {sku: dict(row) for sku, row in (products or {}).items()}
        self.collections = set(collections or ())
        self.family_counts = family_counts
        self.ai_rows = ai_rows
        self._existing_codes = set(existing_codes or ())
        self._admin_id = admin_id
        self._payment_ids = payment_ids or {code: f"pm-{code}" for code in PAYMENT_CODES}
        self.pos: dict[str, dict] = {}
        self.users: dict[str, dict] = {}
        self.user_pos: list[dict] = []
        self.pos_payments: list[dict] = []
        self.inventories: dict[tuple[str, str], dict] = {}
        self.sales: list[dict] = []
        self.movements: list[dict] = []
        self._tx: dict[str, Any] | None = None
        self.committed = True
        self.product_writes = 0
        self.collection_writes = 0

    def begin(self) -> None:
        self._tx = {
            "pos": dict(self.pos),
            "users": dict(self.users),
            "user_pos": list(self.user_pos),
            "pos_payments": list(self.pos_payments),
            "inventories": dict(self.inventories),
            "sales": list(self.sales),
            "movements": list(self.movements),
            "products": {sku: dict(row) for sku, row in self.products.items()},
            "collections": set(self.collections),
        }
        self.committed = False

    def commit(self) -> None:
        if self._tx is not None:
            self.products = self._tx["products"]
            self.collections = self._tx["collections"]
        self._tx = None
        self.committed = True

    def rollback(self) -> None:
        if self._tx is not None:
            self.pos = self._tx["pos"]
            self.users = self._tx["users"]
            self.user_pos = self._tx["user_pos"]
            self.pos_payments = self._tx["pos_payments"]
            self.inventories = self._tx["inventories"]
            self.sales = self._tx["sales"]
            self.movements = self._tx["movements"]
        self._tx = None
        self.committed = False

    def existing_pos_codes(self) -> set[str]:
        return set(self._existing_codes) | set(self.pos)

    def product_map(self) -> dict[str, ProductRef]:
        return {
            sku: ProductRef(id=str(row["id"]), sku=sku, price=Decimal(str(row["price"])))
            for sku, row in self.products.items()
        }

    def snapshot_product_skus(self) -> dict[str, tuple[str, str]]:
        target = self._working_products()
        return {sku: (str(row.get("name")), str(row.get("price"))) for sku, row in target.items()}

    def collection_names(self) -> set[str]:
        return set(self._working_collections())

    def family_row_counts(self) -> tuple[int, int]:
        return self.family_counts

    def ai_row_count(self) -> int:
        return self.ai_rows

    def admin_user_id(self) -> str:
        return self._admin_id

    def payment_method_ids(self) -> dict[str, str]:
        return dict(self._payment_ids)

    def insert_pos(self, **kwargs) -> str:
        new_id = str(uuid.uuid4())
        self.pos[kwargs["code"]] = {"id": new_id, **kwargs}
        return new_id

    def insert_user(self, **kwargs) -> str:
        new_id = str(uuid.uuid4())
        self.users[kwargs["username"]] = {"id": new_id, "role": OPERATOR_ROLE, **kwargs}
        return new_id

    def insert_user_pos(self, **kwargs) -> None:
        self.user_pos.append(dict(kwargs))

    def insert_pos_payments(self, *, pos_id: str, payment_ids: list[str], created_at: datetime) -> int:
        for payment_id in payment_ids:
            self.pos_payments.append(
                {"pos_id": pos_id, "payment_id": payment_id, "created_at": created_at, "is_active": True}
            )
        return len(payment_ids)

    def insert_inventories(self, rows: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
        ids: dict[tuple[str, str], str] = {}
        for row in rows:
            key = (row["pos_code"], row["sku"])
            self.inventories[key] = row
            ids[key] = row["id"]
        return ids

    def insert_sales(self, rows: list[dict[str, Any]]) -> None:
        self.sales.extend(rows)

    def insert_movements(self, rows: list[dict[str, Any]]) -> None:
        self.movements.extend(rows)

    def _working_products(self) -> dict[str, dict]:
        if self._tx is not None:
            return self._tx["products"]
        return self.products

    def _working_collections(self) -> set[str]:
        if self._tx is not None:
            return self._tx["collections"]
        return self.collections


class PostgresWorldStore:
    def __init__(self, connection) -> None:
        self.connection = connection

    def begin(self) -> None:
        return None

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def existing_pos_codes(self) -> set[str]:
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT "Code" FROM public."PointOfSales"')
            return {str(row[0]) for row in cursor.fetchall()}

    def product_map(self) -> dict[str, ProductRef]:
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT "Id", "SKU", "Price" FROM public."Products"')
            return {
                str(row[1]): ProductRef(id=str(row[0]), sku=str(row[1]), price=Decimal(str(row[2])))
                for row in cursor.fetchall()
            }

    def snapshot_product_skus(self) -> dict[str, tuple[str, str]]:
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT "SKU", "Name", "Price" FROM public."Products"')
            return {str(row[0]): (str(row[1]), str(row[2])) for row in cursor.fetchall()}

    def collection_names(self) -> set[str]:
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT "Name" FROM public."Collections"')
            return {str(row[0]) for row in cursor.fetchall()}

    def family_row_counts(self) -> tuple[int, int]:
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM public."ProductFamilies"')
            families = int(cursor.fetchone()[0])
            cursor.execute('SELECT COUNT(*) FROM public."ProductFamilyMembers"')
            members = int(cursor.fetchone()[0])
        return families, members

    def ai_row_count(self) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM information_schema.schemata
                WHERE schema_name = 'ai'
                """
            )
            if int(cursor.fetchone()[0]) == 0:
                return 0
            cursor.execute(
                """
                SELECT COALESCE(SUM(n_live_tup), 0)
                FROM pg_stat_user_tables
                WHERE schemaname = 'ai'
                """
            )
            return int(cursor.fetchone()[0])

    def admin_user_id(self) -> str:
        with self.connection.cursor() as cursor:
            cursor.execute(
                'SELECT "Id" FROM public."Users" WHERE "Username" = %s',
                (ADMIN_USERNAME,),
            )
            row = cursor.fetchone()
        if row is None:
            raise IngestAborted("admin user is missing.")
        return str(row[0])

    def payment_method_ids(self) -> dict[str, str]:
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT "Code", "Id" FROM public."PaymentMethods"')
            return {str(row[0]): str(row[1]) for row in cursor.fetchall()}

    def insert_pos(self, **kwargs) -> str:
        new_id = uuid.uuid4()
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public."PointOfSales"
                    ("Id", "Name", "Code", "Address", "Phone", "Email",
                     "IsActive", "AllowManualPriceEdit", "CreatedAt", "UpdatedAt")
                VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, %s, %s)
                """,
                (
                    new_id,
                    kwargs["name"],
                    kwargs["code"],
                    kwargs["address"],
                    kwargs["phone"],
                    kwargs["is_active"],
                    kwargs["allow_manual_price_edit"],
                    kwargs["created_at"],
                    kwargs["created_at"],
                ),
            )
        return str(new_id)

    def insert_user(self, **kwargs) -> str:
        new_id = uuid.uuid4()
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public."Users"
                    ("Id", "Username", "PasswordHash", "FirstName", "LastName",
                     "Email", "Role", "IsActive", "LastLoginAt", "CreatedAt", "UpdatedAt")
                VALUES (%s, %s, %s, %s, %s, NULL, %s, TRUE, NULL, %s, %s)
                """,
                (
                    new_id,
                    kwargs["username"],
                    kwargs["password_hash"],
                    kwargs["first_name"],
                    kwargs["last_name"],
                    OPERATOR_ROLE,
                    kwargs["created_at"],
                    kwargs["created_at"],
                ),
            )
        return str(new_id)

    def insert_user_pos(self, *, user_id: str, pos_id: str, assigned_at: datetime) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public."UserPointOfSales"
                    ("Id", "UserId", "PointOfSaleId", "IsActive", "AssignedAt",
                     "UnassignedAt", "CreatedAt", "UpdatedAt")
                VALUES (%s, %s, %s, TRUE, %s, NULL, %s, %s)
                """,
                (uuid.uuid4(), UUID(user_id), UUID(pos_id), assigned_at, assigned_at, assigned_at),
            )

    def insert_pos_payments(self, *, pos_id: str, payment_ids: list[str], created_at: datetime) -> int:
        rows = [
            (uuid.uuid4(), UUID(pos_id), UUID(payment_id), True, None, created_at, created_at)
            for payment_id in payment_ids
        ]
        with self.connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO public."PointOfSalePaymentMethods"
                    ("Id", "PointOfSaleId", "PaymentMethodId", "IsActive",
                     "DeactivatedAt", "CreatedAt", "UpdatedAt")
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
        return len(rows)

    def insert_inventories(self, rows: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
        payload = [
            (
                UUID(row["id"]),
                UUID(row["product_id"]),
                UUID(row["pos_id"]),
                row["quantity"],
                row["is_active"],
                row["last_updated_at"],
                row["created_at"],
                row["updated_at"],
            )
            for row in rows
        ]
        with self.connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO public."Inventories"
                    ("Id", "ProductId", "PointOfSaleId", "Quantity", "IsActive",
                     "LastUpdatedAt", "CreatedAt", "UpdatedAt")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                payload,
            )
        return {(row["pos_code"], row["sku"]): row["id"] for row in rows}

    def insert_sales(self, rows: list[dict[str, Any]]) -> None:
        payload = [
            (
                UUID(row["id"]),
                UUID(row["product_id"]),
                UUID(row["pos_id"]),
                UUID(row["user_id"]),
                UUID(row["payment_method_id"]),
                row["price"],
                row["quantity"],
                None,
                False,
                None,
                None if row["bulk_operation_id"] is None else UUID(row["bulk_operation_id"]),
                None,
                row["sale_date"],
                row["created_at"],
                row["updated_at"],
            )
            for row in rows
        ]
        with self.connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO public."Sales"
                    ("Id", "ProductId", "PointOfSaleId", "UserId", "PaymentMethodId",
                     "Price", "Quantity", "Notes", "PriceWasOverridden",
                     "OriginalProductPrice", "BulkOperationId", "SearchEventId",
                     "SaleDate", "CreatedAt", "UpdatedAt")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                payload,
            )

    def insert_movements(self, rows: list[dict[str, Any]]) -> None:
        payload = [
            (
                UUID(row["id"]),
                UUID(row["inventory_id"]),
                None if row["sale_id"] is None else UUID(row["sale_id"]),
                UUID(row["user_id"]),
                row["movement_type"],
                row["quantity_change"],
                row["quantity_before"],
                row["quantity_after"],
                row["reason"],
                row["movement_date"],
                row["created_at"],
                row["updated_at"],
            )
            for row in rows
        ]
        with self.connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO public."InventoryMovements"
                    ("Id", "InventoryId", "SaleId", "ReturnId", "UserId",
                     "MovementType", "QuantityChange", "QuantityBefore",
                     "QuantityAfter", "Reason", "MovementDate", "CreatedAt", "UpdatedAt")
                VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                payload,
            )


def ingest_world(
    *,
    profiles_path: Path,
    generated_dir: Path | None = None,
    env: dict[str, str] | None = None,
) -> IngestCounts:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise IngestError("psycopg is required for live ingest.") from exc

    profiles = load_profiles(profiles_path)
    inventories, sales, movements = load_generated(generated_dir or GENERATED_DIR)
    kwargs = pg_connect_kwargs_from_env(env)
    with psycopg.connect(**kwargs) as connection:
        store = PostgresWorldStore(connection)
        return run_ingest(store, profiles, inventories, sales, movements)
