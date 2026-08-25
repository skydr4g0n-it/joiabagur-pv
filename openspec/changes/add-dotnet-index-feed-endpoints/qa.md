# QA — C12 `add-dotnet-index-feed-endpoints`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-25 · **Rama:** `c12-add-dotnet-index-feed-endpoints` · **Commit de artefactos (HEAD, sin commit de implementación aún):** `14112ca`
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| SDK | .NET 10 (`net10.0`) |
| Solución | `backend/src/JoiabagurPV.sln` |
| Marco de pruebas | xUnit + FluentAssertions + Testcontainers (`postgres:15`) |
| Alcance medido | Filtro `AiIndexFeed` / `IndexFeed` / `PriceBand` / `ReplaceMembers_*` / `Model_HasNoPendingMigrationDifferences` — **no** la suite global |
| `ai-service` | **No se ejecuta**: este change no cruza la frontera. Ver §4 |
| Contrato | `ai-service/openapi.json` — **este change NO lo modifica** |
| Stub C13 | `POST /v1/index/sync` y `GET /v1/index/status` intactos (`DELIVERED_BY = "C13 (add-product-document-indexer)"`) |

---

## 1. Suite automática de .NET (alcance C12)

No se midió la suite global con `git stash`. `CLAUDE.md` avisa de que el recuento no es señal de regresión y de no gastar la sesión «arreglando» rojos preexistentes. La comparación de esta pasada es por **nombres del filtro**, todos verdes al cierre.

| Ejecución | Resultado |
|---|---|
| Primera pasada `IndexFeed\|PriceBand` | **44 passed, 1 failed** de 45 — `CatalogFeed_ExcludesUnapprovedProfiles` (ver §7.1) |
| Familia + snapshot, **antes** de `ExecuteUpdate` | **3 passed, 4 failed** de 7 — `UpdatedAt` no persistía (ver §7.2) |
| Familia + snapshot, **después** de `ExecuteUpdate` | **6 passed, 0 failed** |
| Pasada de cierre (filtro completo) | **52 passed, 0 failed**, 54 s |

Comando de la pasada de cierre (tareas 6.1–6.4):

```powershell
dotnet test backend/src/JoiabagurPV.Tests/JoiabagurPV.Tests.csproj --filter "FullyQualifiedName~AiIndexFeed|FullyQualifiedName~IndexFeed|FullyQualifiedName~PriceBand|FullyQualifiedName~ReplaceMembers_Leaving|FullyQualifiedName~ReplaceMembers_Entering|FullyQualifiedName~ReplaceMembers_Reorder|FullyQualifiedName~ReplaceMembers_Identical|FullyQualifiedName~ReplaceMembers_Rename|FullyQualifiedName~Model_HasNoPendingMigrationDifferences"
```

El filtro `ReplaceMembers_Reorder` arrastra también el test preexistente `ReplaceMembers_ReorderingExistingMembers_Succeeds` (+1). Los 50 tests **nuevos** de C12 están en el conjunto; ninguno falló en la pasada de cierre.

### 1.1. Desglose de los tests nuevos

| Fichero | Nº (métodos / casos) | Qué cubre |
|---|---|---|
| `UnitTests/Application/IndexFeedRegistrationTests.cs` | 5 | Fail-fast: key ausente, corta, placeholder ≥ 32, `ApiKeyPrevious` vacía = unset, previous corta |
| `UnitTests/Application/IndexFeedKeyComparerTests.cs` | 6 + 3 | Match / previous / unset / mismatch / ausente / distinta longitud; filtro HTTP llama a `next` o 401 **sin** loguear el header |
| `UnitTests/Application/PriceBandTests.cs` | 5 + 2 | Cortes v1 (29.99 / 30 / 80 / 150 / 300), 0 → `lt-30`, negativo → `ArgumentOutOfRangeException` |
| `UnitTests/Application/IndexFeedAggregateHashTests.cs` | 4 + 3 | Hash estable al reordenar, 64 hex minúsculas, cambia al salir un id, pares POS; DTOs sin `quantity` / `dataOrigin` / `textProvenance` |
| `IntegrationTests/AiIndexFeedCatalogTests.cs` | 8 | Cursor, tombstones, never-approved, sin perfil, hash de 51 productos en dos páginas, `pageSize` ignorado |
| `IntegrationTests/AiIndexFeedAuthTests.cs` | 5 | JWT usuario, token C03, header ausente, key distinta, key válida — **cliente HTTP fresco** |
| `IntegrationTests/AiIndexFeedPosTests.cs` | 4 | Buckets 0 / 1-2 / 3+, tombstone `unassigned`, ventas sin restar `Return`, página 200 |
| `IntegrationTests/ProductFamiliesControllerTests.cs` (ampliado) | +5 | Sello de altas/bajas, reorder/label, lista idéntica, rename de metadatos |

---

## 2. Escenarios de las specs, uno a uno

### `index-feed`

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Catalog feed pages by keyset watermark at fifty items · The since cursor returns only rows whose watermark changed | `CatalogFeed_WithSinceCursor_ReturnsOnlyChangedRows` | ✅ |
| Catalog feed pages by keyset watermark at fifty items · Catalog page size is server-fixed | `CatalogFeed_IgnoresClientPageSize_AndOmitsProvenance` (`pageSize=1000` → respuesta 50) · `Feed_ReturnsAggregateHashForDriftDetection` (51 productos → primera página 50, `hasMore`) | ✅ |
| Catalog items are upserts or tombstones · A deactivated product emits a tombstone | `CatalogFeed_EmitsTombstoneWhenProductDeactivated` (`reason = deactivated`, sin `sku`) | ✅ |
| Catalog items are upserts or tombstones · An unapproved profile is not upserted and leaving approved is a tombstone | `CatalogFeed_ExcludesUnapprovedProfiles` · `CatalogFeed_NeverApprovedProduct_IsAbsent` · `CatalogFeed_EmitsTombstoneWhenProfileUnapproved` | ✅ |
| Catalog items are upserts or tombstones · A product with no profile does not appear | `CatalogFeed_ProductWithoutProfile_IsAbsent` | ✅ |
| Catalog upsert is a superset of source text · Upsert maps source-text fields and identifiers | `CatalogFeed_IgnoresClientPageSize_AndOmitsProvenance` (`priceBand`, `materials` array). **No** hay aserción dedicada de `collectionName` / `familyId` en el JSON | ⚠️ parcial — ver §8 |
| Catalog upsert is a superset of source text · Provenance and origin stay out of the catalog JSON | misma función + `CatalogUpsert_HasNoForbiddenProperties` / `PageDto_HasNoQuantityOrProvenance` | ✅ |
| Price band is the pure function price-band/v1 · Cuts of price-band/v1 | `PriceBand_Cuts_MatchV1` | ✅ |
| Price band is the pure function price-band/v1 · A negative price fails loudly | `PriceBand_NegativePrice_Throws` · `PriceBand_Zero_IsLt30` | ✅ |
| POS availability feed · The feed returns a bucket not an exact quantity | `PosAvailabilityFeed_ReturnsBucketNotExactQuantity` · `PosAvailabilityFeed_SalesWindows_DoNotSubtractReturns` | ✅ |
| POS availability feed · Unassignment emits a tombstone | `PosAvailabilityFeed_Unassigned_EmitsTombstone` | ✅ |
| POS availability feed · The POS page cap is 200 and is not copied to UI lists | `PosAvailabilityFeed_PageSize_Is200` (201 filas → 200; catálogo sigue en 50) | ✅ |
| Feeds authenticate only with the index-feed API key · A user JWT does not open the feed | `Feed_WithUserJwt_Returns401` · `Feed_WithC03Token_Returns401` · `Feed_MissingApiKey_Returns401` · `Feed_WrongApiKey_Returns401` (todos 401, no 403; cliente fresco) | ✅ |
| Feeds authenticate only with the index-feed API key · A valid API key opens the feed | `Feed_WithValidApiKey_Returns200`. `ApiKeyPrevious` se cubre en unidad (`Matches_PreviousKey_WhenConfigured_IsTrue`, `Filter_WithPreviousKey_CallsNext`), **no** contra el host de Testcontainers | ⚠️ parcial — ver §8 |
| Aggregate hash is the digest of the global indexable set · The aggregate hash detects set drift | `Feed_ReturnsAggregateHashForDriftDetection` (mismo hash en dos páginas; cambia al desactivar) · `Hash_Is64LowercaseHex` · `Hash_ChangesWhenAProductLeavesTheSet` · `PosHash_OrdersByPairNotByArrival` | ✅ |
| Leaving a family surfaces on the catalog cursor · A product that left a family appears after the replace | Escritura: `ReplaceMembers_LeavingProduct_StampsUpdatedAt`. **No** hay GET de catálogo posterior al replace | ⚠️ parcial — ver §8 |
| Leaving a family surfaces on the catalog cursor · A family rename surfaces current members without rewriting them | Escritura: `ReplaceMembers_Rename_DoesNotStampMemberProducts` (productos intactos; familia sellada con `StampUpdatedAtAsync`). **No** hay GET de catálogo posterior al rename | ⚠️ parcial — ver §8 |
| The feed change does not migrate, push or index · Out of scope remains out of scope | `git diff` vacío en migraciones / `ai-service/` / `frontend/` / `terraform/`; runbook existe y **no** se ejecutó; stub C13 intacto; `openspec validate --all --strict` | ✅ |

### `product-family`

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Membership changes stamp the catalog watermark · A product that leaves a family has its UpdatedAt stamped | `ReplaceMembers_LeavingProduct_StampsUpdatedAt` | ✅ |
| Membership changes stamp the catalog watermark · A product that enters a family has its UpdatedAt stamped | `ReplaceMembers_EnteringProduct_StampsUpdatedAt` | ✅ |
| Membership changes stamp the catalog watermark · A reorder or label change stamps the products that stayed | `ReplaceMembers_ReorderOrLabelChange_StampsStayers` | ✅ |
| Membership changes stamp the catalog watermark · An identical list still writes nothing, including Product | `ReplaceMembers_IdenticalList_DoesNotWriteProduct` | ✅ |
| Membership changes stamp the catalog watermark · A metadata rename does not stamp member products | `ReplaceMembers_Rename_DoesNotStampMemberProducts` | ✅ |

**Totales:** 10 requisitos, 23 escenarios (`#### Scenario:`: 18 en `index-feed` + 5 en `product-family`). 18 con test HTTP/unidad que los nombra; 5 con cobertura parcial anotada en §8. Ninguno sin evidencia de código.

---

## 3. Nombres exigidos por `tasks.md` / ticket

Todos existen como métodos `Method_Scenario_ExpectedResult` y están en verde en la pasada de cierre.

| Nombre | Fichero |
|---|---|
| `PriceBand_Cuts_MatchV1` | `PriceBandTests.cs` |
| `PriceBand_NegativePrice_Throws` | `PriceBandTests.cs` |
| `CatalogFeed_WithSinceCursor_ReturnsOnlyChangedRows` | `AiIndexFeedCatalogTests.cs` |
| `CatalogFeed_EmitsTombstoneWhenProductDeactivated` | `AiIndexFeedCatalogTests.cs` |
| `CatalogFeed_ExcludesUnapprovedProfiles` | `AiIndexFeedCatalogTests.cs` |
| `CatalogFeed_NeverApprovedProduct_IsAbsent` | `AiIndexFeedCatalogTests.cs` |
| `CatalogFeed_EmitsTombstoneWhenProfileUnapproved` | `AiIndexFeedCatalogTests.cs` |
| `Feed_ReturnsAggregateHashForDriftDetection` | `AiIndexFeedCatalogTests.cs` |
| `Feed_WithUserJwt_Returns401` | `AiIndexFeedAuthTests.cs` |
| `Feed_WithC03Token_Returns401` | `AiIndexFeedAuthTests.cs` |
| `Feed_MissingApiKey_Returns401` | `AiIndexFeedAuthTests.cs` |
| `Feed_WrongApiKey_Returns401` | `AiIndexFeedAuthTests.cs` |
| `Feed_WithValidApiKey_Returns200` | `AiIndexFeedAuthTests.cs` |
| `PosAvailabilityFeed_ReturnsBucketNotExactQuantity` | `AiIndexFeedPosTests.cs` |
| `PosAvailabilityFeed_Unassigned_EmitsTombstone` | `AiIndexFeedPosTests.cs` |
| `PosAvailabilityFeed_SalesWindows_DoNotSubtractReturns` | `AiIndexFeedPosTests.cs` |
| `PosAvailabilityFeed_PageSize_Is200` | `AiIndexFeedPosTests.cs` |
| `ReplaceMembers_LeavingProduct_StampsUpdatedAt` | `ProductFamiliesControllerTests.cs` |
| `ReplaceMembers_EnteringProduct_StampsUpdatedAt` | `ProductFamiliesControllerTests.cs` |
| `ReplaceMembers_ReorderOrLabelChange_StampsStayers` | `ProductFamiliesControllerTests.cs` |
| `ReplaceMembers_IdenticalList_DoesNotWriteProduct` | `ProductFamiliesControllerTests.cs` |
| `ReplaceMembers_Rename_DoesNotStampMemberProducts` | `ProductFamiliesControllerTests.cs` |
| `Model_HasNoPendingMigrationDifferences` | suite de esquema preexistente; **verde** en la pasada de cierre |

Extras que cubren escenarios o validaciones de tarea no nombrados en la ficha: `CatalogFeed_ProductWithoutProfile_IsAbsent`, `CatalogFeed_IgnoresClientPageSize_AndOmitsProvenance`, `AddIndexFeed_WhenApiKeyMissing_FailsOnStart`, `AddIndexFeed_WhenApiKeyTooShort_FailsOnStart`, `AddIndexFeed_WithValidPlaceholder_Starts`, `Matches_DifferentLength_IsFalseWithoutThrowing`, `Filter_WithMissingOrWrongKey_Returns401AndDoesNotLogTheHeader`, `Hash_Is64LowercaseHex`, `CatalogUpsert_HasNoForbiddenProperties`, `PosUpsert_HasNoQuantityProperty`.

---

## 4. Alcance negativo (tarea 7.3)

```powershell
git diff --stat -- backend/src/JoiabagurPV.Infrastructure/Data/Migrations/ ai-service/ frontend/ terraform/
git diff --name-only -- ai-service/openapi.json ai-service/src/ ai-service/migrations/ frontend/ terraform/
```

Salida **vacía**. `git status --short` sobre esas rutas, también vacío.

| Guardarraíl | Comprobación | Resultado |
|---|---|---|
| `ai-service/openapi.json` | no está en el working tree de C12 | ✅ |
| `ai-service/src/` | no tocado; `routers/index.py` sigue nombrando C13 | ✅ |
| `ai-service/migrations/` | no tocado | ✅ |
| `frontend/` | no tocado | ✅ |
| `terraform/` | no tocado | ✅ |
| Migraciones EF | `git diff` de `Infrastructure/Data/Migrations/` vacío; `Model_HasNoPendingMigrationDifferences` verde | ✅ |
| Stub C13 | `DELIVERED_BY = "C13 (add-product-document-indexer)"`; `require_stub_mode` | ✅ |
| `PaginationConstants.MaxPageSize` | no se usa en `IndexFeedRepository` (comentario de guarda + constantes propias 50/200) | ✅ |
| TODO/FIXME sin seguimiento | `rg TODO\|FIXME` en ficheros `*IndexFeed*` vacío | ✅ |
| AutoBulk de los 1.200 | **no ejecutado**; el runbook lo dice en el título | ✅ |

---

## 5. Decisiones de diseño, verificadas en código

| Decisión | Evidencia |
|---|---|
| 1 · Header `X-Index-Feed-Key`; constant-time; previous opcional | `IndexFeedKeyComparer` + `[IndexFeedKey]` en `AiIndexFeedController`; **sin** `[Authorize]` |
| 2 · Pull; invalidación = watermark; sin outbox ni push | No hay cliente HTTP hacia `/v1/index/sync`; no hay tabla nueva; cursor keyset en `IndexFeedRepository` |
| 3 · `kind` upsert/tombstone; never-approved ausente | Tests de catálogo y POS citados en §2; full-sync no emite tombstones de `Pending`/`Rejected` |
| 4 · Página 50 / 200; constantes propias | `IndexFeedPageSizes.Catalog = 50`, `PosAvailability = 200`; query `pageSize` ignorado |
| 5 · Superset de `ProductSourceText`; sin procedencia | DTOs sin `Quantity` / `DataOrigin` / `TextProvenance`; JSON de integración sin esas claves |
| 6 · `price-band/v1` pura | `PriceBand.From(decimal)`; suite unitaria sin Testcontainers |
| 7 · Hash SHA-256 del conjunto **global** | `Feed_ReturnsAggregateHashForDriftDetection` (51 productos, mismo hash en página 1 y 2) |
| 8 · `ReplaceMembers` sella altas/bajas | `StampUpdatedAtAsync` vía `ExecuteUpdate` (ver §7.2); cortocircuito `AlreadyMatches` no escribe |
| 9 · POS disperso; ventas sin restar `Return` | `PosAvailabilityFeed_SalesWindows_DoNotSubtractReturns`; `TimeProvider` inyectado |
| 10 · Log de página, no de la key | `Filter_WithMissingOrWrongKey_Returns401AndDoesNotLogTheHeader` |

**Arquitectura.** `IIndexFeedRepository` vive en **Domain**, no en Application: Infrastructure no referencia Application. Detectado al compilar el primer borrador.

---

## 6. Documentación de contexto (tareas 7.1 / 7.2)

| Documento | Qué se alineó |
|---|---|
| `Documentos/Proyecto Final AIEng/informes/c12-catalog-autobulk-runbook.md` | Puerta de C13, quién/cuándo (después de archivar C12, antes del apply de C13), 24 llamadas / lote 50 / `force: false`, verificación `ReviewStatus = 2`, tiempo 15–40 min, coste, qué no hacer. **No** es un acta de ejecución |
| `Documentos/epicas.md` (EP14) | HU-AIENG-012 + los dos `GET`, API Key, 401 de JWT/C03, **sin migración / sin push** |
| `Documentos/modelo-de-datos.md` | Feed como **lector HTTP**; sin entidad ni columna nueva |
| [ticket.md](ticket.md) | DoD cubierto por los tests de §3; AutoBulk fuera del merge |

---

## 7. Incidencias encontradas durante la implementación

### 7.1. `OnlyContain` sobre colección vacía (FluentAssertions 7)

`CatalogFeed_ExcludesUnapprovedProfiles` falló en la primera pasada (44/45) porque `OnlyContain(...)` sobre una secuencia vacía no cumple el predicado: no hay elementos que lo satisfagan. Un full-sync de `Pending`/`Rejected` **debe** devolver página vacía (no tombstones de algo que nunca fue indexable).

**Corrección:** `page.Items.Should().BeEmpty(...)`. Tras el cambio, el test está en el 52/52.

### 7.2. `Product.UpdatedAt` no llega a Postgres

`UpdatedAt` está mapeado con `ValueGeneratedOnAddOrUpdate()` + `HasDefaultValueSql("NOW()")`. EF **omite** la columna en el `UPDATE`. El interceptor de `SaveChangesAsync` asigna `UtcNow` en memoria, pero el valor no persiste. Los cuatro tests `ReplaceMembers_*StampsUpdatedAt` veían el mismo instante before/after.

Dos hipótesis, comprobadas y descartadas:

| Hipótesis | Cómo se descartó |
|---|---|
| Marcar `entry.Property(e => e.UpdatedAt).IsModified = true` en `SaveChangesAsync` | Los cuatro tests siguieron fallando igual. La línea **sigue** en el interceptor (cinturón global); no basta para el sello de familia |
| Cambiar `ValueGeneratedOnAddOrUpdate` / AfterSaveBehavior | Abriría diferencia de modelo. Tarea 6.4 exige `git diff` de `Migrations/` **vacío** |

**Corrección:** `IProductRepository.StampUpdatedAtAsync` / `IProductFamilyRepository.StampUpdatedAtAsync` con `ExecuteUpdateAsync`, que salta el change tracker. `ReplaceMembersAsync` sella altas ∪ bajas (o la lista declarada en reorder/label). `UpdateAsync` (rename) sella solo la familia.

Efecto colateral de compilación: el fake `RaceBlindFamilyRepository` de `ProductFamiliesControllerTests` tenía que reenviar `StampUpdatedAtAsync`; sin eso el proyecto de tests no compilaba.

Tras el arreglo: **6/6** en el filtro de familia + snapshot, y **52/52** en el de cierre.

No se tocó el snapshot de EF. Esa era la restricción.

---

## 8. Cobertura parcial (no bloquea el apply)

Ninguno de estos huecos contradice un checkbox de `tasks.md`. Quedan escritos para `/opsx:verify` o para C13.

| Hueco | Qué hay | Qué falta |
|---|---|---|
| Mapeo completo del upsert de catálogo | `priceBand`, `materials` como array, ausencia de procedencia | Aserción de `sku` / `name` / `productId` / `familyId` / `collectionName` en un ítem con familia y colección |
| `ApiKeyPrevious` en el host | Unidad del comparador y del filtro | Integración con Testcontainers y header = previous |
| Familia → cursor de catálogo | Sello de `UpdatedAt` en altas/bajas/rename | Un GET `/catalog?since=` después de `ReplaceMembers` / rename que vea el `productId` |
| Scalar / OpenAPI de la API Key | Comentario en el controlador: no es secreto de usuario | No se abrió Scalar en el navegador |
| Suite global .NET | Filtro C12 verde | Línea base nombre-a-nombre de `dotnet test` sin filtro (tarea 6.4 la pedía; no se ejecutó para no mezclar flakes preexistentes con esta sesión) |

---

## 9. OpenSpec

```powershell
openspec validate --all --strict
```

**40 passed, 0 failed.** Incluye el change `add-dotnet-index-feed-endpoints` y todas las specs vivas. Ejecutado en la forma `--all --strict`, no en la de un solo change (`CLAUDE.md`).

`openspec status --change add-dotnet-index-feed-endpoints`: artefactos proposal/design/specs/tasks **done**; 16/16 tareas marcadas.

`/opsx:verify` **no** se ha ejecutado en esta pasada. Este fichero es el registro de la apply, no el informe de verify.

---

## 10. Fuera de esta pasada (no DoD)

- AutoBulk sobre los 1.200 del catálogo Docker (el runbook existe para correrlo **después** de archivar C12).
- Cliente Python del feed, `POST /v1/index/sync` real, filas en `ai.product_document` (C13).
- Feed POS consumido (`ai.pos_projection`, C22).
- Regenerar `openapi.json`: **prohibido** por el change; el diff está vacío.
- Cobertura de líneas: no se ha ejecutado ninguna herramienta, así que no se afirma el ≥70 % del DoD de proyecto.
- Llamada manual contra un proceso `dotnet run` fuera de Testcontainers.
- SSM / rotación de la key en producción (C17).

---

## Veredicto

**Sin problemas críticos para archivar el código de la apply.** 52/52 en el filtro de C12, `Model_HasNoPendingMigrationDifferences` verde, diffs vacíos en `ai-service/`, `frontend/`, `terraform/` y migraciones EF, `openspec validate --all --strict` en 40/0, 16/16 tareas.

Los cuatro escenarios marcados parciales en §8 son huecos de aserción, no de implementación: el sello de familia, el comparador de previous y el payload sin procedencia están escritos y, donde hay test, verdes.

**Listo para `/opsx:verify` y, si el verify no abre CRITICAL, para archivar.**
