> **Línea de corte.** Los grupos 1–4 son la mitad que **desbloquea C13**: options, API Key, `price-band/v1`, feed de catálogo (cursor, tombstones, hash) y el sello de `ReplaceMembers`. Si la sesión se desborda (ficha C12 / regla 5 del plan), se entrega esa mitad. Los grupos 5–6 son el feed POS (página 200, buckets, ventas, tombstone `unassigned`). Sin ellos C22 no arranca, así que esa segunda mitad sigue siendo 🔴. El usuario pidió no partir; esta línea solo aplica si el apply no cabe.

> **Guardarraíl de contrato.** Este change **no toca** `ai-service/`, `ai-service/openapi.json`, `frontend/`, migraciones EF/Alembic ni `POST /v1/index/sync`. Si `Model_HasNoPendingMigrationDifferences` se pone rojo, se ha abierto esquema: revertir. Si `test_openapi_snapshot_is_stable` se pone rojo, el trabajo se ha salido del alcance: no se regenera el snapshot.

> **Guardarraíl de auth.** El controlador **no** lleva `[Authorize(Roles = ...)]`. Un JWT de usuario, una cookie `access_token` o un token C03 **no** autentican. 401, no 403. Los tests de 401 usan un `HttpClient` **fresco** (sin cookies de un login previo). `IndexFeed:ApiKey` ≥ 32 caracteres, distinta de `Jwt:SecretKey` y de `AiGateway:JwtSecret`. Comparación constant-time. La key no se loguea.

> **Guardarraíl de paginación.** Constantes propias del feed: catálogo = 50, POS = 200. **No** usar `PaginationConstants.MaxPageSize` (1000) ni el tope 50/100 de listados de operador. El cliente no elige `pageSize`.

> **Guardarraíl de tests.** Nombres `Method_Scenario_ExpectedResult`. No «arreglar» rojos preexistentes; comparar **nombres** de fallos contra el baseline. AutoBulk de los 1.200 **no** se ejecuta.

## 1. Options, fail-fast y filtro de API Key

- [ ] 1.1 Añadir `IndexFeedOptions` (`ApiKey`, `ApiKeyPrevious`) en `JoiabagurPV.Application/Configuration/`, sección `IndexFeed`, umbral `MinimumSecretLength = 32` (el mismo que `AiGatewayOptions`). Validar al arranque: `ApiKey` obligatoria y ≥ 32 caracteres; `ApiKeyPrevious` opcional (vacía = unset). Placeholder en `backend/.env.example` y `appsettings*.json`, distinto de `Jwt:SecretKey` y de `AiGateway:JwtSecret`. **No** SSM (C17). **Validación:** el host no arranca si la key falta o es corta; arranca con placeholder local de 32+ chars.

- [ ] 1.2 Implementar el filtro/attribute de `X-Index-Feed-Key` con `CryptographicOperations.FixedTimeEquals` sobre UTF-8. Aceptar `ApiKey` o, si está configurada y no vacía, `ApiKeyPrevious`. Longitudes distintas: comparación dummy + 401, sin camino corto por `Length`. La key no se loguea. **Validación:** test de unidad del comparador (match / mismatch / previous / ausente); ningún `Log*` recibe el valor del header.

## 2. `price-band/v1` (clase pura)

- [ ] 2.1 Implementar `PriceBand.From(decimal)` (o equivalente) sin HTTP ni EF. Constante `PriceBandVersion = "price-band/v1"`. Cortes: `lt-30` &lt; 30; `30-80` [30, 80); `80-150` [80, 150); `150-300` [150, 300); `gte-300` ≥ 300. Precio negativo → `ArgumentOutOfRangeException`. **Validación:** `PriceBand_Cuts_MatchV1` (29.99 / 30 / 80 / 150 / 300); `PriceBand_NegativePrice_Throws`; 0 → `lt-30`. Suite unitaria **sin** Testcontainers.

## 3. Feed de catálogo

- [ ] 3.1 DTOs camelCase de página (`items`, `nextCursor: { since, sinceId } | null`, `hasMore`, `pageSize`, `aggregateHash`) y de ítem (`kind` upsert|tombstone). Upsert = campos de `ProductSourceText` + `productId` + `familyId` + `price` + `priceBand` + `isActive` + `watermark`. Tombstone = `{ kind, productId, reason: deactivated|unapproved, at }`. Materiales y tags como arrays, no `*Json`. **Sin** `dataOrigin` / `textProvenance` / `source` / `confidence`. Constantes `IndexFeedPageSizes.Catalog = 50`. **Validación:** los DTOs no tienen propiedad `quantity`, `dataOrigin` ni `textProvenance`.

- [ ] 3.2 Consulta keyset de catálogo en Infrastructure: `watermark = greatest(Product.UpdatedAt, Profile.UpdatedAt, Family.UpdatedAt)` (familia solo con miembro actual). Predicado `(watermark > since) OR (watermark = since AND productId > sinceId)`. `indexable = IsActive AND ReviewStatus = Approved` (`ReviewOrigin` no se mira). Sin perfil → no se emite. Página fija 50; `pageSize` query se ignora. Hash agregado SHA-256 UTF-8 de los `productId` indexables **globales** ordenados, hex minúsculas 64 chars, **una vez por request**. **Validación:** la query no usa `PaginationConstants.MaxPageSize`; el hash no se calcula sobre la página.

- [ ] 3.3 `IndexFeedService` (o equivalente) + `AiIndexFeedController` en ruta literal `api/ai/index-feed`. **Sin** `[Authorize(Roles = ...)]`. El filtro de 1.2 cubre ambas acciones. Log estructurado de página (`item_count`, `has_more`, `aggregate_hash` truncado, `trace_id` si llega); no dump de descripciones ni de la key. Registrar el servicio en DI. **Validación:** la ruta responde 401 sin header; con key válida responde 200; Scalar no documenta la key como secreto de usuario.

## 4. Invalidación de familia (deuda C07)

- [ ] 4.1 En `ProductFamilyService.ReplaceMembersAsync`, después de calcular altas y bajas y antes/junto al `SaveChanges` de miembros: cargar y marcar `Modified` los `Product` que **salen** y los que **entran**. Reorder o cambio de `variantLabel` (mismos ids): marcar los productos de la lista declarada. Cortocircuito `AlreadyMatches`: **cero** escrituras, incluido Product. Rename de metadatos: no marcar miembros (`Family.UpdatedAt` ya sella). **Validación:** `ReplaceMembers_LeavingProduct_StampsUpdatedAt`; `ReplaceMembers_EnteringProduct_StampsUpdatedAt`; `ReplaceMembers_ReorderOrLabelChange_StampsStayers`; `ReplaceMembers_IdenticalList_DoesNotWriteProduct`; `ReplaceMembers_Rename_DoesNotStampMemberProducts`.

## 5. Feed POS

- [ ] 5.1 DTOs y constante `IndexFeedPageSizes.PosAvailability = 200`. Upsert: `pointOfSaleId`, `productId`, `qtyBucket` (`0` | `1-2` | `3+`), `isAssignedHint`, `sales30d`, `sales90d`, `lastSaleAt`, `kind`. Tombstone: `{ kind, pointOfSaleId, productId, reason: unassigned, at }`. **Prohibido** serializar `quantity`. Cursor keyset `(watermark, Inventory.Id)` con `watermark = greatest(LastUpdatedAt, UpdatedAt)`. **Validación:** el DTO de upsert no tiene propiedad `Quantity` / `quantity`.

- [ ] 5.2 Consulta dispersa: filas `Inventory` activas → upsert; `IsActive = false` en el cursor → tombstone. `qtyBucket` según cortes del design. `sales30d` / `sales90d` = `SUM(Sale.Quantity)` por `(ProductId, PointOfSaleId)` en [now-30d, now] y [now-90d, now] **sin** restar `Return`. `lastSaleAt` = `MAX(SaleDate)` o null. Subquery agrupada, no N+1. `TimeProvider` inyectado. Hash agregado de pares `(posId, productId)` de filas **asignadas activas**, ordenados. **Validación:** ninguna query POS usa `PaginationConstants.MaxPageSize`; las ventas no joinean `Return`.

## 6. Tests de integración y de esquema

- [ ] 6.1 Integración del catálogo (cliente con header de API Key; Testcontainers): `CatalogFeed_WithSinceCursor_ReturnsOnlyChangedRows`; `CatalogFeed_EmitsTombstoneWhenProductDeactivated`; `CatalogFeed_ExcludesUnapprovedProfiles`; `CatalogFeed_NeverApprovedProduct_IsAbsent`; `CatalogFeed_EmitsTombstoneWhenProfileUnapproved`; `Feed_ReturnsAggregateHashForDriftDetection` (mismo hash en dos páginas; cambia al salir un indexable); página ≤ 50; payload sin `dataOrigin` / `quantity`. **Validación:** esos tests verdes.

- [ ] 6.2 Integración de auth con **cliente HTTP fresco**: `Feed_WithUserJwt_Returns401`; `Feed_WithC03Token_Returns401`; `Feed_MissingApiKey_Returns401`; `Feed_WrongApiKey_Returns401`; `Feed_WithValidApiKey_Returns200`. No reutilizar el `HttpClient` de login. **Validación:** 401 (no 403) en los cuatro negativos; 200 con la key.

- [ ] 6.3 Integración del POS: `PosAvailabilityFeed_ReturnsBucketNotExactQuantity` (0 / 1-2 / 3+ y JSON sin `quantity`); `PosAvailabilityFeed_Unassigned_EmitsTombstone`; `PosAvailabilityFeed_SalesWindows_DoNotSubtractReturns`; `PosAvailabilityFeed_PageSize_Is200`. **Validación:** esos tests verdes; catálogo sigue en 50.

- [ ] 6.4 `Model_HasNoPendingMigrationDifferences` sigue verde. Medir baseline de `dotnet test` (nombres de fallos, no el recuento) y confirmar que los **nuevos** nombres no están en el conjunto rojo previo. **Validación:** el test de snapshot de modelo verde; `git diff` de `backend/src/JoiabagurPV.Infrastructure/Data/Migrations/` vacío.

## 7. Documentación y verificación de alcance

- [ ] 7.1 Escribir `Documentos/Proyecto Final AIEng/informes/c12-catalog-autobulk-runbook.md` al final, cuando los feeds existan: para qué (puerta de C13), quién/cuándo (después de archivar C12, antes del apply de C13), condiciones y comandos PowerShell del ticket, lote 50 / 24 llamadas, `force: false`, verificación posterior (`ReviewStatus = 2` y smoke del feed), tiempo 15–40 min, coste ≈ 6–12 USD a gpt-4o (recalcular si el modelo es mini), qué no hacer. **No** ejecutar el lote. **Validación:** el fichero existe y un lector puede correrlo sin abrir C13.

- [ ] 7.2 Enlazar HU-AIENG-012 en `Documentos/epicas.md` (EP14). Mencionar el feed como lector HTTP en `Documentos/modelo-de-datos.md` **sin** entidad nueva. **Validación:** un lector de la épica llega a los dos `GET`, a la API Key y a «sin migración / sin push».

- [ ] 7.3 Confirmar alcance negativo: `git diff` no toca `ai-service/openapi.json`, `ai-service/src/`, `ai-service/migrations/`, `frontend/`, `terraform/`. `/v1/index/sync` sigue siendo el stub C13. No hay TODO/FIXME sin tarea de seguimiento. **Validación:** diffs vacíos en esas rutas; `openspec validate --all --strict` reporta `0 failed`.
