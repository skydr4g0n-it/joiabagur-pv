# QA — C18a `add-family-suggestion-and-approval`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-31 · **Rama:** `c18a-add-family-suggestion-and-approval`, creada desde `ai-eng` en `f5212a7`
> **Alcance al cierre:** 80 tests nuevos en `ai-service` · 22 en `backend` · 64/64 tareas · 4/4 artefactos
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| Python | 3.11 · `uv` **con `--system-certs` en toda llamada**, según `CLAUDE.md` |
| .NET | 10.0 · solución en `backend/src/JoiabagurPV.sln` — **no** en `backend/`, donde `dotnet test` sale con **código 0** sin ejecutar nada |
| PostgreSQL | `jpv-pv-postgres` (pgvector/pg15) en `:5433`, con el corpus real de 1.200 documentos |
| Contrato | `ai-service/openapi.json` — **se regenera a propósito**: novena ruta. Ver §5 |
| Migraciones | **Ninguna.** `git diff` vacío en `Migrations/` y en `ai-service/migrations/` |
| Freeze C11/C13 | `git diff` **vacío** en `indexing/embeddings.py` y en `indexing/source_text.py` |
| Frontend | **No se toca.** `git diff` vacío en `frontend/` |
| Respaldo | `pre-c18a.dump` (12 MB, esquemas `public` y `ai`) antes de escribir una sola fila |

---

## 1. Líneas base, medidas con el árbol limpio

Tomadas **antes** de tocar nada, y guardadas **por nombre de test**, no por recuento — la regla de `CLAUDE.md`.

| Suite | Resultado | Nombres en rojo |
|---|---|---|
| `ai-service` | 2 failed / 356 passed | `test_malformed_exclusions_are_ignored`, `test_trace_id_appears_in_stage_logs` (ambos en `tests/retrieval/test_orchestrator.py`) |
| backend | 47 failed / 850 passed (897) | 47 nombres guardados; **15 de ellos** son variantes de `_WithoutAuth_` / `_Unauthenticated_` |

> **Incidencia de método, en la primera pasada.** Lancé el baseline del backend con `| tail -30` y guardé **28 de los 47 nombres** creyéndolos completos. Un baseline incompleto es peor que ninguno: la comparación de cierre habría señalado 19 regresiones inexistentes. Relanzado sin tubería, verificado que `grep -c '\[FAIL\]'` da 47 y que los nombres únicos son 47.

---

## 2. Comparación de cierre, por nombres

### `ai-service`

| | Fallos | Pasan | Total |
|---|---|---|---|
| Baseline | 2 | 356 | 358 |
| Cierre | **2** | 436 | 438 |

Los dos son **los mismos nombres**. Sin regresión. 80 tests nuevos.

### Backend

| | Fallos | Pasan | Total |
|---|---|---|---|
| Baseline | 47 | 850 | 897 |
| Cierre | 50 | 857 | **907** |

**El recuento no sirve aquí, y compararlo habría sido el error.** Diferencia por nombres: **seis nuevos y tres que dejan de fallar, los nueve en `InventoryIntegrationTests`**.

```
NUEVOS     Admin_AccessCentralizedInventory_ShouldSucceed
           ExcelImport_NegativeQuantityWithSufficientStock_ShouldReduceStockAndCreateMovement
           GetStock_WithNonExistentPOS_ShouldReturnEmpty
           Operator_AdjustStock_ShouldBeForbidden
           StockAdjustment_WithNonExistentProduct_ShouldReturnBadRequest
           StockValidation_WithSufficientStock_ShouldAllowOperation
YA NO      AssignProduct_WithNonExistentPOS_ShouldReturnNotFound
           StockValidation_WithUnassignedProduct_ShouldReturnError
           ReturnsControllerTests.GetReturnById_NonExistentReturn_ReturnsNotFound
```

Ejecutada `InventoryIntegrationTests` **en aislamiento** falla **ocho**, y con nombres distintos otra vez — `AssignProduct_WithValidProduct_ShouldSucceed` y `EndToEnd_AssignAdjustView_Workflow` aparecen sólo ahí. **Tres ejecuciones, tres conjuntos distintos.** Es la dependencia de orden que `CLAUDE.md` advierte, agitada porque la clase de test nueva entra en la misma colección y cambia el orden. **Ninguna regresión es de C18a**, y los 22 tests nuevos del backend pasan.

---

## 3. Escenarios de las specs, uno a uno

### `family-suggestion` (nueva)

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Agrupa por raíz dentro de un tipo · Sufijo de talla | `test_groups_products_differing_only_in_size_suffix` | ✅ |
| Agrupa por raíz dentro de un tipo · Capitalización inconsistente | `test_inconsistent_capitalisation_does_not_split_family` (`Anillo erizo de mar` × 3 + `Anillo Erizo de mar XL`) · `test_lowercase_size_suffix_is_recognised` (`Xs` real) | ✅ |
| Agrupa por raíz dentro de un tipo · Nunca cruza tipos de pieza | `test_does_not_group_across_piece_types` · propiedad `test_a_proposal_never_mixes_piece_types` (5 semillas) | ✅ |
| Agrupa por raíz dentro de un tipo · Sin tipo no agrupa con nadie | `test_null_piece_type_groups_with_nobody` | ✅ |
| La puerta nombra lo que excluye · Sin tipo, nombrado y no descartado | `test_null_piece_type_groups_with_nobody` (afirma `excluded[0].reason == "no_piece_type"`) · propiedad `test_every_input_product_is_proposed_excluded_or_unmatched` | ✅ |
| La puerta nombra lo que excluye · Ya en familia, contados y no listados | `test_products_already_in_a_family_are_counted_not_listed` | ✅ |
| Material fusiona, no se retira de la raíz · Fusión por un token | `test_merges_groups_differing_in_one_material_token` (rejilla `conchiglie` 2×2) | ✅ |
| Material fusiona · Pareja sólo de material | `test_size_is_removed_from_any_position_not_only_the_suffix` (`lapislázuli`) | ✅ |
| Material fusiona · Raíz con material no se degrada | `test_material_in_root_is_not_stripped` (`Anillo plata S/M/L/XL`) | ✅ |
| Material fusiona · Fusión degenerada rechazada y reportada | `test_degenerate_root_is_rejected_and_reported` (`Encargos`) · `test_bare_piece_type_root_is_rejected` (`Cadena`) | ✅ |
| Material fusiona · Miembros indistinguibles, rechazados | `test_two_indistinguishable_products_are_rejected_not_proposed` | ✅ |
| Veto relativo · Marcado, no eliminado | `test_veto_flags_member_without_removing_it` (3 miembros siguen siendo 3) | ✅ |
| Veto relativo · Ningún umbral global decide | `test_no_global_threshold_decides_membership` (similitud 0,62 y nadie marcado) · `test_a_stranger_inside_the_margin_does_not_flag` | ✅ |
| Veto relativo · El margen viene de configuración | `test_margin_is_read_from_configuration_not_hard_coded` · `test_margin_is_honoured_as_given` | ✅ |
| Etiquetas verbatim y orden canónico · Escala en palabra tal cual | `test_variant_label_is_verbatim_not_translated` (`mini` ≠ `XS`) · `test_accented_label_keeps_its_spelling` (`pequeña`) | ✅ |
| Etiquetas verbatim · Orden por rango, no alfabético | `test_members_ordered_by_canonical_rank_not_alphabetically` (`S,M,L,XL`) · propiedad `test_positions_are_consecutive_from_zero` | ✅ |
| Etiquetas verbatim · La pieza base no lleva etiqueta | `test_base_member_has_null_variant_label` | ✅ |
| Etiquetas verbatim · Etiqueta compuesta única en dos ejes | `test_two_axis_family_labels_stay_unique` · `test_a_material_every_member_shares_is_not_a_label` · propiedad `test_variant_labels_are_unique_within_a_family` | ✅ |
| Proponer no escribe · Pedir sugerencias no toca el catálogo | `SuggestFamilies_ReturnsProposals_WithoutWritingAnything` *(ver §8.1)* · verificado en la ejecución real: tras `suggest`, familias = 0 | ✅ |
| Proponer no escribe · Sólo se persiste el subconjunto devuelto | `ApplyFamilySuggestions_RecordsAiApprovedOriginWithApprover` (1 familia de 1 propuesta) | ✅ |
| Proponer no escribe · Repetir converge | `test_products_already_in_a_family_are_counted_not_listed` · ejecución real: 2ª `suggest` tras aplicar → `already_in_family` distinto de 0 | ✅ |
| Aplicar registra la aprobación · Origen asistido | `ApplyFamilySuggestions_RecordsAiApprovedOriginWithApprover` | ✅ |
| Aplicar registra · La creación manual sigue siendo Manual | `CreateFamily_StillRecordsManualOrigin` | ✅ |
| Aplicar registra · Un conflicto no tumba el lote | `ApplyFamilySuggestions_ReportsConflict_WithoutPartialFamily` | ✅ |
| Aplicar registra · Los que entran son visibles al pull incremental | `ApplyFamilySuggestions_MakesMembersVisibleToAnIncrementalPull` · ejecución real: `upserted 486` | ✅ |
| Restringido a administradores · Un operador no puede | `SuggestFamilies_ReturnsForbidden_ForOperator` · `ApplyFamilySuggestions_ReturnsForbidden_ForOperator` (y verifica que no se creó nada) | ✅ |
| Restringido a administradores · Anónimo rechazado | `SuggestFamilies_ReturnsUnauthorized_ForAnonymous` (**cliente nuevo de la factoría**) · `test_route_requires_the_service_token` | ✅ |
| Determinista y sin LLM · Dos pasadas coinciden | `test_grouping_is_deterministic_for_the_same_catalogue` · propiedad `test_rerunning_over_the_same_catalogue_agrees` (5 semillas) · `test_stub_is_deterministic` | ✅ |
| Determinista y sin LLM · Ninguna llamada al proveedor | `test_stub_opens_no_database_connection` (con `forbid_network`) · el paquete no importa `EmbeddingClient`: `grep` vacío | ✅ |

### `ai-service-api-contracts` (delta)

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Superficie congelada · Cada ruta responde su modelo | `test_stub_matches_response_schema` · la suite `tests/api/` completa (124 passed) | ✅ |
| Superficie congelada · `/health` sin cambios | `test_health_*` intactos; `/health` no aparece en el diff | ✅ |
| Superficie congelada · La ruta exige el token | `test_route_requires_the_service_token` (401/403) | ✅ |
| Superficie congelada · El snapshot regenerado casa con el esquema vivo | `test_openapi_snapshot_is_stable` **en rojo antes** de regenerar y en verde después · `test_snapshot_covers_the_frozen_surface` con las nueve rutas | ✅ |
| Contrato de sugerencia · Miembros en orden con etiquetas | `test_members_carry_nullable_variant_and_ordered_positions` | ✅ |
| Contrato de sugerencia · Miembro marcado, reportado y retenido | `test_a_flagged_member_reports_its_margin` | ✅ |
| Contrato de sugerencia · Grupos rechazados reportados | `test_stub_populates_all_three_lists` | ✅ |
| Contrato de sugerencia · Stub sin base de datos | `test_stub_opens_no_database_connection` | ✅ |

### `ai-gateway-client` (delta)

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Cliente tipado expone sugerencia · Sin truncar | `SuggestFamiliesAsync_WhenServiceReturns200_SurfacesAllThreeListsWithoutTruncating` · `SuggestFamiliesAsync_KeepsMemberOrderAndTheReviewMark` | ✅ |
| Cliente tipado · Variante ausente a null explícito | `SuggestFamiliesAsync_MapsAnAbsentVariantToNullAndNotToEmptyString` | ✅ |
| Cliente tipado · Nombres de cable del contrato | `FamilySuggestRequest_SerializesInSnakeCase` · `FamilySuggestResponse_DeserializesTheSnakeCaseContract` | ✅ |
| Fallos distinguibles · 501 frente a indisponible | `SuggestFamiliesAsync_WhenRouteIsNotImplemented_RaisesTheNotImplementedError` · `..._WhenServiceFails_RaisesUnavailableAndNotNotImplemented` · `..._WhenCredentialsAreRejected_RaisesTheConfigurationError` | ✅ |
| Fallos distinguibles · Sin propuesta degradada | `SuggestFamiliesAsync_ProducesNoProposalsWhenItFails` | ✅ |

Extra de alcance, no exigido por spec: `SuggestFamiliesAsync_RejectsAPointOfSaleScope` y `..._RejectsAMaxProposalsOutsideTheContract`.

### `product-family` (delta)

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Aprobación asistida registra su aprobador · Origen, aprobador e instante | `ApplyFamilySuggestions_RecordsAiApprovedOriginWithApprover` | ✅ |
| Aprobación asistida · La manual sigue distinguible | `CreateFamily_StillRecordsManualOrigin` | ✅ |
| Aprobación asistida · Estampa el watermark como la manual | `ApplyFamilySuggestions_MakesMembersVisibleToAnIncrementalPull` *(afirmado sobre el feed; ver §8.2)* | ✅ |
| Aprobación asistida · Conflicto reportado sin familia parcial | `ApplyFamilySuggestions_ReportsConflict_WithoutPartialFamily` | ✅ |
| Aprobación asistida · Aprobar dos veces no escribe nada | `ApplyFamilySuggestions_AppliedTwice_WritesNothingTheSecondTime` *(escenario reescrito; ver §8.3)* | ✅ |

**Totales.** 29 escenarios en `family-suggestion` + 8 en `ai-service-api-contracts` + 5 en `ai-gateway-client` + 5 en `product-family` = **47**. Los 47 tienen test nombrado o comprobación ejecutada.

---

## 4. Nombres exigidos por `tasks.md`

Todos existen y están en verde. `3.6b` se añadió durante el apply, al revisarse D12.

| Nombre | Fichero |
|---|---|
| `test_groups_products_differing_only_in_size_suffix` · `test_inconsistent_capitalisation_does_not_split_family` | `tests/families/test_grouping.py` |
| `test_does_not_group_across_piece_types` · `test_null_piece_type_groups_with_nobody` | `tests/families/test_grouping.py` |
| `test_merges_groups_differing_in_one_material_token` · `test_material_in_root_is_not_stripped` | `tests/families/test_grouping.py` |
| `test_degenerate_root_is_rejected_and_reported` | `tests/families/test_grouping.py` |
| `test_veto_flags_member_without_removing_it` · `test_no_global_threshold_decides_membership` | `tests/families/test_veto.py` |
| `test_margin_is_read_from_configuration_not_hard_coded` | `tests/families/test_veto.py` |
| `test_family_vocabulary_reuses_enrichment_terms` (3.6b) | `tests/families/test_vocabulary.py` |
| `test_variant_label_is_verbatim_not_translated` · `test_base_member_has_null_variant_label` | `tests/families/test_grouping.py` |
| `test_members_ordered_by_canonical_rank_not_alphabetically` · `test_two_axis_family_labels_stay_unique` | `tests/families/test_grouping.py` |
| `test_grouping_is_deterministic_for_the_same_catalogue` | `tests/families/test_grouping.py` |
| Tests de propiedades sobre invariantes (3.10) | `tests/families/test_invariants.py`, 7 propiedades × 5 semillas |
| `ApplyFamilySuggestions_RecordsAiApprovedOriginWithApprover` · `CreateFamily_StillRecordsManualOrigin` | `FamilySuggestionControllerTests.cs` |
| `ApplyFamilySuggestions_ReportsConflict_WithoutPartialFamily` | `FamilySuggestionControllerTests.cs` |
| `SuggestFamilies_ReturnsForbidden_ForOperator` · `SuggestFamilies_ReturnsUnauthorized_ForAnonymous` | `FamilySuggestionControllerTests.cs` |

**Dos nombres del ticket cambiaron, y el motivo está en §8.2:** `ApplyFamilySuggestions_StampsUpdatedAtOfEnteringProducts` e `IndexFeed_EmitsExactlyTheStampedProducts_AfterApply` se fusionaron en `ApplyFamilySuggestions_MakesMembersVisibleToAnIncrementalPull`.

---

## 5. Dos guardas verificadas **fallando**

Un test que no muerde no sirve, y este proyecto lleva encontrando de esos.

| Guarda | Mutación | Resultado |
|---|---|---|
| Reutilización de vocabulario | Añadida a propósito una lista `["plata", "oro"]` dentro de `families/vocabulary.py` | `test_no_term_list_is_declared_inside_the_families_package` **falla**; al retirarla, verde |
| Deriva del contrato | Ruta nueva **antes** de regenerar el snapshot | `test_openapi_snapshot_is_stable` **falla**; tras regenerar, verde. La lista explícita de `test_snapshot_covers_the_frozen_surface` se actualizó aparte, porque el snapshot por sí solo pasaría sobre cualquier fichero regenerado sin que nadie note un camino nuevo |

El test del feed (§3, `product-family`) no necesita mutación: muerde por los dos lados. `Contain` fallaría con página vacía y `NotContain` fallaría si el feed emitiera todo — y ambas cosas ocurrieron durante el desarrollo.

---

## 6. Alcance negativo, verificado con `git diff` contra `ai-eng`

| Lo que **no** debía cambiar | Comprobación |
|---|---|
| Migraciones de EF Core | diff **vacío** en `Data/Migrations/` |
| Migraciones de Alembic | diff **vacío** en `ai-service/migrations/` |
| `frontend/` | diff **vacío** — la pantalla es C18b |
| `indexing/embeddings.py` | diff **vacío** (freeze de C11) |
| `indexing/source_text.py` | diff **vacío**: la plantilla no cambia, sólo el contenido de 486 filas |
| `terraform/` y `.github/` | diff **vacío** |
| `preprocessing_id` | sigue `source-text/v1`; un único `embedding_version` en las 1.168 filas |
| Tabla de propuestas | **no existe**: `apply` recibe de vuelta lo aceptado |

---

## 7. Ejecución sobre datos reales

Por el camino completo `.NET → jbg-ai`, no por un script suelto.

| | |
|---|---|
| Familias / miembros | **156 / 486**, cero conflictos |
| `Origin = AiApproved` con aprobador e instante | 156 / 156 |
| Productos en dos familias | **0** |
| Retiradas del índice | **32** con `ReviewStatus = Rejected`; **las 32 siguen `IsActive`** |
| Sincronización incremental | `upserted 486 · deleted 32 · skipped 0 · failed 0` |
| Índice final | 1.168 documentos · 486 con `family_id` · 467 con `variant_label` · **0** sin embedding · **0** en `ai.sync_failure` |

Detalle y hallazgos de catálogo: [`informes/c18a-family-suggestion-report.md`](../../../Documentos/Proyecto%20Final%20AIEng/informes/c18a-family-suggestion-report.md).

---

## 8. Incidencias y huecos de esta pasada

### 8.1 El escenario «pedir sugerencias no toca el catálogo» no tiene test de integración propio

`SuggestFamilies_ReturnsProposals_WithoutWritingAnything` está en el ticket y **no se escribió**: exigiría un doble del gateway devolviendo propuestas, y el fichero de integración usa el gateway real. Está cubierto **por dos vías indirectas**: la ejecución real —tras `suggest` sobre 1.200 productos, `ProductFamilies` seguía en 0— y el hecho de que el controlador no inyecta `IProductFamilyService` en esa acción. **Hueco reconocido**, no cerrado.

### 8.2 El test del watermark cambió de forma, y el cambio es el hallazgo

Lo escribí afirmando que `apply` estampa `Product.UpdatedAt` —que es lo que D1 decía— y **falló**: el timestamp no se movía. `CreateAsync` nunca estampó, y no lo necesita: el watermark del feed es `greatest(Product, perfil, familia cuando es miembro actual)`, así que **crear** una familia lo mueve por el `UpdatedAt` de la propia familia. El estampado hace falta en el **reemplazo**, donde quien sale deja de unirse a la fila de familia.

La regla no cambia —se escribe siempre por el servicio— pero el argumento correcto es que el servicio mantiene el watermark coherente en **las dos** direcciones. El test pasó a afirmar sobre el feed, que es el requisito; el timestamp era el detalle de implementación. Corregido en `design.md`.

**Segundo tropiezo del mismo test:** el feed hace *join interno* con `ProductAiProfiles` y exige el perfil aprobado, así que los productos del fixture —creados sin perfil— eran invisibles al feed hicieran lo que hicieran con las familias. La página volvía vacía. Laguna del montaje, no del flujo.

### 8.3 Un escenario de spec describía algo que el sistema no hace

«Aprobar la misma sugerencia dos veces no escribe nada» daba a entender un cortocircuito como el de C07 para listas idénticas. Lo que ocurre es que la segunda aprobación **toma el camino del conflicto**: los productos ya pertenecen a la familia que creó la primera. No se escribe nada —la afirmación se cumple— pero se **reporta**, que es mejor que absorberlo en silencio. **El escenario se reescribió para describir el sistema**, no la suposición.

### 8.4 El veto se implementó primero con la prueba equivocada

`mediana − k·MAD` contra el centroide es una prueba **dentro** del grupo; la medición que la justificaba era **entre** grupos. Disparaba al **16,9 %**, marcando al miembro menos típico de cada clúster — algo que todo clúster tiene. Sustituida por la prueba comparativa. Y el **1,7 %** que la exploración midió describía familias de sufijo de talla solamente: sobre el algoritmo entregado la cifra honesta es **3,1 %**. Corregido en `design.md`, el ticket, la HU y la spec.

### 8.5 `ai-gateway-client` estuvo sin cobertura hasta la revisión de este QA

Sus cinco escenarios no tenían un solo test. Se detectó al recorrer las specs una a una para escribir §3 — que es exactamente para lo que sirve ese recorrido. Cerrado con `AiGatewayFamilySuggestionTests.cs`, 11 tests.

### 8.6 Dos obstáculos de entorno, ninguno del producto

Ambos son de desarrollo local en Windows, **no tocan el repositorio**, y están documentados en `ai-service/README.md` porque cuestan una tarde si aparecen sin aviso.

**Uvicorn instala el `ProactorEventLoop`** y psycopg no puede usarlo: `/health` reporta `database: unavailable` sin más pistas. Fijar la política antes de `uvicorn.run` no basta — uvicorn instala la suya. Hay que arrancar con `loop="none"`.

**`litellm` verifica TLS contra `certifi`**, no contra el almacén del sistema. El síntoma engaña: `curl` con la misma clave devuelve **200** y `httpx` devuelve `CERTIFICATE_VERIFY_FAILED`, y el indexador lo traduce a `OpenAIException - Connection error` en `ai.sync_failure`, que no menciona TLS ni certificados. Es la hermana en tiempo de ejecución del `--system-certs` que el README ya documentaba.

---

## 9. Puertas del proyecto

| Puerta | Resultado |
|---|---|
| `openspec validate --all --strict` | **46 passed, 0 failed** |
| `openspec status --change` | 4/4 artefactos |
| `dotnet build JoiabagurPV.sln` | sin errores |
| `uv run pytest` | 2 failed / 436 passed — los del baseline |
| `test_openapi_snapshot_is_stable` | verde tras regeneración deliberada |
| Migración EF / Alembic | **ninguna**, verificado |

---

## 10. Fuera de esta pasada (no DoD)

- **La pantalla de revisión y la alerta de huérfanos** son C18b. Sin ellas, la cola de 15 miembros marcados, 4 grupos rechazados y 37 productos excluidos sólo se lee en el informe.
- **Un rechazo no se recuerda.** Al repetir `suggest`, una propuesta descartada reaparece: es el precio de no persistir propuestas, y la lista de descartes es de C18b.
- **Las lagunas del vocabulario de enriquecimiento** quedan como change propuesto en el §0 del plan, `fix-enrichment-vocabulary-gaps`. Al costearlo aparecieron dos correcciones al informe: el problema afecta a **once** productos y no a treinta y siete —la limpieza se llevó los demás— y la salida «no es una pieza» **ya existe** en el prompt, de modo que lo que falta es advertir al modelo, no ampliar el contrato. La escala métrica queda **descartada**: `Cadena Barbara 40/42/45 cm` son tres cadenas de longitud distinta, no variantes de una pieza.
- **El doble etiquetado del golden set de C24** trabajando en solitario: planteado en el §0, a decidir **antes** de abrir C24.
- **La divergencia de `Product.CollectionId`**, anotada en el §0.

---

## Veredicto

**Listo para archivar.** Los 47 escenarios de las cuatro specs tienen test nombrado o comprobación ejecutada; las dos suites no registran ninguna regresión atribuible al change comparadas por nombre; el alcance negativo está verificado con `git diff`; y el camino del dato se ejecutó de verdad, con 156 familias creadas y una sola reconciliación de `486 upserted, 32 deleted, 0 failed`.

El único hueco sin cerrar es **8.1**, cubierto por dos vías indirectas y anotado como tal.
