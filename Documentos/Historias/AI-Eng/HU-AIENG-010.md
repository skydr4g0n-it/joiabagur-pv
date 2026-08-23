# HU-AIENG-010: Simulador de mundo sintético — POS, inventario e histórico de ventas coherentes con el catálogo local

## Formato estándar

Como **desarrollador del proyecto**, quiero **simular una red de puntos de venta, un inventario sesgado por perfil y un histórico de ventas coherente con el catálogo local de ~1.200 SKUs, versionar los perfiles y cargarlo en la base Docker** **para** **que C19, C22, C27, C29 y C33 tengan señales que no sean cero, sin convertir el simulador en un servicio de la aplicación Joiabagur ni en un endpoint de `jbg-ai`**.

---

## Descripción

Change OpenSpec `add-synthetic-world-simulator` / **C10**, épica **EP12 — Corpus y Enriquecimiento del Catálogo**. Marcado 🟢. Prerrequisito de la ficha: **C06a** (archivado). En la práctica el generate se engancha al catálogo **ya ingerido** por C06a+C06b (`public."Products"` = 1.200). Desbloquea **C19** (señales de demanda), **C22** (proyección POS), **C27** (complementarios por co-ocurrencia) y, aguas abajo, C33/C29/C35.

No es un servicio de producto de Joiabagur: no hay pantalla, no hay ruta `/v1`, no hay seeder de la API. Es el dataset **D6 / D7 / D8** del [diseño RAG](../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) §8.2–8.3: mundo **numérico y relacional**, código determinista con semilla, **cero LLM**. El histórico tiene que ser coherente por construcción con catálogo y stock (no se vende sin stock en ese POS).

Estado verificado en Docker local (`jpv-pv-postgres`, `:5433`, `joiabagur_pv`, 2026-08-23): `"Products"` 1.200, `"Collections"` 38, `"PaymentMethods"` 6, `"Users"` 1 (`admin`). Vacías las tablas que este change puebla (`"PointOfSales"`, `"Inventories"`, `"Sales"`, `"InventoryMovements"`, `"PointOfSalePaymentMethods"`, `"UserPointOfSales"`). El esquema `ai` **no está** provisionado en este volumen. `"Products"` tiene tres huecos respecto al ancla 1–436 (`SKU135`, `SKU400`, `SKU418`): el ingest usa la BD como autoridad, no el JSONL de catálogo.

**Aproximación acordada (C3, exploración 2026-08-23).** Empaquetado de C06b (CLI en `jbg_ai.data`, no FastAPI, no API .NET) + alma de C06a (sin LLM, perfiles curados) + POS escritos a mano en YAML. No se extiende `generate.py` / `ingest.py` del catálogo: módulo **nuevo** (`jbg_ai.data.world`) y subcomandos propios. No se parte el change (D8).

**Alcance de esta historia (sí):**

- YAML curado de **12 POS** (censo cerrado abajo) + semilla, **commiteado**. Campos de perfil: `code`, `name`, `address`, estacionalidad, λ relativo, mix de colecciones, `is_supply_source`, `is_active`, `allow_manual_price_edit`, operador si aplica. Teléfono pinado `600123456` (`PointOfSale.Phone` es `varchar(20)`).
- CLI en [`ai-service/src/jbg_ai/data/world/`](../../../ai-service/src/jbg_ai/data/) invocado como módulo (`python -m jbg_ai.data world simulate|ingest`). [`jbg_ai.api.main`](../../../ai-service/src/jbg_ai/api/main.py) **no** importa el paquete `data` (sigue la regla C06b).
- Simulación Poisson 14–18 meses (defecto **16**), matriz de propensión producto×POS (intención de audiencia C06b **≠** canal exclusivo de venta), stock inicial, ventas, movimientos derivados, tickets con `BulkOperationId` en un % de checkouts multi-línea (distinto tipo de pieza cuando haya co-venta).
- Volúmenes (centro de las bandas de la ficha, holgura): **12 POS**, **~6.500–8.000** filas `"Inventories"` (no el cartesiano 1.200×12), **15.000–25.000** ventas.
- Ingesta local transaccional (Docker, host **5433**, BD `joiabagur_pv`, `JPV_PG*`): `INSERT` de POS, 3 operadores, asignaciones, métodos de pago por POS, inventario, ventas y movimientos. **No** toca `"Products"` ni `"Collections"`. Un SKU del mundo ausente en BD → lista unmatched y **`ROLLBACK`**.
- Claves naturales en generate: `SKU` y `Code`. Los UUID los resuelve el ingest (`SKU → ProductId`, `Code → PointOfSaleId`, `username → UserId`). `Sale.Price` = snapshot de `"Products"."Price"` en el ingest.
- Tres operadores sintéticos (`Role = Operator`, string EF) en las tres POS de demo; el resto de ventas históricas llevan el `admin` existente. Detalle en D4/D6.
- `PointOfSalePaymentMethods`: los 6 métodos seed en las 11 POS activas; ninguno activo en el hotel cerrado.
- Un POS `IsActive = false` (hotel cerrado) y un % de `"Inventories"."IsActive" = false`.
- Co-ocurrencia: JSONL **efímero** derivado de `Sales.BulkOperationId`. **No** se ingiere en `ai.co_occurrence` (el esquema `ai` no está; lo harán C22/C27). Fuente de verdad = `BulkOperationId`.
- `is_supply_source` **solo** en YAML/sidecar. La columna SQL llega en **C19**; este change **no** abre migración EF Core.
- Informe `Documentos/Proyecto Final AIEng/informes/c10-synthetic-world-report.md` (censo, recuentos, operadores, nota de backup).
- Tras el ingest: `pg_dump` local gitignored por si se pierde el volumen Docker. **No** se commitea el JSONL de ~20k ventas.
- Tests de invariantes (sin LLM, sin red). **No** se exige `test_simulation_is_deterministic_for_same_seed`: el dump es el plan B del volumen, no un corpus bit-idéntico en git.

**Fuera de alcance (no):**

- Ruta HTTP en FastAPI o en la API .NET. Regenerar `ai-service/openapi.json`. Seeder `DatabaseSeeder` de la API.
- RDS / producción.
- Migración EF Core (`IsSupplySource` es **C19**). Ingest del esquema `ai` / `ai.co_occurrence`.
- LLM. Reutilizar `scripts/catalog/assist.py` o el generate de catálogo C06b.
- Tocar `"Products"`, `"Collections"`, `"ProductFamilies"`, `"ProductFamilyMembers"`, `"ProductAiProfiles"`.
- Devoluciones, fotos, componentes, `ProductSearchEvents`, `SalePhotos`, `ModelMetadata` (D9).
- Un operador por cada POS. PII de clientes ( `Sale` no tiene cliente).
- Partir el change en POS+inventario / ventas (D8: un solo change, aunque se trabaje despacio).

**Decisiones de diseño ya acordadas** (exploración 2026-08-23):

| # | Tema | Decisión |
|---|---|---|
| D1 | Aproximación | **C3**: paquete C06b (`jbg_ai.data` CLI), determinismo/curado C06a, POS en YAML. No scripts/ aparte. No seeder .NET. No LLM |
| D2 | Co-ocurrencia | JSONL derivado ahora; ingest `ai` = C22/C27 cuando el schema exista. Verdad = `Sales.BulkOperationId` |
| D3 | `IsSupplySource` | En YAML/sidecar **sí**. En SQL **no** hasta C19 |
| D4 | `Sale.UserId` | La app **no** exige un usuario distinto por POS; exige `UserId` NOT NULL. El RAG (C19/C22/C25/C27/C33) agrega por producto×POS, **no** por operador. Tres operadores solo para demo de login + historial creíble en 3 POS. El chequeo «operador asignado» es de la API, no de la tabla; el CLI hace `INSERT` |
| D5 | Métodos de pago por POS | **Incluirlos** |
| D6 | Quién cobra | Operador sintético **solo** en sus 3 POS. Resto de ventas (y movimientos `Import`/`Adjustment`) → `admin` |
| D7 | Resolución de FKs | Generate trabaja con `SKU`/`Code` (sin Postgres). Ingest lee Docker y resuelve UUID. Unmatched → rollback. No `POST /api/sales` |
| D8 | Partición | **No**. Un change |
| D9 | Returns, fotos, componentes, familias, perfiles IA, search events | **Fuera** |
| D10 | Mundo demasiado limpio | 1 POS `IsActive=false` (hotel cerrado) + % de inventario inactivo |
| D11 | Constraints y fechas | `Phone = 600123456`; `Code` ≤ 20 unique; `SaleDate`/`MovementDate` en el pasado; `CreatedAt`/`UpdatedAt` **escritos**, no `NOW()` del default. Test venta↔movimiento |
| D12 | Destino | **Solo Docker local.** Mismo contrato C06a/C06b |
| Artefactos | JSONL 20k | **No** se commitea. Git: YAML + semilla. Local: JSONL gitignored + `pg_dump` gitignored |
| Determinismo pytest | Ficha C10 | Se **retira** `test_simulation_is_deterministic_for_same_seed`. El seed documenta intención; el dump cubre el accidente del volumen |
| Módulo | vs C06b catálogo | **Nuevo** `world`; no pisar `generate`/`ingest` de catálogo |

**Censo cerrado de 12 POS** (Baleares, centro de gravedad Menorca; audiencias C06b como *intención*, no como canal exclusivo):

| # | Code (≤20) | Nombre | Isla | Estado | λ / rol | Extra |
|---|---|---|---|---|---|---|
| 1 | `MAO-TALLER` | Taller Joia Bagur, Maó | Menorca | activo, **`is_supply_source`** | ~0 retail | Sin operador. `AllowManualPriceEdit=false` |
| 2 | `CIU-CENTRE` | Ciutadella Centre | Menorca | activo, **más ventas** | máx. | Operador `op-ciutadella` |
| 3 | `MAO-AIR` | Aeroport de Menorca | Menorca | activo, persona PF | alto | Operador `op-aeroport`. Precio manual |
| 4 | `FORNELLS` | Fornells | Menorca | activo, **menos ventas retail** | mín. retail | Operador `op-fornells`. Estacionalidad extrema |
| 5 | `BINIBECA` | Boutique Binibeca | Menorca | activo | medio | |
| 6 | `HT-GALDANA` | Hotel Cala Galdana | Menorca | activo | medio-alto, jun–sep | Precio manual |
| 7 | `HT-SONBOU` | Hotel Son Bou | Menorca | activo | medio, más picudo | Precio manual |
| 8 | `PORT-MAO` | Estació Marítima, Maó | Menorca | activo | medio | |
| 9 | `PALMA-JAIME3` | Palma Jaume III | Mallorca | activo | alto (evolución urbana) | Sin operador dedicado |
| 10 | `EIV-MARINA` | Eivissa Marina | Ibiza | activo | medio-alto, may–oct | Precio manual |
| 11 | `HT-ALCUDIA` | Hotel Alcúdia | Mallorca | activo | medio, hotel que el brief no imaginó | Precio manual |
| 12 | `HT-ARTRUTX` | Hotel Cap d'Artrutx | Menorca | **`IsActive=false`** | 0 tras el corte | Cerró tras verano 2025. Sin operador. Sin pagos activos. Inventario residual inactivo |

Operadores (password pinado `Operator123!`, documentado en el informe; no es secreto de producción):

| Username | POS | Relato |
|---|---|---|
| `op-ciutadella` | `CIU-CENTRE` | Flagship, quien «ya se sabe las piezas» |
| `op-fornells` | `FORNELLS` | Temporada baja, `Rotate`, stock parado |
| `op-aeroport` | `MAO-AIR` | Persona del PF: operador de vitrina que no se sabe el catálogo |

`UserPointOfSales`: solo esas tres asignaciones. `MAO-TALLER` y `HT-ARTRUTX` no llevan operador (el admin entra en todos).

**Matriz intención ≠ evolución** (para que C33/C25 no vean colección = canal, que C06b se negó a escribir en `Collection.Name`):

| Colección C06b (brief) | Dónde debería venderse | Dónde también se cuela |
|---|---|---|
| El Jaleo (turista) | `MAO-AIR`, `PORT-MAO`, `EIV-MARINA` | `CIU-CENTRE`, `HT-GALDANA` |
| Fuego / Umbra / Coral negro (hotel) | `HT-GALDANA`, `HT-SONBOU`, `HT-ALCUDIA` | `MAO-AIR` (regalo), `PALMA-JAIME3` |
| Cielo estrellado / Filigrana (atelier) | `MAO-TALLER` (stock), `CIU-CENTRE`, `PALMA-JAIME3` | Casi nunca aeropuerto |
| La Pomada (tienda clásica) | `CIU-CENTRE`, `PALMA-JAIME3` | `BINIBECA` |
| Tramontana / Caliza (menorquín) | `BINIBECA`, `FORNELLS` | `PALMA-JAIME3`, `EIV-MARINA` |
| Marea viva (aeropuerto) | `MAO-AIR`, `PORT-MAO` | `HT-SONBOU`, `EIV-MARINA` |

Cobertura de inventario (orden de magnitud): taller ≈ catálogo entero qty alta; flagship/Palma ~60–70 %; aeropuerto/puertos/hoteles ~25–40 % sesgado al mix; Fornells poco surtido con stock parado a propósito; Artrutx un puñado `IsActive=false`. Global **~6,5k–8k** filas.

**Referencias:**

[proyecto-final-plan-changes-openspec.md](../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C10, §0 C06b 22–23 ago),
[proyecto-final-diseno-rag-joiabagur.md](../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§6.3 frontera, §8.2 mundo determinista, D6–D8, §10 señales),
[epicas.md](../../epicas.md) (EP12),
[modelo-de-datos.md](../../modelo-de-datos.md) (`PointOfSale`, `Inventory`, `InventoryMovement`, `Sale`, `User`, `UserPointOfSale`, `PointOfSalePaymentMethod`),
[HU-AIENG-006a.md](HU-AIENG-006a.md), [HU-AIENG-006b.md](HU-AIENG-006b.md),
change OpenSpec [`openspec/changes/add-synthetic-world-simulator/`](../../../openspec/changes/add-synthetic-world-simulator/) y su [ticket técnico](../../../openspec/changes/add-synthetic-world-simulator/ticket.md).

---

## Criterios de Aceptación

### Escenario 1: El YAML describe las 12 POS del censo
**Dado que** el recetario del mundo vive en git
**Cuando** se lee el YAML de perfiles
**Entonces** hay exactamente los 12 `Code` del censo (`MAO-TALLER` … `HT-ARTRUTX`)
**Y** `MAO-TALLER` lleva `is_supply_source: true` y el resto `false`
**Y** `HT-ARTRUTX` lleva `is_active: false` y una ventana de ventas que termina tras el verano 2025
**Y** todos los teléfonos son `600123456`
**Y** cada `Code` tiene longitud ≤ 20 y es único
**Y** el sidecar/YAML declara `seed` y `generator_version`

### Escenario 2: La simulación no vende sin stock en ese POS
**Dado que** el simulador recorre el horizonte 14–18 meses
**Cuando** emite una venta de SKU S en POS P
**Entonces** existía una fila de inventario activa de S en P con cantidad suficiente **antes** de la venta
**Y** el movimiento tipo `Sale` deja `QuantityAfter = QuantityBefore + QuantityChange` con `QuantityChange < 0`
**Y** ninguna cantidad de inventario queda negativa

### Escenario 3: Los picos siguen el perfil, no un ruido uniforme
**Dado que** Fornells y los hoteles vivos son estacionales y Ciutadella es más plana
**Cuando** se agregan ventas por mes y POS
**Entonces** `HT-GALDANA` / `HT-SONBOU` / `FORNELLS` concentran el volumen en temporada (jun–sep o equivalente del perfil)
**Y** `CIU-CENTRE` no replica esa curva extrema
**Y** `MAO-TALLER` tiene volumen retail ~0 (es origen de suministro, no tienda)
**Y** `HT-ARTRUTX` no tiene ventas **después** de su fecha de cierre
**Y** el orden esperado de volumen (Ciutadella > aeropuerto/Palma > … > Fornells retail > taller > Artrutx) se cumple en magnitud, no hace falta bit-identidad

### Escenario 4: Inventario y movimientos cuadran con el stock final
**Dado que** cada celda producto×POS simulada tiene un stock inicial y una serie de movimientos
**Cuando** se reconstruye `QuantityAfter` del último movimiento
**Entonces** coincide con `"Inventories"."Quantity"` ingerida
**Y** cada venta tiene **un** movimiento (`SaleId` unique) con el mismo `UserId` que la venta
**Y** `SaleDate` (timestamptz) es el mismo instante que `MovementDate`
**Y** `CreatedAt` / `UpdatedAt` de venta y movimiento están alineados con esa fecha, no con el instante del ingest

### Escenario 5: La co-ocurrencia solo cuenta la misma operación
**Dado que** un porcentaje de checkouts lleva `BulkOperationId` compartido
**Cuando** se deriva el JSONL de pares
**Entonces** un par solo cuenta si las líneas comparten `BulkOperationId` (no basta el mismo POS y día)
**Y** el par se orienta de forma canónica (como `ai.co_occurrence` exigirá `product_a < product_b`)
**Y** **no** se escribe ninguna fila en el esquema `ai`

### Escenario 6: El ingest resuelve FKs y no toca el catálogo
**Dado que** Docker tiene 1.200 productos y 0 POS
**Cuando** corre `world ingest` contra el JSONL efímero
**Entonces** se insertan 12 POS, 3 operadores, 3 `UserPointOfSales`, métodos de pago en las 11 activas, inventario, ventas y movimientos en **una** transacción
**Y** el recuento y los SKU de `"Products"` no cambian
**Y** `"Collections"` no cambia
**Y** un SKU del mundo que no exista en `"Products"` aborta con unmatched y `ROLLBACK`
**Y** PostgreSQL asigna los `Id`; el YAML no lleva UUID de POS ni de producto
**Y** no hay escrituras contra RDS
**Y** no existe columna `IsSupplySource` en `"PointOfSales"`

### Escenario 7: Operadores y `Sale.UserId`
**Dado que** `Sale.UserId` es NOT NULL y el RAG no agrupa por operador
**Cuando** se inspeccionan las ventas ingeridas
**Entonces** las de `CIU-CENTRE` / `FORNELLS` / `MAO-AIR` llevan el `UserId` de `op-ciutadella` / `op-fornells` / `op-aeroport`
**Y** las de las otras POS activas llevan el `UserId` del `admin` existente
**Y** `HT-ARTRUTX` no tiene operador asignado
**Y** los tres operadores tienen `Role = Operator`, asignación activa a **una** POS, y permiten login local con `Operator123!`

### Escenario 8: El hotel cerrado y el inventario inactivo
**Dado que** un mundo demasiado limpio no ejercita tombstones ni `Rotate`
**Cuando** termina el ingest
**Entonces** `"PointOfSales"` de `HT-ARTRUTX` tiene `IsActive = false`
**Y** su inventario residual tiene `IsActive = false`
**Y** un porcentaje de filas de inventario en POS **activas** también está `IsActive = false`
**Y** `HT-ARTRUTX` no tiene `PointOfSalePaymentMethods` activos

### Escenario 9: El servicio HTTP no se entera
**Dado que** C17 arranca `jbg-ai` sin claves de catálogo ni de mundo
**Cuando** se inspecciona este change
**Entonces** `jbg_ai.api.main` no importa `jbg_ai.data`
**Y** `ai-service/openapi.json` no ha cambiado
**Y** no hay migración EF Core ni Alembic
**Y** pytest del simulador no abre sockets a proveedores LLM
**Y** el JSONL de ventas **no** está en git; sí el YAML y la semilla
**Y** el README del CLI documenta `pg_dump` / restore contra `jpv-pv-postgres`

### Escenario 10: Fuera de alcance explícito
**Dado que** esta historia está implementada según el alcance acordado
**Cuando** se revisa el entregable
**Entonces** **no** hay endpoint de simulación, ni cambios de API backend/frontend, ni alta de POS por la UI
**Y** **no** se ha implementado C19, C22 ni C27 (solo se les deja datos en `public`)
**Y** **no** hay filas nuevas en `"ProductFamilies"`, `"ProductAiProfiles"`, `"Returns"` ni `"ProductSearchEvents"`
**Y** **no** se ha ejecutado el generate de catálogo C06b ni un LLM

---

## Notas adicionales

- **Actor:** equipo del Proyecto Final. La ingesta es operación de desarrollo. El login de los tres operadores es para demostrar C16/C36 más adelante, no un requisito del ranking.

- **Por qué `Sale.UserId` no calibra el RAG.** C19/C22/C25/C27/C33 agregan por producto×POS. El `user_id` del JWT interno es quien busca *ahora*. El campo histórico es cosmética coherente + filtro del historial de ventas de la app ya existente (HU-EP9-001). La API sí exige asignación al **crear** ventas como Operator; el CLI no pasa por esa API. Un admin vende en cualquier POS sin `UserPointOfSales`.

- **Por qué no hay test de determinismo.** La ficha C10 lo nombraba. Se retira a propósito: no se versiona el JSONL de 20k líneas; el seguro es un dump local del volumen. Los tests de *invariantes* siguen siendo el contrato. Un refactor del Poisson puede mover Fornells; el dump no lo detecta, pytest de propiedades sí detecta stock negativo o picos planos.

- **Esquema `ai`.** C05 está archivado en código; este Docker no tiene el schema. C10 no lo provisiona (bootstrap aparte) y no escribe `ai.co_occurrence`.

- **`IsSupplySource`.** El plan ya decía que C10 genera la marca y la importación SQL se ejecuta después de C19 o se repite. El YAML es esa marca.

- **Huecos SKU135/400/418.** El generate puede leer el JSONL de catálogo para sesgar mix; el ingest **inner-join** contra `"Products"`. Si el simulador emite un SKU fantasma, falla en rojo, no a medias.

- **`User.Role`.** EF lo persiste como string (`Administrator` / `Operator`), no como entero.

---

## Tareas

1. Completar artefactos OpenSpec del change `add-synthetic-world-simulator` (proposal, design, specs, tasks).
2. YAML de 12 POS + semilla; `.gitignore` para JSONL de mundo y dumps SQL.
3. Módulo `jbg_ai.data.world`: simulate (SKU/Code, Poisson, movimientos, `BulkOperationId`) e ingest transaccional (`JPV_PG*`).
4. Alta de 3 operadores (BCrypt cost 12, mismo factor que `DatabaseSeeder`) y asignaciones; `Sale.UserId` según D6.
5. Tests de invariantes listados en los escenarios 2–9; **sin** test de bit-identidad.
6. Informe C10 + `pg_dump` local documentado.
7. `openspec validate --all --strict` antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** 4 — no es pantalla; sin este mundo C19/C22/C27 miden cero
- **Urgencia:** 3 — 🟢; no está en la ruta crítica de búsqueda, sí conviene antes de señales e inventario asistido
- **Complejidad:** 4 — simulación coherente + INSERT masivo en `public` desde CLI Python, sin contrato HTTP
- **Riesgos y dependencias:** catálogo C06a+C06b ya ingerido (1.200 SKUs); Postgres Docker; frontera §6.3 (rol `jbg-ai` vs CLI); C19 posterior para `IsSupplySource`; schema `ai` posterior para co-ocurrencia persistida; dump local no sustituye tests de invariantes
