# HU-AIENG-012: Feeds HTTP de indexación con cursor, tombstones y autenticación de servicio

## Formato estándar

Como **desarrollador del proyecto**, quiero **feeds HTTP paginados con cursor, tombstones y un hash agregado, autenticados con API Key de servicio** **para** **que C13 (y C22) puedan poblar `ai.product_document` y `ai.pos_projection` sin leer `public` por SQL, y que un producto desactivado, un perfil que deja de estar aprobado o uno que sale de una familia salgan del índice en la siguiente sincronización**.

---

## Descripción

Change OpenSpec `add-dotnet-index-feed-endpoints` / **C12**, épica **EP14 — Búsqueda Semántica Híbrida**. Marcado 🔴 en la ruta crítica. Prerrequisitos de la ficha: **C07** y **C08** (archivados). C11 (archivado) congeló el DTO `ProductSourceText` que C13 mapeará **desde** este feed; esta historia no embebe ni hace *upsert*.

Es la única vía de lectura de Python sobre el catálogo de negocio (§6.3 del diseño RAG): *`public.*` es de .NET; `ai.*` es de Python; Python nunca escribe en `public` ni lo lee por SQL*. Hasta ahora el JWT interno viaja **.NET → Python**. Aquí se abre la dirección inversa: `jbg-ai` tira (`pull`) de `GET /api/ai/index-feed/*`. No hay HTTP *push* hacia `POST /v1/index/sync` (sigue siendo el stub de C13). El «empuje» de invalidación del §6.3 se materializa **ensuciando el cursor**: `Product.UpdatedAt` en altas y bajas de familia, unión por `ProductAiProfile.UpdatedAt` y `ProductFamily.UpdatedAt`.

El valor no es de operador: no hay pantalla. C13 hará el primer sync; C22 la proyección POS. El AutoBulk de los 1.200 perfiles **no** se ejecuta en esta historia: es la puerta de un C13 útil, documentada en un *runbook* que sí entrega C12.

C07 dejó dos deudas por escrito. Un producto que **sale** de una familia pierde la fila de miembro y el cursor no lo veía; un rename de familia no toca miembros y hay que unir por `IX_ProductFamilies_UpdatedAt`. Hay una tercera, igual de muda: un perfil que pasa de `Approved` a `Rejected`/`Pending` desaparece del filtro de aprobados y, sin tombstone, el documento vectorial sigue vivo.

**Alcance de esta historia (sí):**

- `GET /api/ai/index-feed/catalog` con cursor keyset `(watermark, productId)`, página **50**, ítems `upsert` | `tombstone`.
- `GET /api/ai/index-feed/pos-availability` con cursor keyset, página **200** (excepción de servicio, no copiable a UI), proyección **dispersa** (asignaciones + tombstones de desasignación), `qty_bucket` (`0` | `1-2` | `3+`) y `sales_30d` / `sales_90d` como suma de `Sale.Quantity` (sin netear devoluciones).
- Autenticación **solo de servicio**: header `X-Index-Feed-Key`, secreto `IndexFeed:ApiKey` (opcional `ApiKeyPrevious` para rotación). Un JWT de usuario **no** autentica el feed → **401**.
- Payload de catálogo = campos de `ProductSourceText` (C11) + `productId` + `familyId` + `price` + `priceBand` (`price-band/v1`) + `isActive` + `kind`. **Sin** `data_origin`, **sin** `text_provenance`, **sin** `source`/`confidence`.
- Función pura `price-band/v1` en .NET: `lt-30` / `30-80` / `80-150` / `150-300` / `gte-300`.
- Hash agregado SHA-256 del conjunto **indexable completo** (no de la página), el mismo en cada página de una respuesta coherente.
- `ProductFamilyService.ReplaceMembersAsync` marca `Product.UpdatedAt` de los productos que **entran y salen**. El cortocircuito de lista idéntica se conserva.
- Informe *runbook* `Documentos/Proyecto Final AIEng/informes/c12-catalog-autobulk-runbook.md` (condiciones, comandos, tiempo y coste). **No** se ejecuta el AutoBulk.
- Tests de integración y unitarios de la ficha más los que abren las deudas de C07 y el 401 de JWT humano (cliente HTTP **fresco**, sin cookies de login).

**Fuera de alcance (no):**

- Ejecutar `POST /api/ai/catalog/enrich-batch` AutoBulk sobre los 1.200 → **después de archivar C12, antes del apply de C13**. El *runbook* sí entra; la corrida no.
- `POST /v1/index/sync`, *upsert*, embeddings, `ai.product_document`, `ai.pos_projection`, `drift_count` → **C13** / **C22**.
- HTTP *push* .NET → Python.
- Migración EF Core o Alembic. Sin columna `DataOrigin` en `Product`. Sin tabla outbox.
- Regenerar `ai-service/openapi.json`. Tocar `jbg_ai.api.main` o firmar JWT en Python.
- UI, frontend, listados de administración.
- Revisión humana de perfiles (C28) y propuesta de familias (C18).

**Decisiones de diseño ya acordadas** (exploración 2026-08-25):

| # | Tema | Decisión |
|---|---|---|
| 1 | Migración | **No.** C12 no es 🗄️ |
| 2 | Invalidación | `Product.UpdatedAt` en altas/bajas de familia + unión por perfil y familia. Sin outbox |
| 3 | Push HTTP | **No.** C13 tira |
| 4 | `data_origin` | **No** en el JSON. C13 lo resuelve contra el JSONL real (436 SKU) |
| 5 | `text_provenance` | **No** en el JSON. C13 + JSONL |
| 6 | `price_band` | C12, función `price-band/v1`, cortes de la tabla inferior |
| 7 | Página POS | **200**, excepción escrita, no copiable a UI. Catálogo = **50** |
| 8 | Auth | **API Key** (`X-Index-Feed-Key`). JWT interno se queda en .NET → Python (S9 aplicado **por dirección**) |
| 9 | Ventas del feed POS | Solo `Sale.Quantity`. Sin netear `Return` |
| 10 | Actor | Desarrollador. AutoBulk de los 1.200 fuera de los criterios, documentado en el *runbook* |
| 11 | Alcance de sesión | **Los dos feeds** en este change; no se parte |
| 12 | Tombstone | Discriminador `kind` + `reason` (`deactivated` \| `unapproved` en catálogo; `unassigned` en POS). No solo `{deleted_at\|deactivated_at}` |
| 13 | Cursor | Keyset `(watermark, id)`, no un ISO-8601 suelto |
| 14 | Hash agregado | Del conjunto indexable global, orden-independiente. *Set drift*; el *content drift* es el `source_hash` de C11/C13 |
| 15 | POS | Disperso: filas de inventario activas + tombstones de `IsActive = false`. Ausencia = no asignado (C22 penaliza) |

**Cortes `price-band/v1`:**

| Banda | Precio (EUR) |
|---|---|
| `lt-30` | &lt; 30 |
| `30-80` | [30, 80) |
| `80-150` | [80, 150) |
| `150-300` | [150, 300) |
| `gte-300` | ≥ 300 |

Indexable en catálogo: `Product.IsActive` **y** `ProductAiProfile.ReviewStatus = Approved` (sin mirar `ReviewOrigin`). Un cambio cuyo producto **ya no** es indexable sale como tombstone. Un producto que nunca tuvo perfil aprobado **no** genera tombstone.

**Referencias:**

[proyecto-final-plan-changes-openspec.md](../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C12, §0 C07 obligaciones heredadas, §6 nunca se recorta),
[proyecto-final-diseno-rag-joiabagur.md](../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§6.2, **§6.3** contrato de sincronización, §7.2 esquema, D10, D11),
[La capa de datos como servicio](../Sesiones%20Master%20AIEng/S9_Fundamentos_RAG/La%20capa%20de%20datos%20como%20servicio%20-%20Aislar%20y%20Securizar%20el%20Retriever.md) (guía: API Key en este camino; JWT donde hay identidad),
[Reindexación y versionado de embeddings](../Sesiones%20Master%20AIEng/S11_RAG_avanzado/Reindexacion%20y%20Versionado%20Embeddings.md) (captura de cambios vs skip de embedding),
[epicas.md](../../epicas.md) (EP14),
[modelo-de-datos.md](../../modelo-de-datos.md) (`Product`, `ProductAiProfile`, `ProductFamily`, `Inventory`, `Sale`),
[HU-AIENG-007.md](HU-AIENG-007.md), [HU-AIENG-008.md](HU-AIENG-008.md), [HU-AIENG-011.md](HU-AIENG-011.md),
specs vivas `product-family`, `product-ai-profile`, `catalog-source-text`, `ai-vector-schema`,
change OpenSpec [`openspec/changes/add-dotnet-index-feed-endpoints/`](../../../openspec/changes/add-dotnet-index-feed-endpoints/) y su [ticket técnico](../../../openspec/changes/add-dotnet-index-feed-endpoints/ticket.md).

---

## Criterios de Aceptación

### Escenario 1: El cursor `since` solo devuelve filas cuyo watermark cambió
**Dado que** hay perfiles aprobados y un cursor `(since, sinceId)` de una página anterior
**Cuando** C13 (o el test) llama a `GET /api/ai/index-feed/catalog` con ese cursor y una API Key válida
**Entonces** la página trae como máximo 50 ítems
**Y** todos tienen watermark posterior al cursor (keyset: no se pierden ni se duplican filas con el mismo instante)
**Y** `hasMore` / `nextCursor` permiten continuar hasta agotar

### Escenario 2: Un producto desactivado emite tombstone
**Dado que** un producto indexable pasa a `IsActive = false`
**Cuando** el feed catálogo se consulta con `since` anterior a ese cambio
**Entonces** el ítem sale con `kind = tombstone` y `reason = deactivated`
**Y** no sale como `upsert`

### Escenario 3: Un perfil no aprobado no se indexa; uno que deja de estarlo es tombstone
**Dado que** un producto tiene perfil `Pending` o `Rejected`
**Cuando** se pide el feed catálogo
**Entonces** no aparece como `upsert`
**Y** si el perfil **era** `Approved` y pasa a no aprobado, el ítem es tombstone con `reason = unapproved`

### Escenario 4: El feed POS devuelve bucket, no cantidad exacta
**Dado que** un inventario activo tiene `Quantity` 0, 1, 2 o ≥ 3
**Cuando** se pide `GET /api/ai/index-feed/pos-availability`
**Entonces** `qtyBucket` es `0`, `1-2` o `3+` respectivamente
**Y** el JSON **no** incluye `quantity`
**Y** `isAssignedHint` refleja `Inventory.IsActive`
**Y** `sales30d` / `sales90d` suman `Sale.Quantity` en la ventana, sin restar devoluciones

### Escenario 5: Un JWT de usuario no abre el feed
**Dado que** un Administrador o un Operador tiene un access token válido (`Jwt:SecretKey`)
**Cuando** llama al feed **sin** `X-Index-Feed-Key` (cliente HTTP fresco, sin cookies de un login previo)
**Entonces** la respuesta es **401**
**Y** lo mismo ocurre sin header, o con una key distinta de `IndexFeed:ApiKey` / `ApiKeyPrevious`
**Y** un token C03 (`AiGateway:JwtSecret`) tampoco autentica el feed

### Escenario 6: El hash agregado detecta deriva de conjunto
**Dado que** el conjunto de productos indexables es I
**Cuando** se pide cualquier página del feed catálogo
**Entonces** `aggregateHash` es el SHA-256 hex de los `productId` de I ordenados
**Y** es **el mismo** en todas las páginas de esa lectura
**Y** cambia si un producto entra o sale del conjunto indexable

### Escenario 7: Salir de una familia reindexa al que se fue; renombrar reindexa a los que quedan
**Dado que** un producto deja de figurar en `PUT .../members` (y el cortocircuito no aplica)
**Cuando** se consulta el feed con `since` anterior al replace
**Entonces** ese `productId` aparece (upsert sin familia, o tombstone si ya no es indexable)
**Y** su `Product.UpdatedAt` es posterior al cursor
**Y** un rename de familia (`PUT` de metadatos) hace aparecer a los **miembros actuales** vía `Family.UpdatedAt`, sin reescribir filas de miembro

### Escenario 8: El tope POS es 200 y no se copia a listados de UI
**Dado que** hay más de 200 filas de disponibilidad
**Cuando** se pide el feed POS sin cursor
**Entonces** la página tiene como máximo 200 ítems
**Y** `PaginationConstants.MaxPageSize` (1000) y el tope 50 de listados de operador **no** se usan en esta ruta
**Y** el catálogo sigue limitado a 50

### Escenario 9: Fuera de alcance explícito
**Dado que** C12 entrega los feeds
**Cuando** se revisa el entregable
**Entonces** **no** se ha ejecutado AutoBulk sobre los 1.200
**Y** **sí** existe el *runbook* markdown con condiciones, comandos, tiempo y coste
**Y** **no** hay migración EF Core, ni `data_origin` en `Product`, ni cliente Python contra el feed
**Y** `POST /v1/index/sync` sigue siendo el stub de C13
**Y** `ai-service/openapi.json` no ha cambiado

---

## Notas adicionales

- **Actor:** equipo del Proyecto Final. Nada visible para el operador hasta C16.

- **Por qué API Key y no el JWT interno.** S9: un solo consumidor interno sin identidad de persona → API Key. El JWT HS256 de C02/C03 existe porque .NET → Python **sí** lleva `user_id` / `role` / `pos_id` y «el token manda». Reutilizar ese secreto en el feed haría válidos los tokens C03 que Python ya recibe en cada búsqueda. Tercer secreto, blast radius aislado. Rotación: `ApiKeyPrevious`.

- **401, no 403.** La ficha nombraba 403. Un JWT humano no es una credencial de este esquema: el middleware no identifica al usuario y responde 401. El espíritu (un admin logado no lee el índice) se cubre con cliente fresco — la trampa del `HttpClient` compartido de `CLAUDE.md` / `testing-backend.md`.

- **`PaginationConstants.MaxPageSize` es 1000** en el código actual. No usarlo aquí. Constantes propias del feed.

- **`UpdatedAt` de `Product`.** `SaveChangesAsync` lo sella en entidades `Modified`. Hay que cargar y marcar los productos que salen; un `DELETE` de miembro **no** toca `Product`.

- **C13 y `data_origin`.** `ai.product_document.data_origin` es NOT NULL. C12 no lo emite; C13 cruza SKU con `data/catalog/real/generated/catalog-real-enriched.jsonl`.

- **Par de zona.** C12 es .NET. No solapar con otro 🗄️ (este change no abre migración). C13 no empieza hasta archivar.

---

## Tareas

1. Completar artefactos OpenSpec (`proposal`, **`design.md` obligatorio** — hay alternativas reales —, specs `index-feed` + delta `product-family`, `tasks`).
2. Options `IndexFeed` (key + previous), fail-fast, filtro de API Key con comparación de tiempo constante.
3. `price-band/v1` como clase pura + tests sin contenedor.
4. Servicio y consultas del feed catálogo (joins, keyset, tombstones, hash agregado).
5. Servicio y consultas del feed POS (disperso, buckets, ventas 30/90 d, página 200).
6. Controlador `api/ai/index-feed` sin `[Authorize]` de roles de negocio.
7. `ReplaceMembersAsync`: `UpdatedAt` de altas y bajas; test dedicado.
8. Tests de integración (incl. JWT humano → 401 con cliente fresco) y de esquema: **ninguna** migración nueva (`Model_HasNoPendingMigrationDifferences` verde).
9. *Runbook* AutoBulk en `Documentos/Proyecto Final AIEng/informes/c12-catalog-autobulk-runbook.md`. Enlazar HU en `epicas.md` (EP14).
10. `openspec validate --all --strict` antes de archivar. **No** regenerar OpenAPI de Python.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** 4 — habilitador; sin esto C13 no puede indexar sin violar §6.3
- **Urgencia (mercado / feedback):** **5** — 🔴; nunca se recorta; desbloquea C13 y C22
- **Complejidad / esfuerzo:** 4 — dos feeds, auth nueva, deudas de C07, sin migración
- **Riesgos y dependencias:** C07 y C08 archivados; 0 perfiles en Docker hasta el AutoBulk (fuera); no reutilizar el secreto JWT de C03; no usar el `HttpClient` de login para el 401; el tope 200 del POS no debe colarse en UI
