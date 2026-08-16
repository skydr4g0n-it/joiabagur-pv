> **Línea de corte (regla 5 del plan).** Los grupos 1-3 forman una mitad archivable por sí sola:
> liberan el turno de migración de EF Core y desbloquean a C12. Los grupos 4-8 son la segunda mitad,
> no llevan migración y conviven con el C07 del compañero. Si la sesión se desborda, se corta ahí.

## 1. Línea base y andamiaje

- [x] 1.1 Medir la línea base de la suite de .NET **antes de escribir nada** (`git stash push -u` → `dotnet test` → `git stash pop`) y guardar la **lista de nombres** de los tests que ya fallan. `CLAUDE.md` documenta que el recuento es poco fiable porque algunos fallos dependen del orden: la comparación al final será por nombres.
  - Árbol ya commiteado en `f7488c1`, así que no hizo falta `stash`: la ejecución sobre el commit **es** la línea base. Dos ejecuciones seguidas dieron **48** y **51** fallos, todos de `IntegrationTests` — la inestabilidad por orden que `CLAUDE.md` documenta, confirmada de primera mano. Unión de nombres guardada; los tests de esquema de C04 **pasan**, luego Testcontainers funciona.
- [x] 1.2 Medir la línea base de `ai-service` con `uv run --system-certs pytest` y anotar el total. Verificación: parte de cero fallos.
  - **127 passed, 0 failed.**

## 2. Entidad y persistencia

- [x] 2.1 Crear `ProfileReviewStatus` (`Pending`, `Approved`, `Rejected`) y `ProfileReviewOrigin` (`AutoBulk`, `Human`) en `JoiabagurPV.Domain/Enums/`. Verificación: `dotnet build` limpio.
- [x] 2.2 Crear `ProductAiProfile` en `JoiabagurPV.Domain/Entities/`, con valores vigentes, procedencia por campo, propuesta original, hash de entradas y bloque de revisión. **Sin propiedad de navegación desde `Product`**. Documentar en el propio tipo por qué `SourceHash` no es el `source_hash` de C11. Verificación: `dotnet build` limpio.
- [x] 2.3 Escribir `ProductAiProfileConfiguration` declarando **a mano** lo que falla en silencio: las siete columnas `jsonb`, el **índice único** sobre `ProductId`, los índices `(ReviewStatus)` y `(ReviewStatus, ReviewOrigin)`, y `RESTRICT` en las dos claves foráneas. Verificación: `dotnet build` limpio y `Model_HasNoPendingMigrationDifferences` en rojo (aún no hay migración).
- [x] 2.4 Registrar el `DbSet` en `ApplicationDbContext` y generar **una única migración**. Verificación: `Model_HasNoPendingMigrationDifferences` vuelve a verde.
  - `20260816113157_AddProductAiProfile`. **Aviso para quien repita esto:** generarla con `--no-build` produce una migración **vacía y sin error** —usa el ensamblado anterior a la entidad—, y `ef migrations remove` no la puede deshacer sin conexión a la base de datos. Hay que borrar los dos ficheros a mano y regenerar compilando.

## 3. Detectores de esquema

- [x] 3.1 Extender `SchemaAssert` con **una sola pregunta nueva**: si un índice es único. Nada más — es el guardarraíl que C04 se puso a sí mismo. Verificación: compila y los tests de esquema de C04 siguen verdes.
- [x] 3.2 Escribir `ProductAiProfileSchemaTests` con `Migration_JsonColumnsAreJsonbNotText`, `Migration_ProductIdIsUnique` y `Migration_DeletingProduct_IsRestrictedNotCascaded`. Verificación: los tres pasan con Testcontainers.
- [x] 3.3 **Romper a propósito** lo que cada detector vigila —cambiar una columna a `text`, quitar la unicidad, dejar el borrado en cascada—, comprobar que el test **falla**, y revertir. Un detector que nadie ha visto fallar es él mismo un fallo mudo.
  - Las tres roturas aplicadas a la vez sobre la migración: fallaron **exactamente** los tres detectores correspondientes y ninguno más (3 con error / 26 superados). Revertido: 50 verdes.

## 4. Contrato de enriquecimiento renegociado

- [x] 4.1 Ampliar `ai-service/src/jbg_ai/api/schemas/enrich.py`: envoltorio común con `confidence` y `source` (`rule` \| `inferred`), campos `piece_type`, `stone_type` y `size_label`, desglose de `tags` en `color_tags` / `style_tags` / `occasion_tags`, y `prompt_version` en la respuesta. Verificación: `uv run --system-certs pytest` — el test de snapshot debe ponerse **rojo**, que es la señal esperada.
- [x] 4.2 Actualizar `enrich_products_stub` para que siga siendo determinista y sin reloj, y produzca **al menos un campo sensible `inferred` y al menos uno `rule`**, más etiquetas por encima y por debajo de un umbral razonable. Sin esa variedad, los tests de integración no distinguen nada.
- [x] 4.3 Escribir `test_enrich_profile_carries_source_per_field` y el test de variedad del stub en `ai-service/tests/api/`. Verificación: ambos pasan.
  - Seis tests nuevos: provenance por campo, campos sensibles y desglose de etiquetas, ambas procedencias en el stub, umbral cruzado por ambos lados, `prompt_version` y determinismo.
- [x] 4.4 Regenerar `ai-service/openapi.json` con el *one-liner* canónico del README. Verificación: `test_openapi_snapshot_is_stable` vuelve a verde y `git diff` sobre el snapshot muestra **solo** los campos de enriquecimiento.
  - El snapshot se puso en rojo tras 4.1, como estaba previsto, y volvió a verde al regenerarlo. Diff: +71/−6 líneas, todas bajo los esquemas de enriquecimiento. Suite Python **133 passed** (127 de línea base + 6).

## 5. Scope de catálogo — dos cierres independientes

- [x] 5.1 Python: hacer `pos_id` opcional en `ServicePrincipal`, parametrizar los claims exigidos en `decode_service_token` y añadir `get_catalog_principal` en `deps.py`. `get_service_principal` **no cambia**. Verificación: los tests de autenticación existentes siguen verdes.
- [x] 5.2 Pasar `routers/enrich.py` a `get_catalog_principal`. Recuperación, asistencia e inventario se quedan como están. Verificación: `test_catalog_token_without_pos_is_accepted_on_enrich` y `test_catalog_token_is_rejected_on_retrieval` pasan.
- [x] 5.3 .NET: añadir `AiCallScope.ForCatalog(userId, role)`, pasar `PointOfSaleId` a `Guid?` y exponer la clase de scope. `ForPointOfSale` conserva intactas sus validaciones. Verificación: `AiCallScopeTests` ampliado en verde.
- [x] 5.4 Emitir `pos_id` en `AiServiceTokenFactory` **solo** cuando el scope lo tenga, y hacer que `SearchAsync` rechace un scope de catálogo antes de emitir la petición. Verificación: `BuildToken_ForCatalogScope_OmitsPosClaim` y `SearchAsync_WithCatalogScope_IsRejected` en verde, y el test que afirma el conjunto exacto de claims sigue pasando para el scope con punto de venta.
  - **Efecto colateral que hubo que resolver:** `PointOfSaleId` pasando a `Guid?` rompió la compilación de `ProductSearchEventService` (C04). Se resuelve con una guarda explícita **dentro** del `try` existente, de modo que se traga y se registra como cualquier otro fallo: la garantía de C04 —la telemetría nunca rompe una búsqueda— pesa más que sacar a la luz un error de programación que el compilador ya no puede cazar.

## 6. Cliente de enriquecimiento

- [x] 6.1 Añadir los DTO de enriquecimiento en `Application/DTOs/Ai/`, con `confidence` y `source` como valores de primera clase y los campos nulables mapeados como tales. Verificación: `dotnet build` limpio.
- [x] 6.2 Añadir `EnrichAsync` a `IAiGatewayClient` y a `AiGatewayClient`, reutilizando la traducción de estados, el contador de intentos y el logging existentes. El 501 se traduce a un resultado distinguible. Verificación: tests de mapeo con `HttpMessageHandler` falso.
- [x] 6.3 Registrar el cliente con nombre `ai-enrich` con `EnrichTimeoutMs` configurable, **cortacircuitos aislado** y **sin reintento**. Verificación: `AiGatewayRegistrationTests` ampliado comprueba que un fallo de enriquecimiento no abre el circuito de recuperación y que se emite **una sola** petición.
- [x] 6.4 Extender `AiContractSnapshotTests` a los modelos de enriquecimiento. Verificación: en verde contra el snapshot regenerado, y en rojo si se altera un nombre o una nulabilidad.
  - Siete modelos más, **y una aserción por nombre sobre `source`**: el barrido genérico solo comprueba que las propiedades de .NET existan en el contrato, no al revés, así que una renegociación futura podría quitar la procedencia sin que nada se pusiera rojo.

## 7. Política de enrutado y caso de uso

- [x] 7.1 Crear las opciones de umbrales con validación al arranque (rango 0-1), siguiendo el patrón de `AiGatewayOptions`. Verificación: test de que un umbral fuera de rango impide arrancar y nombra la clave.
- [x] 7.2 Implementar la política de enrutado como **clase pura**, sin base de datos ni HTTP. Verificación: `Routing_WhenSensitiveFieldInferred_MarksPendingReview`, `Routing_WhenSensitiveFieldFromRule_DoesNotRequireReview`, `Routing_WhenTagConfidenceAboveThreshold_AutoApproves` y el caso de etiquetas bajo umbral, todos sin contenedor y en milisegundos.
- [x] 7.3 Implementar el cálculo del `SourceHash` de las entradas (SKU + nombre + descripción + colección, orden fijo, SHA-256). Verificación: test de estabilidad ante la misma entrada y de cambio ante entrada distinta.
- [x] 7.4 Implementar `ProductAiProfileService`: descarte por hash **antes** de llamar al gateway, mapeo de la propuesta, aplicación de la política, modos `Routed` y `AutoBulk`, y persistencia en una transacción. En `AutoBulk`, `FieldConfidenceJson` y `FieldSourceJson` siguen registrando lo que el enrutado habría dicho. Verificación: `EnrichBatch_WhenSourceHashUnchanged_SkipsProductWithoutCallingGateway`, `EnrichBatch_WithAutoBulkMode_ApprovesButRecordsWhatRoutingWouldHaveSaid` y `Profile_StoresMultipleMaterials`.
- [x] 7.5 Implementar el reset de revisión al cambiar el hash —vuelta al resultado del enrutado, origen a masivo, campos de revisión limpiados y traza en el log— y la opción `force`. Verificación: tests de ambos caminos.

## 8. Endpoint, verificación y documentación

- [x] 8.1 Crear `AiCatalogController` con `POST /api/ai/catalog/enrich-batch`, `[Authorize(Roles = "Administrator")]`, validador de FluentValidation **invocado explícitamente** (este proyecto no cablea pipeline automático) y traducción del 501 a 503 nombrando C09. Verificación: `EnrichBatch_WithMoreThanContractBatchSize_ReturnsBadRequest` y el test del 503.
- [x] 8.2 Escribir `EnrichBatch_AsOperator_Returns403` pidiendo un **cliente nuevo a la factoría**, no el compartido de la clase, que conserva las cookies de logins previos. Verificación: pasa, y el caso sin autenticar devuelve 401.
- [x] 8.3 Prueba manual extremo a extremo con `docker compose up` y `STUB_MODE=true`: enriquecer un lote como administrador, repetirlo y comprobar `skippedUnchanged` con **cero llamadas al gateway**, y repetirlo como operador esperando 403.
  - Ejecutada contra el contenedor real: token de catálogo **sin `pos_id`** → 200 en `/v1/enrich/products`, con ambas procedencias (`piece_type: inferred`, `size_label: rule`), las tres listas de etiquetas y sin `tags` plano; **el mismo token → 401 en `/v1/retrieval/products`**; token con punto de venta → 200 en recuperación. El 403 del operador, el 401 anónimo y la idempotencia se cubren con tests automáticos (`AiCatalogControllerTests`, `EnrichBatch_WhenSourceHashUnchanged_SkipsProductWithoutCallingGateway` con mock estricto), que es donde deben vivir.
- [x] 8.4 Comparar la suite de .NET contra la línea base de 1.1 **por nombres de test**, y verificar `uv run --system-certs pytest` en verde. Verificación: ningún nombre nuevo en la lista de fallos.
  - Línea base **51** → después **46** y **48** en dos pasadas. Aparecieron tres nombres de `InventoryIntegrationTests` que no estaban en la línea base, así que **no se dieron por flakes sin comprobarlo**: (1) pasan en aislamiento, (2) la segunda pasada post-cambio ya no los incluye y trae otros distintos, sobre código idéntico, y (3) el total baja en lugar de subir. La clase baraja su conjunto de fallos entre ejecuciones, que es justo lo que `CLAUDE.md` documenta. **Ningún test nuevo de este change falla en ninguna pasada.**
- [x] 8.5 Actualizar la documentación de contexto: `Documentos/modelo-de-datos.md` (entidad, índices, relaciones), `Documentos/epicas.md` (EP12), `backend/README.md` (endpoint y matriz de autorización), `ai-service/README.md` (marcador de change y contrato), `openspec/project.md` (entidades clave).
- [x] 8.6 Registrar en el **§0 del plan de changes** las dos desviaciones de la ficha: la zona real son seis carpetas y no tres, y C08 renegocia el contrato de enriquecimiento que la ficha daba por suficiente.
- [x] 8.7 Ejecutar **`openspec validate --all --strict`** y comprobar que reporta `0 failed`. La forma sin `--all` no valida nada y no cuenta como aprobado.
