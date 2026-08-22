# HU-AIENG-006b: Ampliación sintética del catálogo — LLM, colecciones nuevas e ingesta local

## Formato estándar

Como **desarrollador del proyecto**, quiero **generar un corpus de productos sintéticos (~1.200 totales junto al real), versionarlo e insertarlo en la base local** **para** **dar volumen a C11 y C24 con piezas imaginadas de joyería vendible, diferenciadas del ancla real, sin chivar familias a C18 y sin exponer un endpoint HTTP**.

---

## Descripción

Segundo tramo de C06 del Proyecto Final de IA (change OpenSpec `add-synthetic-catalog-augmentation` / **C06b**, épica **EP12 — Corpus y Enriquecimiento del Catálogo**). Marcado 🟢: puede correr en paralelo a C09. Prerrequisito: **C06a** (archivado). Desbloquea **C11 y C24 por volumen ya ingerido** en `.NET`; C10 **no** lo necesita.

C06a dejó 436 productos reales con texto utilizable. El objetivo de corpus híbrido sigue siendo **~1.200 productos totales** (holgura, no cifra exacta): faltan ~750 sintéticos. La ficha v3 pedía calibrar precio, SKU y ~350 familias S/M/L al real, e inyectar un 15 % de huérfanos. La exploración del 2026-08-22 retira eso: el real ya tiene 354 grupos internos; preasignar `ProductFamily` chivaría C18; el precio lo razona un LLM; las colecciones sintéticas son **altas nuevas** con nombre de **diseño**, no de canal.

El valor no es de usuario de tienda —no hay pantalla ni ruta `/v1`— sino de **calibración**: C11/C13 indexan lo que C12 lee de `public."Products"`. Un JSONL sin `INSERT` no llega al índice. La generación **no vive en la API .NET de Joiabagur** ni en FastAPI: es un CLI en `jbg_ai.data`. C10, cuando llegue, se sienta al lado (mundo numérico, también CLI).

**Alcance de esta historia (sí):**

- CLI en [`ai-service/src/jbg_ai/data/`](../../../ai-service/src/jbg_ai/) que **no** se importa desde [`jbg_ai.api.main`](../../../ai-service/src/jbg_ai/api/main.py).
- Orquestador + cliente **OpenAI** + prompt versionado: nombres, descripciones y **precios razonados** (pieza, tamaño, materiales, público del brief). Sin bandas fijas.
- Hotel / aeropuerto / turista / atelier clásico son **brief de público o POS pensado** para el prompt (y, si se anota, para el informe). **No** son nombres de colección ni un campo en `Product`.
- Nombres de colección inspirados en el **diseño de las piezas** (p. ej. «El Jaleo», «Fuego», «Cielo estrellado», «La Pomada»). 8–12 colecciones **nuevas**. Un par pueden seguir temática menorquina en el diseño; el resto divergen. **No** meter sintéticos en Biniacolla, Melia, Composturas, etc.
- El código reserva SKUs con el **mismo esquema que el real**: `SKU` + 2, 3 o 4 dígitos según la magnitud (`SKU01`…`SKU99`, `SKU100`…`SKU999`, `SKU1000`…), continuando **después de 436** (`SKU437`, `SKU438`, …). Sin prefijo `SYN-` ni otra marca que delate origen al extractor de C09. Unique vs JSONL C06a y vs `"Products"."SKU"` (máx. 50).
- Sellado `data_origin: synthetic` y `text_provenance: synthetic` **por código**, no por el modelo.
- `text_quality_tier` ~70 `rich` / ~20 `sparse` / ~10 corto o vacío. Misma regla que C06a: el stem del **`Name`** (hermanos de talla) comparte tier; no se mezcla riqueza dentro de esa «familia» de nombre. `text_provenance` es siempre `synthetic`.
- Validación `Description` ≤ 1000 (`Product.Description` es `varchar(1000)`). Precio > 0; se rechaza `>= 50000`.
- ~35 % de las descripciones mencionan **dos o más materiales en la prosa**. El JSONL **no** lleva `materials[]` (eso es extracción C09).
- Tallas en el **nombre** permitidas (como el real: «Colgante erizo S»). Eso es catálogo, no semilla de C18.
- El JSONL **no** lleva `product_id`: el `Id` lo genera PostgreSQL en el `INSERT`; C12/C13 lo leen de .NET.
- Salida versionada:
  - `data/catalog/synthetic/generated/catalog-synthetic.jsonl` — **commiteado**
  - sidecar `.meta.json` (`generator_version`, `seed`, `model`, `prompt_version`, `generated_at`)
  - informe `Documentos/Proyecto Final AIEng/informes/c06b-synthetic-catalog-report.md`
- **Ingesta local** (Docker, host **5433**, BD `joiabagur_pv`): transacción con `INSERT` de colecciones nuevas y productos (`IsActive = true`). **No** `UPDATE` de filas reales. **No** toca `ProductFamily` / `ProductFamilyMember`. Credenciales solo por `JPV_PG*` (mismo patrón que C06a).
- Settings `LLM_*` / clave OpenAI **opcionales** al arrancar `/health`; el CLI las exige. `openapi.json` no cambia.
- Tests con LLM **falso**; cero llamadas a proveedor en pytest (regla transversal del plan §1).

**Fuera de alcance (no):**

- **C09** — extractor, vocabularios, `POST /v1/enrich/products`.
- **C10** — POS, inventario, ventas, co-ocurrencia. El brief hotel/aeropuerto **no** crea puntos de venta.
- **C18** — propuesta y aprobación de `ProductFamily`. Este change **no** escribe miembros ni emite `family_seed` / `variant_group_key` / `variant_label`.
- **C13** — columna `text_provenance` en `ai.product_document`.
- Reutilizar [`scripts/catalog/assist.py`](../../../scripts/catalog/src/catalog_pipeline/assist.py) (plantillas de C06a).
- Ruta HTTP en FastAPI o en la API .NET. Regenerar `ai-service/openapi.json`.
- RDS / producción. Migración EF Core. Columna de procedencia o de canal en `Product`.
- Colecciones llamadas «Hotel», «Aeropuerto», «Turista», «Atelier» o equivalentes de canal/POS.
- Papelería, portes, cursos u otros no-joyería que el export real ya arrastra.
- Cliente LLM **obligatorio** para que `GET /health` arranque (rompería C17).
- Reescribir `product_id` en el JSONL tras el INSERT.

**Decisiones de diseño ya acordadas** (exploración 2026-08-22 y cierre de preguntas):

| Tema | Decisión |
|---|---|
| Volumen | ~**1.200 productos totales** (436 reales + sintéticos). Holgura; no es un umbral de aceptación exacto |
| Familias (entidad) | **Fuera.** `Product` no tiene columna de familia. D4 es C18. Todos los sintéticos nacen **huérfanos** (GET familia → 204) |
| «Familia» de calidad | Solo el **stem del `Name`** (tallas). Misma regla C06a: un grupo no mezcla `text_quality_tier` |
| Colección vs familia vs canal | Colección = línea editorial de **diseño** (`CollectionId`). Familia = variantes (C18). Canal/POS = brief de prompt, no nombre ni columna |
| Nombre de colección | Inspirado en las piezas («El Jaleo», «Fuego», «Cielo estrellado», «La Pomada»). 8–12 altas nuevas |
| Zona | `jbg_ai.data` como **CLI**, no como proceso FastAPI ni como API Joiabagur |
| Texto y precio | **OpenAI**. El código reserva SKU, sella procedencia y valida. Temperatura > 0: el JSONL commiteado es la fuente; regenerar exige flag |
| SKU | Esquema del real: `SKU` + 2/3/4 dígitos según magnitud, a partir de **437**. Sin prefijo que delate sintético |
| Calibración al real | **No** se heredan precios, tamaño de familia ni longitud de descripción. Del real se toman SKUs y nombres de colección **a no reutilizar**; el esquema de SKU **sí** se copia a propósito |
| Multi-material | ~35 % en la **prosa**; sin `materials[]` en el JSONL |
| Ingesta | **INSERT** local de colecciones nuevas + productos. Sin repetir SKU real. Sin RDS |
| `product_id` en JSONL | **No.** Lo genera la BD; C12 lo emite al indexar |
| Techo de precio | Rechazar `>= 50000` antes de ingerir |
| `text_provenance` | JSONL + sidecar + informe en C06b · `public."Products"` nunca · `ai.product_document` en **C13** |
| Frontera §6.3 | El **rol de runtime** de `jbg-ai` no gana `INSERT` sobre `public`. El CLI de desarrollo usa `JPV_PG*` igual que C06a |

**Referencias:**

[proyecto-final-plan-changes-openspec.md](../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C06b, §0 2026-08-22),
[proyecto-final-diseno-rag-joiabagur.md](../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§7.5, §8.1.1 regla 2, §8.2, D1/D4, §8.4, §15.1),
[epicas.md](../../epicas.md) (EP12; EP13 para familias),
[modelo-de-datos.md](../../modelo-de-datos.md) (`Product`, `Collection`, `ProductFamily` — esta HU no escribe la tercera),
[HU-AIENG-006a.md](HU-AIENG-006a.md), spec viva [`real-catalog-corpus`](../../../openspec/specs/real-catalog-corpus/spec.md),
change OpenSpec [`openspec/changes/add-synthetic-catalog-augmentation/`](../../../openspec/changes/add-synthetic-catalog-augmentation/) y su [ticket técnico](../../../openspec/changes/add-synthetic-catalog-augmentation/ticket.md).

---

## Criterios de Aceptación

### Escenario 1: El corpus híbrido alcanza el volumen sin clonar el real
**Dado que** el JSONL de C06a tiene 436 SKUs con `data_origin: real`
**Cuando** termina la generación sintética
**Entonces** el JSONL sintético tiene el recuento necesario para ~1.200 productos **totales** (holgura documentada en el sidecar)
**Y** cada línea lleva `data_origin: synthetic` y `text_provenance: synthetic`
**Y** ningún SKU sintético aparece en el JSONL real ni está duplicado en el sintético

### Escenario 2: Los SKU siguen el esquema del real y no delatan origen
**Dado que** C09 no debe recibir una pista léxica de «sintético» en el SKU
**Cuando** se listan los SKUs reservados
**Entonces** tienen la forma `SKU` + 2, 3 o 4 dígitos según la magnitud (como `SKU01`, `SKU100`, `SKU1000`)
**Y** la secuencia numérica empieza **después de 436** (`SKU437`, …)
**Y** no usan prefijos del tipo `SYN-`, `JB-S-` u otros que no existan en el ancla real
**Y** el reservador es determinista a igual semilla

### Escenario 3: Colecciones con nombre de diseño, no de canal
**Dado que** `Collections.Name` es único y el real ya tiene 28 nombres
**Cuando** se generan e ingieren 8–12 colecciones sintéticas
**Entonces** ninguna coincide con una colección del JSONL C06a ni con una fila ya presente en `"Collections"`
**Y** los nombres evocan el diseño de las piezas, no el POS ni el canal (no «Hotel», «Aeropuerto», «Turista», «Atelier»…)
**Y** ningún producto sintético apunta a una colección real existente
**Y** el informe puede anotar el **público o POS pensado** de cada colección como metadato de generación, separado del nombre

### Escenario 4: El JSONL no chiva C18 ni C09
**Dado que** las familias las propone C18 y los materiales los extrae C09
**Cuando** se parsea cualquier línea del JSONL sintético
**Entonces** no existen las claves `variant_group_key`, `variant_label`, `family_seed`, `materials` ni `product_id`
**Y** la ingesta no inserta filas en `"ProductFamilies"` ni `"ProductFamilyMembers"`
**Y** un `GET` de familia sobre un SKU sintético ingerido responde 204 (huérfano), no 404

### Escenario 5: El reparto de calidad no mezcla hermanos de nombre
**Dado que** C06a sorteaba tier por familia interna de variantes
**Cuando** dos productos sintéticos comparten stem de `Name` (p. ej. el mismo motivo en S y M)
**Entonces** llevan el mismo `text_quality_tier`
**Y** los ratios globales por producto caen en ~70 / ~20 / ~10 ± holgura razonable
**Y** los tres tiers llevan `text_provenance: synthetic`

### Escenario 6: El texto es de joyero imaginativo, no plantilla C06a
**Dado que** el producto sintético no existe y puede inventar piedras y mix de materiales
**Cuando** se revisan las muestras del informe
**Entonces** nombres y descripciones no siguen el molde de `assist.py` («El anillo con X, en talla Y, en plata de ley…»)
**Y** al menos un tercio aproximado de las descripciones nombra dos materiales
**Y** ninguna descripción supera 1000 caracteres
**Y** el precio es > 0, cabe en `decimal(18,2)` y es &lt; 50.000 €

### Escenario 7: La ingesta inserta sin tocar el ancla real
**Dado que** Docker local tiene los 436 productos de C06a
**Cuando** corre la ingesta del JSONL sintético
**Entonces** se insertan las colecciones nuevas y los productos nuevos (`IsActive = true`)
**Y** el recuento y los SKU/precio/nombre de las filas reales no cambian
**Y** un SKU sintético que ya existiera aborta la transacción (rollback, sin INSERT parcial)
**Y** PostgreSQL asigna el `Id` de cada producto; el JSONL no se reescribe con ese UUID
**Y** no hay escrituras contra RDS

### Escenario 8: Trazabilidad y git
**Dado que** el corpus debe auditarse y regenerarse con un comando
**Cuando** se lee el sidecar y el estado del repositorio
**Entonces** el sidecar incluye `generator_version`, `seed`, `model` (OpenAI), `prompt_version` y `generated_at`
**Y** el JSONL sintético está versionado en git
**Y** regenerar descripciones exige un flag explícito (sin él, no se reescribe el texto commiteado)

### Escenario 9: El servicio HTTP no se entera
**Dado que** C17 arranca `jbg-ai` sin claves de proveedor de catálogo
**Cuando** se inspecciona este change
**Entonces** `jbg_ai.api.main` no importa `jbg_ai.data`
**Y** `GET /health` arranca sin `LLM_*` / `OPENAI_*`
**Y** `ai-service/openapi.json` no ha cambiado
**Y** pytest del generador no abre sockets a proveedores

### Escenario 10: Fuera de alcance explícito
**Dado que** esta historia está implementada según el alcance acordado
**Cuando** se revisa el entregable
**Entonces** **no** hay endpoint de generación ni cambios en backend/frontend de API
**Y** **no** se ha implementado C09, C10 ni C18
**Y** **no** hay migración Alembic de `text_provenance` ni columna nueva en `Product`

---

## Notas adicionales

- **Actor:** equipo del Proyecto Final. No hay rol Admin/Operador en la generación; la ingesta es operación de desarrollo.

- **Por qué no está en la ruta crítica.** C09 ya puede construirse con C06a. C06b es volumen para el índice y el golden set. El plan **admite recortarlo**: sin él, las métricas se reportan sobre los 436 y el README declara que no hubo ampliación.

- **Por qué hay ingesta y no solo JSONL.** C12 alimenta C13 desde `.NET`. Sin filas en `"Products"`, C11 no ve el sintético y el grafo `C06b → C11` mentiría.

- **Familia.** No es un campo de `Product`. C07 ya tiene las tablas; C18 las rellena. C06b deja huérfanos a propósito. El sorteo 70/20/10 usa solo el `Name`.

- **`product_id`.** En C06a era un lookup opcional porque el xlsx no traía UUID. Aquí el `INSERT` crea el `Id`. Nadie aguas abajo (C09, C12, C13) necesita que el JSONL lo copie: C09 trabaja el texto; el feed de C12 ya lleva el Guid de .NET.

- **`.gitignore`.** Hoy solo está exceptuado `data/catalog/real/generated/`. Hay que abrir la excepción simétrica para `data/catalog/synthetic/generated/` sin des-ignorar basura de datos.

- **Honestidad del README (§15).** El sintético lo escribe un LLM; no es un clon estadístico del export. Las métricas de C24 se desglosan por `data_origin`; el umbral de aceptación sigue siendo la porción real.

---

## Tareas

1. Completar artefactos OpenSpec del change `add-synthetic-catalog-augmentation` (proposal, design, specs, tasks).
2. CLI en `jbg_ai.data`: reservador de SKU (`SKU437`…), prompt OpenAI versionado (briefs de público ≠ nombre de colección), validación, escritura JSONL + sidecar.
3. Abrir `.gitignore` para `data/catalog/synthetic/generated/`; commitear corpus e informe.
4. Ingesta `INSERT` (colecciones + productos) contra Docker con transacción e invariante de no tocar SKUs reales.
5. Tests con LLM falso: unicidad, esquema de SKU, omisión de familia y `product_id`, tiers por stem de `Name`, tope 1000, boot sin API key, cero red.
6. `openspec validate --all --strict` antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** 4 — no es pantalla; desbloquea volumen de C11/C24 y categorías del golden set que el real no cubre (multi-material, piedra)
- **Urgencia:** 3 — 🟢; C09 no espera; sí conviene antes de indexar en serio
- **Complejidad:** 4 — LLM + invariantes + INSERT en `public` desde un CLI de Python; sin contrato HTTP
- **Riesgos y dependencias:** C06a archivado; Postgres Docker con los 436 reales; clave OpenAI solo en la pasada de generate (no en CI); frontera §6.3 (rol `jbg-ai` vs CLI de desarrollo); C18 posterior para familias
