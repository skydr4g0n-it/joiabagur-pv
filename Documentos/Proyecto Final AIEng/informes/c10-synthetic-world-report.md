# C10 — Informe del mundo sintético (POS, inventario, ventas)

Perfiles: [`data/world/pos-profiles.yaml`](../../../data/world/pos-profiles.yaml)
CLI: [`ai-service/src/jbg_ai/data/`](../../../ai-service/src/jbg_ai/data/README.md)
`generator_version`: `c10-world/v1` · semilla: `20260823` · horizonte: **16** meses (`2025-04-23` … `2026-08-23`)
`generated_at` (sidecar local, gitignored): `2026-08-23T17:29:17Z`

El JSONL de ventas y el `pg_dump` **no** están en git. La receta commiteada es el YAML. No hay test de bit-identidad: los invariantes (stock no negativo, picos, pareja venta↔movimiento) viven en pytest.

`is_supply_source` existe **solo** en el YAML (`MAO-TALLER`). La columna SQL es C19. Cero escrituras al schema `ai`. Cero LLM.

## Recuentos (simulate + ingest Docker `:5433` / `joiabagur_pv`)

| Métrica | Valor | Banda |
|---|---|---|
| POS | **12** | 12 del censo |
| Inventario | **6.720** | 6.500–8.000 |
| Ventas | **22.961** | 15.000–25.000 |
| Movimientos | **29.681** (6.720 Import + 22.961 Sale) | cuadran con stock |
| Pares de co-ocurrencia (JSONL efímero) | **4.075** | solo `BulkOperationId` |
| Operadores | **3** | `op-ciutadella`, `op-fornells`, `op-aeroport` |
| `UserPointOfSales` | **3** | una POS cada uno |
| `PointOfSalePaymentMethods` | **66** (11 × 6) | Artrutx = 0 |
| `"Products"` / `"Collections"` | **1.200** / **38** | intactos |

Huecos del ancla real **no** vendidos: `SKU135`, `SKU400`, `SKU418`.

## Censo POS

| Code | Nombre | Extra |
|---|---|---|
| `MAO-TALLER` | Taller Joia Bagur, Maó | único `is_supply_source` (YAML); λ retail ~0 |
| `CIU-CENTRE` | Ciutadella Centre | operador `op-ciutadella` |
| `MAO-AIR` | Aeroport de Menorca | operador `op-aeroport`; precio manual |
| `FORNELLS` | Fornells | operador `op-fornells`; estacionalidad extrema |
| `BINIBECA` | Boutique Binibeca | |
| `HT-GALDANA` | Hotel Cala Galdana | precio manual |
| `HT-SONBOU` | Hotel Son Bou | precio manual |
| `PORT-MAO` | Estació Marítima, Maó | |
| `PALMA-JAIME3` | Palma Jaume III | |
| `EIV-MARINA` | Eivissa Marina | precio manual |
| `HT-ALCUDIA` | Hotel Alcúdia | precio manual |
| `HT-ARTRUTX` | Hotel Cap d'Artrutx | `IsActive=false`; `closed_after` 2025-09-30; sin pagos; sin operador |

Teléfono de todos: `600123456`.

## Operadores de demo (no son secretos de producción)

| Username | Nombre | POS | Password |
|---|---|---|---|
| `op-ciutadella` | Catalina Pons | `CIU-CENTRE` | `Operator123!` |
| `op-fornells` | Joan Marí | `FORNELLS` | `Operator123!` |
| `op-aeroport` | Marta Soler | `MAO-AIR` | `Operator123!` |

`Role` = `Operator` (string EF). Hash BCrypt work factor **12**, prefijo `$2a$` (compatible con BCrypt.Net). El resto de ventas históricas llevan el `admin` existente. Login local comprobado contra el hash generado en ingest.

## Backup

Dump local (gitignored): `data/world/backups/c10-world.sql`.

```powershell
docker exec jpv-pv-postgres pg_dump -U postgres joiabagur_pv > data/world/backups/c10-world.sql
Get-Content data/world/backups/c10-world.sql | docker exec -i jpv-pv-postgres psql -U postgres -d joiabagur_pv
```

Rehydrate = restore. Un segundo `world ingest` aborta si los códigos del censo ya existen.

## Fuera de este change

C19 (`IsSupplySource` SQL, señales), C22 (`ai.pos_projection`), C27 (`ai.co_occurrence` persistida), OpenAPI, RDS, LLM, seeder .NET.
