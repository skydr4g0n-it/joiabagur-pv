## Why

Python no puede leer `public` por SQL (C05) y C11 construye `doc_text` a partir de un DTO que **aún nadie serializa**. C13 tiene que tirar de un feed HTTP; sin este change el indexador o bien viola el §6.3 del diseño RAG o bien nace con `ai.product_document` vacío. Se hace ahora porque C07, C08 y C11 están archivados, C12 nunca se recorta, y desbloquea C13 (catálogo) y C22 (POS).

## What Changes

- **`GET /api/ai/index-feed/catalog`**: cursor keyset `(watermark, productId)`, página fija **50** (el cliente no envía `pageSize`). `watermark = greatest(Product.UpdatedAt, Profile.UpdatedAt, Family.UpdatedAt)` (familia solo si hay miembro actual). Ítems `kind = upsert` si el producto es indexable (`IsActive` y `ReviewStatus = Approved`); `kind = tombstone` si el watermark cambió y ya no lo es. Un producto **nunca** aprobado no aparece.
- **`GET /api/ai/index-feed/pos-availability`**: cursor keyset, página fija **200** (excepción de servicio, no copiable a UI). Feed **disperso**: filas `Inventory` activas como upsert; desasignación (`IsActive = false`) como tombstone `unassigned`. `qtyBucket` (`0` | `1-2` | `3+`); **prohibido** serializar `quantity`. `sales30d` / `sales90d` = `SUM(Sale.Quantity)` sin restar devoluciones.
- **Auth de servicio**: header `X-Index-Feed-Key`, secreto `IndexFeed:ApiKey` (opcional `ApiKeyPrevious` para rotación). Comparación constant-time. Fail-fast al arranque si la key falta o mide menos de 32 caracteres. Un JWT de usuario, una cookie `access_token` o un token C03 **no** autentican → **401**. Sin segundo `JwtBearer`.
- **Payload de catálogo** = campos de `ProductSourceText` (C11) + `productId` + `familyId` + `price` + `priceBand` (`price-band/v1`) + `isActive` + `watermark` + `kind`. **Sin** `data_origin`, **sin** `text_provenance`, **sin** `source`/`confidence`. Materiales y tags como arrays JSON, no como el `*Json` persistido.
- **Función pura `price-band/v1`**: `lt-30` / `30-80` / `80-150` / `150-300` / `gte-300`. Precio negativo → `ArgumentOutOfRangeException`. Cambiar cortes = v2 = re-sync C13 **sin** reembeber.
- **Hash agregado** SHA-256 UTF-8 de los identificadores indexables ordenados (catálogo: `productId`; POS: pares `(posId, productId)`), hex minúsculas 64 chars, **una vez por request** sobre el conjunto global, el mismo en cada página.
- **`ProductFamilyService.ReplaceMembersAsync`**: tras calcular altas y bajas, marcar `Product` `Modified` (sella `UpdatedAt`) de los que **entran y salen**. Cortocircuito de lista idéntica: **cero** escrituras, incluido Product. Rename de metadatos: no amplificar miembros; el feed une por `Family.UpdatedAt`.
- **Runbook** `Documentos/Proyecto Final AIEng/informes/c12-catalog-autobulk-runbook.md` (condiciones, comandos, tiempo y coste). **No** se ejecuta el AutoBulk de los 1.200.

**Fuera de alcance:** `POST /v1/index/sync`, upsert, embeddings, `ai.product_document`, `ai.pos_projection` (C13/C22); HTTP *push* .NET → Python; migración EF Core o Alembic; columna `DataOrigin` en `Product`; tabla outbox; regenerar `ai-service/openapi.json`; tocar `jbg_ai.api.main`; firmar JWT en Python; UI / frontend; revisión humana de perfiles (C28); propuesta de familias (C18); ejecutar AutoBulk.

Sin breaking changes de contrato REST ni OpenAPI. Superficie **nueva**. `POST /v1/index/sync` sigue siendo el stub de C13.

## Capabilities

### New Capabilities

- `index-feed`: feeds HTTP de indexación (`catalog` y `pos-availability`) con cursor keyset, tombstones (`deactivated` / `unapproved` / `unassigned`), hash agregado de conjunto, autenticación por API Key de servicio, y la función pura `price-band/v1` que C13 mapeará sin inventar bandas.

### Modified Capabilities

- `product-family`: `ReplaceMembers` sella `Product.UpdatedAt` de los productos que entran **y** salen de la familia, para que el cursor del feed los vea. La lista idéntica sigue sin escribir nada, incluido Product. Un rename de metadatos no reescribe miembros.

`catalog-source-text` **no lleva delta**: el feed es un *superset* del DTO; C13 mapea y hashea. `product-ai-profile` no cambia: el predicado `ReviewStatus = Approved` ya está escrito y el `SourceHash` del perfil no es el del índice. `ai-service-auth` no cambia: el JWT interno se queda en .NET → Python. `ai-vector-schema` no cambia: C12 no escribe `ai.*`. `backend` no cambia a nivel de requisito (paginación de UI intacta; el tope 200 es propio del feed). `ai-service-api-contracts` no se toca: `openapi.json` intacto.

## Impact

**Backend .NET** — controlador nuevo `AiIndexFeedController` (ruta literal `api/ai/index-feed`); `IndexFeedOptions` + filtro de API Key; DTOs de catálogo y POS; `IndexFeedService` (o equivalente) + `PriceBand.From(decimal)`; consultas keyset en Infrastructure; `ProductFamilyService.ReplaceMembersAsync` marca Product de altas y bajas; `backend/.env.example` y `appsettings*.json` con `IndexFeed:ApiKey` (placeholder local). Producción: SSM en **C17**, no aquí.

**Tests** — unitarios de banda y hash; integración de ambos feeds, tombstones, cursor, hash estable por página, 401 con cliente HTTP **fresco** (sin cookies de login), y test dedicado de `ReplaceMembers` + `UpdatedAt`. `Model_HasNoPendingMigrationDifferences` verde. No «arreglar» rojos preexistentes; comparar **nombres**.

**`ai-service/` / frontend / terraform / migraciones EF/Alembic / `openapi.json`** — **sin cambios**. Python no consume el feed en este change; C13 añadirá el header.

**Documentación** — `Documentos/epicas.md` (EP14) enlaza HU-AIENG-012; *runbook* AutoBulk nuevo; `Documentos/modelo-de-datos.md` menciona el feed como lector (sin entidad nueva).

**Dependientes desbloqueados:** C13 (indexador de catálogo) y C22 (proyección POS). El AutoBulk de los 1.200 (ops, fuera de este código) es la puerta de un C13 *útil*, no de este merge. El valor de producto no es visible: no hay pantalla.
