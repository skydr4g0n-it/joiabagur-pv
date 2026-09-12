## 1. Línea base antes de tocar nada

- [ ] 1.1 Ejecutar `dotnet test` sobre el árbol limpio y guardar la lista de **nombres** de test fallidos — la suite viene roja de base y el recuento no es comparable entre ejecuciones
- [ ] 1.2 Ejecutar `npm run test` en `frontend/` sobre el árbol limpio y guardar la lista de nombres fallidos (medidos el 2026-08-29: 118 de 482, en 17 de 40 ficheros); leer la línea de resumen, no el código de salida
- [ ] 1.3 Ejecutar `npm run build` en `frontend/` y confirmar que está en verde: es el gate real, no `tsc --noEmit`
- [ ] 1.4 Confirmar contra la base que no hace falta migración: `ProposedProfileJson`, `ReviewDurationMs`, `ReviewedByUserId` y `ReviewedAt` existen y son nulables donde deben

## 2. Estratificación y muestreo (Application)

- [ ] 2.1 Implementar la función de estrato a partir de `FieldConfidenceJson`, con el mínimo de los campos sensibles y `stone_type` ausente tratado como no penalizador; **una sola implementación**, consumida por la cola y por las métricas
- [ ] 2.2 Test `Stratum_StoneTypeAbsent_DoesNotLowerStratum`
- [ ] 2.3 Test `Stratum_ComputedIdenticallyForQueueAndMetrics` sobre el mismo conjunto de perfiles
- [ ] 2.4 Implementar el muestreo determinista por `hash(ProductId + semilla)` dentro de cada estrato, con cuotas por estrato y la semilla leída de configuración
- [ ] 2.5 Test `Sampling_SameSeed_ReturnsSameBatchInSameOrder`
- [ ] 2.6 Test `Sampling_StratumSmallerThanQuota_ReturnsAllAndReportsExhausted`
- [ ] 2.7 Test `Sampling_QueueRequest_WritesNoRow` — el lote no se persiste

## 3. Servicio de revisión (Application)

- [ ] 3.1 Crear `IProfileReviewService` y su implementación, con las cuatro operaciones: cola, revisión individual, aprobación masiva y métricas
- [ ] 3.2 Implementar la cola sobre `ReviewOrigin = AutoBulk` **y** `ReviewStatus = Approved`, con el estrato y el texto de origen (nombre y descripción) en cada ítem
- [ ] 3.3 Test `Queue_Request_DoesNotChangeAnyReviewStatus`
- [ ] 3.4 Test `Queue_Request_LeavesIndexableCountUnchanged`
- [ ] 3.5 Implementar la clasificación de la corrección por dirección —confirmación, adición, retirada, sustitución— diferenciando valores en vigor contra `ProposedProfileJson`, con diferencia de conjuntos para los campos de lista
- [ ] 3.6 Test `Review_MaterialAdded_RecordsAdditionDirection`
- [ ] 3.7 Test `Review_UnsupportedStoneCleared_RecordsRemovalDirection`
- [ ] 3.8 Test `Review_FieldUntouched_RecordsConfirmation`
- [ ] 3.9 Test `Review_AnyCorrection_LeavesProposedProfileJsonUnchanged` — el registro crudo es inmutable
- [ ] 3.10 Implementar la revisión individual: origen a `Human`, revisor e instante estampados por el **servidor**, duración persistida en la misma operación
- [ ] 3.11 Test `Review_Individual_PersistsDurationInSameOperation`
- [ ] 3.12 Test `Review_IndividualWithoutDuration_IsRejected`
- [ ] 3.13 Test `Review_Reviewer_TakenFromCurrentUserNotFromBody`
- [ ] 3.14 Implementar la aprobación masiva acotada a un campo dentro de un estrato, marcada como masiva y sin duración
- [ ] 3.15 Test `BulkApprove_SelectionSpansStrata_IsRejectedAndModifiesNothing`
- [ ] 3.16 Test `BulkApprove_MoreThanOneField_IsRejectedAndModifiesNothing`
- [ ] 3.17 Test `BulkApprove_Success_LeavesDurationNullAndMarksBulk`
- [ ] 3.18 Implementar la lista de perfiles rechazados y la operación de devolver uno a `Approved`, sin consumir cuota de ningún estrato
- [ ] 3.19 Test `RejectedList_DoesNotConsumeStratumQuota`
- [ ] 3.20 Test `RejectedProfile_ReturnedToApproved_RecordsReviewerAndInstant`

## 4. Métricas (Application)

- [ ] 4.1 Implementar el cálculo de la tasa de corrección por campo, por estrato y por dirección, con total **ponderado por el tamaño real del estrato en el corpus**
- [ ] 4.2 Test `Metrics_CorrectionRate_ComputedPerField` *(nombrado por la ficha del plan)*
- [ ] 4.3 Test `Metrics_CorrectionRate_SplitByStratumAndDirection`
- [ ] 4.4 Test `Metrics_Total_WeightedByCorpusStratumSize_NotBySampleSize`
- [ ] 4.5 Implementar la exclusión de los perfiles `AutoBulk` del numerador y del denominador, reportando el recuento por origen
- [ ] 4.6 Test `Metrics_ExcludesAutoBulkProfiles` *(nombrado por la ficha del plan)*
- [ ] 4.7 Test `Metrics_ReportsProfileCountPerReviewOrigin`
- [ ] 4.8 Implementar las dos poblaciones de tiempo por separado, con media **nula y nunca cero** cuando no hay tiempos — replicando el patrón de `FamilyReviewMetricsDto`
- [ ] 4.9 Test `Metrics_NoTimedReviews_AverageIsNullNotZero`
- [ ] 4.10 Test `Metrics_TimedAndBulkPopulations_CountedApart`

## 5. API (.NET)

- [ ] 5.1 Añadir a `AiCatalogController` las rutas `GET profile-review-queue`, `POST profile-reviews`, `POST profile-reviews/bulk` y `GET profile-review-metrics`, bajo el prefijo y la política de administrador existentes
- [ ] 5.2 Añadir la ruta de perfiles rechazados y la de devolución a aprobado
- [ ] 5.3 DTOs y reglas de FluentValidation: duración obligatoria en la individual, y rechazo de la masiva que cruce estrato o campo
- [ ] 5.4 Paginación obligatoria, máximo 50 ítems por página
- [ ] 5.5 Test de integración `ProfileReview_OperatorRole_Returns403` sobre las seis rutas
- [ ] 5.6 Test de integración `ProfileReview_Unauthenticated_Returns401` — pedir un cliente **nuevo** a la factoría; el compartido conserva las cookies de cada login
- [ ] 5.7 Logging estructurado con Serilog en las escrituras: quién, qué campo y qué dirección, sin volcar el perfil entero

## 6. Carcasa compartida (frontend)

- [ ] 6.1 Extraer `useItemStopwatch()` desde `family-review.tsx`, con el patrón ya corregido: el tiempo viaja en la petición de guardado y **no se acumula en el estado del componente**
- [ ] 6.2 Extraer `<ThreeStateList>` — cargando / cargado / no se pudo calcular
- [ ] 6.3 Crear `useReviewKeyboard()`, inerte cuando el foco está dentro de un campo de edición de texto
- [ ] 6.4 Reconectar `family-review.tsx` a las tres piezas y **comparar los nombres de test fallidos contra la línea base de 1.2**, nunca el recuento

## 7. Pantalla de revisión de perfiles (frontend)

- [ ] 7.1 Crear `src/types/profile-review.types.ts`, espejo de los DTOs
- [ ] 7.2 Crear `src/services/profile-review.service.ts` con resultado discriminado para distinguir «vino vacío» de «no se pudo calcular», replicando `family-review.service.ts`
- [ ] 7.3 Crear `src/pages/admin/profile-review.tsx`: tabla editable, confianza y procedencia por campo, texto de origen completo al lado, y destacado de los sensibles inferidos
- [ ] 7.4 Presentar la pregunta según el estrato: *«¿falta algo?»* en el de máxima confianza, *«¿es correcto?»* en los demás
- [ ] 7.5 Declarar explícitamente la ausencia de descripción en lugar de dejar un hueco
- [ ] 7.6 Barra de aprobación masiva, acotada a un campo dentro de un estrato en la propia interfaz
- [ ] 7.7 Tarjeta de métricas con las dos poblaciones de tiempo separadas
- [ ] 7.8 Vista de los 32 rechazados con la pregunta invertida
- [ ] 7.9 Registrar la ruta en `routes.tsx` (`PROFILE_REVIEW: '/admin/profile-review'`) y en `app-routing-setup.tsx` como `lazy` bajo `AdminRoute`
- [ ] 7.10 Enganchar `useReviewKeyboard()` en la pantalla nueva

## 8. Tests de frontend

- [ ] 8.1 `should highlight inferred sensitive fields pending review` *(nombrado por la ficha del plan)*
- [ ] 8.2 `should record correction when material list is edited` *(nombrado por la ficha del plan)*
- [ ] 8.3 `should send the measured duration when an individual review is saved`
- [ ] 8.4 `should report that the queue could not be computed when the read fails`
- [ ] 8.5 `should not trigger a shortcut when typing inside a text field`
- [ ] 8.6 `should show the product description beside the proposed values`
- [ ] 8.7 Declarar los handlers de MSW explícitamente: la suite arranca con `onUnhandledRequest: 'warn'` y un test sin handler pasa sin haber afirmado nada

## 9. Creación de familia desde la revisión (frontend)

- [ ] 9.1 Añadir a `family-review.tsx` la creación de familia con nombre y miembros con su etiqueta de variante, consumiendo el `POST /api/product-families` que ya existe
- [ ] 9.2 Test `should create a family with its members from the review screen`
- [ ] 9.3 Verificar a mano el caso real heredado: los siete productos de `piece_type` `cadena` y las dos alianzas

## 10. La sesión de revisión — el entregable

- [ ] 10.1 Fijar y declarar la semilla del muestreo, y obtener el lote de 180 (60 por estrato)
- [ ] 10.2 Revisar los ~40 primeros ítems **a ratón**, alternando estratos, para tener el término de comparación del teclado
- [ ] 10.3 Revisar los ~140 restantes con teclado
- [ ] 10.4 Pasada corta sobre los 32 rechazados con la pregunta invertida, resolviendo el caso de `Presión Oro`
- [ ] 10.5 Comprobar que los productos corregidos vuelven a emitirse por el feed incremental y que sus documentos reflejan la corrección
- [ ] 10.6 Comprobar que un perfil rechazado por una persona desaparece del índice

## 11. Cierre

- [ ] 11.1 `openspec validate --all --strict` con **0 failed**
- [ ] 11.2 Confirmar que no hay diff en `ai-service/` ni en `openapi.json`, y que no se ha creado ninguna migración
- [ ] 11.3 Comparar ambas suites contra la línea base por **nombres** de test, y `npm run build` en verde
- [ ] 11.4 Escribir `Documentos/Proyecto Final AIEng/informes/c28-implementation-measurements.md` con los dos números, su desglose por estrato y dirección, la semilla, el resultado del A/B de teclado con su confundido declarado, y los hallazgos de vocabulario que la revisión destape
- [ ] 11.5 Actualizar la limitación 2 del §15 del diseño con el porcentaje realmente revisado
- [ ] 11.6 Actualizar `Documentos/epicas.md` y el plan de changes al archivar
- [ ] 11.7 Anotar como hallazgo, sin corregirlos aquí, los términos de vocabulario que la revisión demuestre que faltan
