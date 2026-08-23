# HU-AIENG-009: Pipeline de enriquecimiento del catálogo — extracción estructurada con vocabularios cerrados

## Formato estándar

Como **Administrador del catálogo**, quiero **que el lote de enriquecimiento extraiga de cada producto materiales, tipo de pieza, piedra, talla y etiquetas comerciales a partir del nombre y la descripción, con origen y confianza por campo** **para** **dejar de depender del stub determinista y poder afirmar sobre las piezas solo lo que el texto permite afirmar, de modo que C08 enrute de verdad y C12/C11 indexen perfiles reales**.

---

## Descripción

Change OpenSpec `add-catalog-enrichment-pipeline` / **C09**, épica **EP12 — Corpus y Enriquecimiento del Catálogo**. Marcado 🔴 en la ruta crítica: C11 lo tiene como prerrequisito. Prerrequisito propio: **C06a** (archivado). C06b (archivado) no es prerrequisito: el extractor se prueba con fixtures; el sintético aporta volumen cuando más adelante se ejecute `enrich-batch`.

C08 ya creó `ProductAiProfile`, renegoció el contrato (`source`, `piece_type`, `stone_type`, `size_label`, tags desglosadas, `prompt_version`) y expuso `POST /api/ai/catalog/enrich-batch`. Ese lote llama a `POST /v1/enrich/products`, que **sigue en stub**: `require_stub_mode` y `enrich_products_stub`. Con `STUB_MODE=false` responde 501 nombrando C09. El enrutado híbrido de C08 está listo; no tiene de qué fiarse. Esta historia **sustituye el stub por el extractor real** y no toca .NET.

El corpus híbrido ya existe: 436 reales (C06a) + 764 sintéticos (C06b) = 1.200 en `public."Products"`. El JSONL lleva `text_provenance` y `text_quality_tier`; **el HTTP no**. C09 extrae de `name` + `description` (más `sku` e id, que no informan talla). Precio y colección no viajan: C08 los excluyó a propósito.

**Alcance de esta historia (sí):**

- Paquete `ai-service/src/jbg_ai/enrichment/` importado por el router `/v1/enrich/products`. **No** se importa `jbg_ai.data` (CLI de C06b).
- Prompt versionado `ai-service/prompts/enrichment/v1.md`; la respuesta lleva `prompt_version` real (no `"stub"`).
- Structured output a temperatura 0 vía **LiteLLM** (`litellm.completion(..., response_format=ExtractionSchema)` + Pydantic). Puerto propio `EnrichLlm`; **no** se reutiliza `OpenAICatalogLlm` de C06b. Una llamada LLM por producto; semáforo `JPV_RAG_LLM_CONCURRENCY` (default **8**) dentro del lote de 50.
- Normalización determinista previa: talla por regex sobre **`Name` primero y `Description` después**; nunca sobre el SKU. Acierto de regex → `source: rule`, confianza `1.0`.
- Vocabularios cerrados versionados en el repo (YAML/JSON, no `ENUM` de PostgreSQL):
  - `piece_type` padres: `anillo`, `pendientes`, `collar`, `pulsera`, `colgante`, `tobillera`, `broche`, `cadena`
  - `materials` sustancias, **incluido `hilo`**: `plata`, `oro`, `baño de oro`, `hilo`, `latón`, `acero`, `resina`, `cuero`, `perla` (perla como cuerpo de pieza; si es engaste va a `stone_type`)
  - `stone_type`: lista **cerrada para el modelo**, YAML **ampliable para el mantenedor** (semilla del corpus + residual **`piedra`**). Sinónimos en el mismo fichero. Fuera de lista: `piedra` si el texto afirma gema/engaste; si no, `null`. Criterio de alta: «¿es gema/mineral reconocible?», no umbral de apariciones. No strings libres.
- Normalización de sinónimos en código / YAML («plata de ley», «925», «sterling» → `plata`; «hilo encerado» → `hilo`; «ámbar»/«amber» → `ambar`; sortija/alianza → `anillo`; gargantilla → `collar`; brazalete/esclava → `pulsera`; criollas/aro → `pendientes`).
- `materials: []` si no hay evidencia; nunca un material por defecto. Valor fuera de vocabulario → se rechaza (no se persiste).
- Confianza por **span** en el texto de entrada, no por el número que invente el modelo: con span → alto (p. ej. 0,85); sin span → bajo (p. ej. 0,45); ausente/`[]` → 0,20.
- `title` y `description` del perfil propuesto → **`null`**. `family_id` y `variant_label` → **`null`**.
- Settings `JPV_RAG_LLM_*` (distintas de `JPV_CATALOG_LLM_*`): `API_KEY`, `MODEL` (p. ej. `openai/gpt-4o`), `BASE_URL` opcional, `CONCURRENCY` (default 8). Opcionales en `/health`; exigidas al enriquecer de verdad.
- Auditor de puertas de lote **fuera del HTTP**: unicidad de SKU, vocabulario, cobertura de tags por estrato (lee JSONL). El POST no falla por cobertura del lote de 50.
- Dependencia `litellm` con **versión fijada** en `pyproject.toml` (S3: compromiso PyPI marzo 2026). C06b no se migra.
- Tests con LLM **falso** en `ai-service/tests/enrichment/` (carpeta ya reservada). Cero llamadas a proveedor en pytest.
- `openapi.json` **no cambia** (el contrato ya lo renegoció C08).

**Fuera de alcance (no):**

- Ejecutar `enrich-batch` AutoBulk sobre los 1.200 e indexarlos → verificación posterior, no entrega de esta HU. C12/C13 no se implementan aquí.
- Cualquier escritura sobre `Product` (nombre, SKU, precio, descripción).
- Persistencia de perfiles: es C08. C09 solo propone.
- Campo `piece_subtype`, hijos en `style_tags`, o diccionario de sinónimos de consulta → **C20**.
- `piedras preciosas` como material.
- **Instructor** (S4). Se apila encima de LiteLLM en C30+ si el retry de schema hace falta; no entra en C09.
- Migrar C06b a LiteLLM. El CLI de generate sigue en el SDK OpenAI.
- Renegociar el contrato para meter `text_provenance`, `collection_name` o `price`.
- UI, cola, asincronía, RDS, migración EF Core o Alembic.
- Familias (C18), `SourceText` (C11), feed (C12), revisión humana (C28).

**Decisiones de diseño ya acordadas** (exploración 2026-08-23):

| Tema | Decisión |
|---|---|
| Qué entrega C09 | El **endpoint real**. El catálogo enriquecido (lote AutoBulk) es verificación posterior |
| Dónde viven las puertas 70/90 | **Auditor / tests**, no un 422 del POST. El HTTP no recibe `text_provenance` |
| Cobertura de tags | Un producto cuenta si **al menos una** de las tres listas no está vacía. `original`/`short`: las tres vacías son válidas y no castigan. `sparse`: ≥ 1 lista. El 90 % sobre `ai_assisted` se mide en el auditor |
| Talla | Regex sobre `Name`, luego `Description`. Empate o duda → nombre. Nunca SKU |
| `piece_type` | Solo hiperónimos. Hijos (sortija, gargantilla, brazalete, criollas) → C20 + el `Name`. `colgante` es padre, no hijo de `collar` |
| `materials` | Sustancias, con `hilo`. Sin flag de piedras |
| `stone_type` | Cerrado para el modelo, YAML ampliable. Residual `piedra` si afirma gema y no concreta. Fuera de lista → `piedra` o `null`, nunca string libre. Ámbar/ónix/perla-engaste van aquí, no a materials |
| Confianza | Heurística por span. El umbral de tags de C08 (0,80) queda por encima del «sin span» |
| LLM | **LiteLLM** (S3). `JPV_RAG_LLM_MODEL=openai/gpt-4o` hoy; cambio de proveedor = config. 1 producto / llamada, temp 0 |
| Concurrencia | Semáforo `JPV_RAG_LLM_CONCURRENCY`, default **8** (tope de llamadas en vuelo dentro de un POST de 50). No compilado |
| `title` / `description` | `null`. Nadie aguas abajo los aplica; el índice usa `Product.Name` |
| Familia en la propuesta | `null`. C08 los ignora; C18 es otra autoridad |
| Contrato OpenAPI | **No se toca.** C08 ya puso `source` y `prompt_version` |
| Instructor (S4) | **No en C09.** S3 = LiteLLM (proveedor); S4 = Instructor (forma). Se apilan, no se eligen |

**Referencias:**
[proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C09, §0 16–23 ago),
[proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§7.1 pipeline, §7.3 materiales, §7.4 sinónimos / C20, §7.8 revisión, §8.5 puertas),
[Abstracción de proveedores y estrategias de fallback](../../Sesiones%20Master%20AIEng/S3_Patrones_Diseños_Wrappers_Modelos/Abstracci%C3%B3n%20de%20proveedores%20y%20estrategias%20de%20fallback.md) (LiteLLM, S3),
[Extracción de datos estructurados](../../Sesiones%20Master%20AIEng/S4_Productos_IA_avanzados/Extraccion%20de%20datos%20estructurados.md) y [Guardrails y validación de outputs](../../Sesiones%20Master%20AIEng/S4_Productos_IA_avanzados/Guardrails%20y%20validacion%20de%20outputs.md),
[epicas.md](../../epicas.md) (EP12),
[HU-AIENG-006a.md](HU-AIENG-006a.md), [HU-AIENG-006b.md](HU-AIENG-006b.md), [HU-AIENG-008.md](HU-AIENG-008.md),
specs vivas `openspec/specs/ai-service-api-contracts/spec.md`, `openspec/specs/product-ai-profile/spec.md`, `openspec/specs/real-catalog-corpus/spec.md`, `openspec/specs/synthetic-catalog-corpus/spec.md`,
contrato `ai-service/openapi.json` (no se regenera),
change OpenSpec `openspec/changes/add-catalog-enrichment-pipeline/` y su ticket técnico.

---

## Criterios de Aceptación

### Escenario 1: Una descripción con varios materiales produce una lista canónica
**Dado que** el texto nombra «plata de ley» y «baño de oro»
**Cuando** el extractor propone el perfil
**Entonces** `materials.value` contiene `plata` y `baño de oro` (canónicos, no las frases crudas)
**Y** `materials.source` es `inferred`
**Y** no aparece ningún valor fuera del vocabulario cerrado

### Escenario 2: Un sinónimo de material se normaliza; un valor inventado se rechaza
**Dado que** el texto dice «925» o «sterling», y en otro producto el modelo propone «mithril»
**Cuando** corre la validación contra el vocabulario
**Entonces** «925» / «sterling» quedan como `plata`
**Y** «mithril» no llega al perfil: o se descarta el campo o el producto lleva `materials: []` con aviso
**Y** un test dedicado afirma ambos caminos

### Escenario 3: Sin evidencia de material no se inventa uno
**Dado que** nombre y descripción no mencionan ninguna sustancia del vocabulario
**Cuando** se propone el perfil
**Entonces** `materials.value` es `[]`
**Y** la confianza de materials es baja
**Y** no se escribe `plata` ni ningún otro valor por defecto

### Escenario 4: La talla se lee del nombre y se marca `rule`
**Dado que** el nombre es «Colgante erizo de mar S» y el SKU es `SKU06`
**Cuando** corre la normalización determinista previa
**Entonces** `size_label.value` es la talla canónica (`S`)
**Y** `size_label.source` es `rule` y la confianza es `1.0`
**Y** el SKU no se inspecciona para extraer talla

### Escenario 5: Si nombre y descripción contradicen la talla, gana el nombre
**Dado que** el nombre lleva «M» y la descripción dice «talla L»
**Cuando** se resuelve `size_label`
**Entonces** el valor vigente es el del nombre
**Y** si solo la descripción tiene talla y el nombre no, se usa la de la descripción (como `rule` si la regex dispara)

### Escenario 6: Piedra genérica, tipo concreto y valor fuera de lista
**Dado que** un producto dice «lleva una piedra preciosa» sin nombrar cuál, otro dice «ámbar», y un tercero afirma gema con un tipo que no está en el YAML
**Cuando** se proponen los perfiles
**Entonces** el primero tiene `stone_type.value = piedra` y `materials` solo con las sustancias
**Y** el segundo tiene `stone_type.value` canónico (`ambar`) y **no** añade `piedra` (el campo es escalar)
**Y** el tercero queda en `piedra` (no se persiste el string libre)
**Y** un copy que solo habla de «relieve» o «brillo» deja `stone_type` nulo

### Escenario 7: El tipo de pieza es el hiperónimo, no el hijo
**Dado que** el nombre es «Gargantilla Horizonte Marfil» o «Brazalete suspiro» o «Anillo mini conchiglie»
**Cuando** se extrae `piece_type`
**Entonces** los valores son `collar`, `pulsera` y `anillo` respectivamente
**Y** no se persiste `gargantilla`, `brazalete` ni `sortija` como `piece_type`
**Y** `style_tags` no se usa como taxonomía de subtipo

### Escenario 8: Title, description y familia no se proponen
**Dado que** el contrato permite `title`, `description`, `family_id` y `variant_label`
**Cuando** el extractor real responde
**Entonces** esos cuatro campos van `null`
**Y** el stub de C08 puede seguir rellenándolos en `STUB_MODE=true` para no romper los tests de contrato que ya existen
**Y** ninguna columna de `Product` cambia

### Escenario 9: La confianza sigue al span, no al modelo
**Dado que** «plata» aparece literalmente en la descripción y un tag de ocasión se afirma sin aparecer en el texto
**Cuando** se asignan confianzas
**Entonces** materials queda por encima del umbral de auto-aprobación de tags de C08 (0,80)
**Y** el tag sin span queda por debajo (p. ej. 0,45)
**Y** no se copia un `confidence` inventado por el LLM

### Escenario 10: El POST no falla por cobertura de tags; el auditor sí mide por estrato
**Dado que** un lote HTTP de 50 productos `original` o `short` no tiene etiquetas comerciales
**Cuando** se llama `POST /v1/enrich/products`
**Entonces** la respuesta es 200 con perfiles honestos (listas vacías)
**Y** el auditor, sobre fixtures con `text_quality_tier` / `text_provenance` del JSONL, acepta las tres listas vacías en `original`/`short`
**Y** exige al menos una lista no vacía en `sparse`
**Y** evalúa el 90 % de cobertura sobre el estrato `ai_assisted` **fuera** del request HTTP

### Escenario 11: Arranque y tests no llaman al proveedor
**Dado que** C17 y el compose local no inyectan `JPV_RAG_LLM_API_KEY` en todos los perfiles
**Cuando** se arranca `GET /health` y se ejecuta pytest
**Entonces** `/health` no exige esa clave
**Y** la suite usa un LLM falso y no abre sockets a proveedores
**Y** con `STUB_MODE=false` y sin clave, el enriquecimiento real falla de forma explícita (no inventa perfiles)
**Y** `ai-service/openapi.json` no ha cambiado

### Escenario 12: Fuera de alcance explícito
**Dado que** esta historia está implementada
**Cuando** se revisa el entregable
**Entonces** no se ha ejecutado como parte del change el lote AutoBulk sobre los 1.200 (queda documentado como verificación posterior)
**Y** no hay pantalla, ni migración, ni columna nueva en `Product` ni en `ProductAiProfile`
**Y** no se ha implementado C11, C12, C18, C20 ni C28
**Y** `jbg_ai.api.main` no importa `jbg_ai.data`

---

## Notas adicionales

- **Actor:** el Administrador dispara el lote que C08 ya expone. Esta historia no añade endpoint .NET ni UI; cambia **qué responde** `jbg-ai`. El operador no interviene.

- **Por qué es 🔴.** Sin extractor real, `enrich-batch` rellena perfiles de stub (materiales cíclicos, talla «leída del SKU»). C11 construiría un `SourceText` mentiroso y C24 mediría un extractor que no existe.

- **Consumidor único.** C08 es quien llama. C09 no persiste. Si todo sale `inferred`, el enrutado `Routed` manda el catálogo a cola; `AutoBulk` indexa igual pero deja huella. Por eso `source: rule` en la talla no es cosmética.

- **Tests de contrato existentes.** `test_enrich_stub_exercises_both_provenances` y vecinos corren contra el cliente HTTP. Con `STUB_MODE=true` (perfil de test / snapshot) el stub permanece. Los tests nuevos de extracción viven en `tests/enrichment/` con el puerto LLM inyectado.

- **Apuntes S3 / S4.** LiteLLM es el cliente de runtime (S3: un puerto, el proveedor es config). Instructor no se añade en C09 (S4: forma / retry de schema); se apila encima de LiteLLM en C30+ si hace falta. Retry solo si el JSON no parsea. C06b no se migra.

- **OpenSpec:** change `add-catalog-enrichment-pipeline`. Llevará `design.md`: las decisiones de vocabulario, puertas y confianza tienen alternativas defendibles. Capability nueva prevista: `catalog-enrichment-pipeline`. El contrato vivo `ai-service-api-contracts` **no exige delta** si la forma del JSON no cambia.

---

## Tareas

1. Completar artefactos OpenSpec del change (proposal, design, specs, tasks).
2. Vocabularios cerrados + normalización de sinónimos + regex de talla (`Name` > `Description`) como funciones puras.
3. Prompt `enrichment/v1.md` + schema Pydantic + cliente LiteLLM (`JPV_RAG_LLM_*`, temp 0, 1 producto / llamada, semáforo `CONCURRENCY`).
4. Ensamblar el pipeline: regla previa → LLM → validación de vocabulario → confianza por span → `ProposedProfile` (`title`/`description`/`family_*` nulos).
5. Sustituir `require_stub_mode` en `/v1/enrich/products` por el pipeline cuando `STUB_MODE=false`; conservar el stub en `true`.
6. Auditor de puertas (tests + función) con estrato leído del JSONL; no enganchado al POST.
7. Settings `JPV_RAG_LLM_*` (incl. `CONCURRENCY`) opcionales al boot; dependencia `litellm` fijada; tests en `tests/enrichment/` con LLM falso; `openapi.json` intacto.
8. `openspec validate --all --strict` antes de archivar.

---

## Estimaciones y atributos de priorización

> Valores propuestos a partir de [Procedimiento-TicketsTrabajo.md](../../Procedimientos/Procedimiento-TicketsTrabajo.md) (§4.6). **Pendientes de validar** en refinamiento.

- **Puntos de historia:** **8** — no hay migración ni UI, pero es el primer LLM de *runtime* del servicio (LiteLLM + semáforo), con vocabularios, procedencia y un contrato que no se puede romper.
- **Impacto en usuario / Valor de negocio:** **4** — el Administrador no ve pantalla nueva; el operador pasa a buscar sobre atributos reales en lugar del ciclo del stub.
- **Urgencia (mercado / feedback):** **5** — 🔴; C11 no puede construir un `SourceText` honesto sin esto.
- **Complejidad / Esfuerzo:** **4** — la dificultad está en no inventar para aprobar las puertas y en honrar `source` para que C08 no revise el catálogo entero.
- **Riesgos y dependencias:**
  - **Prerrequisito:** C06a archivado (corpus y evidencia de talla/materiales). C08 archivado (contrato + enrutado). C06b archivado, no bloquea.
  - **Riesgo:** el POST se usa para «aprobar» cobertura inventando tags → mitigado: puertas fuera del HTTP; `[]` si no hay evidencia.
  - **Riesgo:** dos reglas de talla (Python vs un futuro .NET) → mitigado: solo Python; C08 ya decidió honrar `source`.
  - **Riesgo:** `JPV_RAG_LLM_*` se cuela en `/health` o se reutiliza la key de generate → mitigado: settings opcionales al boot; nombres distintos ya reservados por C06b.
  - **Riesgo:** LiteLLM sin pin o con un modelo sin prefijo de proveedor → mitigado: versión fijada en `pyproject.toml`; `MODEL` con prefijo (`openai/gpt-4o`).
  - **Riesgo:** 50 llamadas en paralelo rate-limitan; 1 en serie rompe el presupuesto de C08 → mitigado: semáforo configurable, default 8.
  - **Riesgo:** romper `test_openapi_snapshot_is_stable` → mitigado: no se toca el contrato.
  - **Riesgo:** la suite de contrato espera title relleno del stub → mitigado: stub intacto bajo `STUB_MODE=true`.
