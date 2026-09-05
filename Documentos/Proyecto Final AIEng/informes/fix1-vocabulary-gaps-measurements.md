# Informe FIX1 — Corrida de reenriquecimiento de la cohorte de veintidós

> Acta de ejecución del change [`fix-enrichment-vocabulary-gaps`](../../../openspec/changes/fix-enrichment-vocabulary-gaps/).
> **Fecha:** 2026-09-05 · **Entorno:** local (PostgreSQL 15 en `:5433`, `jbg-ai` en `:8001`, API .NET en `:5056`).
> **Exploración previa:** [fix1-exploration-measurements.md](fix1-exploration-measurements.md) · **Historia:** [HU-AIENG-FIX1](../../Historias/AI-Eng/HU-AIENG-FIX1.md)

---

## 1. Condiciones de la corrida

| Condición | Valor |
|---|---|
| `STUB_MODE` | `false` — verificado con `printenv` dentro del contenedor |
| Modelo | `openai/gpt-4o-mini`, `JPV_RAG_LLM_CONCURRENCY=2` (override del runbook de C12 para TPM de tier 1) |
| Prompt | `enrichment/v2`, servido desde `/app/prompts/enrichment/v2.md` de la imagen reconstruida |
| Cohorte | los **22 SKU enumerados** en `design.md` D1, en **un solo lote** (`MaxBatchSize = 50`) |
| Petición | `POST /api/ai/catalog/enrich-batch` con `force: true` y `reviewMode: "AutoBulk"` |
| Comprobación previa | ningún perfil de la cohorte tenía `ReviewedByUserId` ni `ReviewedAt`; **no se perdió revisión humana** y no hubo ningún `enrich_profile_review_reset` |

**El modelo coincide con el de los 1.178 perfiles no reenriquecidos**, que también son `openai/gpt-4o-mini`.
Las dos poblaciones se distinguen por `PromptVersion` y no por modelo, que es lo que hace comparable la tabla.

---

## 2. La primera corrida falló, y el fallo era del encargo

**Hay que contarlo porque es el resultado más útil de la corrida.** La primera ejecución de `v2` dejó
**dos de los tres llaveros sin tipo**:

| SKU | Nombre | 1.ª corrida | Esperado |
|---|---|---|---|
| SKU415 | Llavero Cala Galdana | `NULL` | `llavero` |
| SKU417 | Llavero Cape Nao pequeño | `NULL` | `llavero` |
| SKU416 | Llavero Cape Nao Grande | `llavero` | `llavero` |

Sin `warnings`: el modelo **devolvió nulo**, no propuso un valor que el pipeline rechazara. Y los tres
textos son casi idénticos entre sí, así que no era falta de evidencia.

**Causa.** La línea nueva del encargo —la que la HU pedía— dice que el catálogo puede contener
*servicios, consumibles y **artículos de regalo***, y que para esas filas `piece_type` es nulo. **Un
llavero es literalmente un artículo de regalo.** El modelo hizo exactamente lo que se le pidió: la
advertencia nueva se comió un canónico nuevo. Es el mismo patrón que motivó el change —una instrucción
bien formada que produce un resultado falso— reproducido dentro de él.

**Corrección.** Dos frases de `v2.md`, sin tocar la lista ni el vocabulario:

- se declara la precedencia: *«La lista cerrada manda sobre esta advertencia: si uno de sus términos
  nombra la pieza, ese término gana aunque el artículo sea además de regalo»*;
- la regla del nombre propio se acota para que no niegue el sustantivo núcleo: *«Un **nombre propio**
  que contenga un término de la lista no manda sobre el sustantivo núcleo del nombre […]. El sustantivo
  núcleo sí es evidencia, y a menudo la única que hay»*.

**La cohorte entera se volvió a correr con el texto corregido**, no sólo los dos fallidos: si no, veintidós
perfiles sellados `enrichment/v2` habrían venido de dos textos distintos, que es justo la propiedad que la
derivación de la ruta desde `PROMPT_VERSION` existe para proteger. Coste: 22 llamadas más.

**Lo que esto demuestra:** la evaluación del prompt **es** la corrida. Ningún test con un `EnrichLlm`
falso podía haber detectado esto, porque el fallo estaba en el enunciado y no en el pipeline.

---

## 3. Resultado: las 22 filas, diff completo

`-` es nulo o lista vacía. La columna de tipo es la única que la cohorte pretendía mover; el resto se
publica porque el reenriquecimiento las mueve y ocultarlo sería el pecado que este change corrige.

| SKU | Nombre | tipo antes → después | otros campos que se movieron |
|---|---|---|---|
| SKU498 | Diadema Calor del Volcán | `-` → **`diadema`** | — (confianza 0,330 → 0,417) |
| SKU862 | Diadema Ola de Coral | `-` → **`diadema`** | materiales `[]`→`["oro"]` · piedra `onix`→`piedra` · color `[]`→`["negro"]` |
| SKU933 | Diadema Reflejo de Coral | `-` → **`diadema`** | materiales `[]`→`["oro"]` · piedra `piedra`→`-` |
| SKU1082 | Diadema de Hilo de Plata y Oro | `-` → **`diadema`** | — |
| SKU1090 | Diadema Sueños de Plata | `-` → **`diadema`** | — |
| SKU617 | Diadema Luz de Luna | `broche` → **`diadema`** | estilo `["etnico"]`→`[]` |
| SKU821 | Diadema Lira | `broche` → **`diadema`** | — |
| SKU1105 | Diadema Hilos de Encaje | `broche` → **`diadema`** | — |
| SKU658 | Diadema Resplandor Volcánico | `colgante` → **`diadema`** | — |
| SKU720 | Diadema Encanto de Hielo | `collar` → **`diadema`** | — |
| SKU843 | Diadema Virgo | `collar` → **`diadema`** | color `["azul"]`→`["plateado"]` · estilo `["clasico"]`→`[]` |
| SKU844 | Gemelos Hércules | `-` → **`gemelos`** | — |
| SKU859 | Gemelos de Coral | `-` → **`gemelos`** | materiales `[]`→`["oro"]` · piedra `coral`→`piedra` |
| SKU500 | Gemelos Ardor Metálico | `broche` → **`gemelos`** | piedra `piedra`→`-` |
| SKU667 | Gemelos Brasa Elegante | `broche` → **`gemelos`** | — |
| SKU415 | Llavero Cala Galdana | `-` → **`llavero`** | ocasión `["diario"]`→`[]` |
| SKU417 | Llavero Cape Nao pequeño | `-` → **`llavero`** | — |
| SKU416 | Llavero Cape Nao Grande | `broche` → **`llavero`** | — |
| SKU936 | Cinturón Ola Dorada | `-` → **`cinturon`** | materiales `[]`→`["oro"]` · piedra `onix`→`piedra` · color `[]`→`["dorado","negro"]` |
| SKU845 | Joya del Zodiaco | `-` → **`-`** | **ninguno.** Fila idéntica campo a campo |
| **SKU822** | **Broche Cinturón de Orión** | `broche` → **`broche`** | **ninguno.** Fila idéntica campo a campo |
| **SKU882** | **Anillo Cinturón de Orión** | `anillo` → **`anillo`** | **ninguno.** Fila idéntica campo a campo |

**19 cambian de tipo, 1 sigue nulo por ser correcto, 2 no se mueven.** Es la tabla que `design.md` D1
declaró antes de ejecutarla.

### 3.1 Veredicto del grupo de control

**Los dos «Cinturón de Orión» no se movieron en ningún campo**, ni siquiera en la confianza
(SKU822 0,458 → 0,458; SKU882 0,460 → 0,460). Añadir `cinturon` al vocabulario cerrado **no arrastró
el nombre propio**: el riesgo mayor de `v2` queda medido y no supuesto. `SKU845 Joya del Zodiaco` se
comporta igual: descripción vacía, ningún término la nombra, y el nulo se conserva.

### 3.2 Movimientos colaterales, que no se ocultan

Fuera del tipo, la corrida movió campos en 9 de las 22 filas. Dos patrones, ninguno atribuible al
vocabulario nuevo:

- **`stone_type` pierde concreción en tres filas** — `coral`→`piedra` (SKU859), `onix`→`piedra`
  (SKU862, SKU936) — y desaparece en dos (SKU500, SKU933). Es una **regresión de calidad**, pequeña y
  real: el residual es menos informativo que el tipo concreto.
- **`materials` gana `oro` en cuatro filas** que antes tenían la lista vacía, y la confianza sube en 19
  de las 22.

Ambos son variación del extractor entre dos invocaciones, no efecto de los cuatro términos: las filas
afectadas no comparten el tipo nuevo. Se dejan escritos porque **1,6 % del corpus se ha movido** y quien
lea una métrica agregada de `stone_type` debe saberlo.

---

## 4. Recuentos: la aceptación es estructural

Medido sobre `ai.product_document` (1.168 filas) **después** de la sincronización.

| Comprobación | Antes | Después | Esperado |
|---|---:|---:|---:|
| `piece_type = 'diadema'` | 0 | **11** | 11 ✅ |
| `piece_type = 'gemelos'` | 0 | **4** | 4 ✅ |
| `piece_type = 'llavero'` | 0 | **3** | 3 ✅ |
| `piece_type = 'cinturon'` | 0 | **1** | 1 ✅ |
| `piece_type IS NULL` | 11 | **1** | 1 ✅ |
| `broche` | 85 | **79** | 79 ✅ |
| Impostores dentro de `broche` | 6 | **0** | 0 ✅ |
| `collar` | 140 | **138** | −2 ✅ |
| `colgante` | 161 | **160** | −1 ✅ |
| Perfiles en `enrichment/v2` | 0 | **22** | 22 ✅ |
| Perfiles en `enrichment/v1` | 1.200 | **1.178** | 1.178 ✅ |

**El criterio léxico de la ficha no se usa como prueba.** *«Buscar "diadema" pasa de cero a resultados»*
ya se cumplía antes del change —la rama léxica de C21 alcanzaba los 11 documentos por el nombre—, así
que firmarlo verde no habría demostrado nada.

---

## 5. Sincronización del índice

Una sola pasada incremental, `python -m jbg_ai.indexing sync`:

```
upserted=19 skipped=1149 deleted=0 failed=0
```

**19 filas reembebidas = 19 filas cuyo `source_hash` cambió**, comprobado comparando el hash de las
1.168 filas antes y después. Son la cohorte menos las tres cuyo perfil no se movió (SKU822, SKU882,
SKU845): `doc_text` idéntico, hash idéntico, sin reembeber. El indexador no tocó una sola fila de más.

`embedding_version` (`openai/text-embedding-3-small:1536:source-text/v1`) y `text_provenance` **no se
movieron en ninguna de las 1.168 filas**. No se mezclan dos espacios geométricos.

---

## 6. Verificación por la interfaz

Con sesión real de operador contra `POST /api/ai/search`, que es la llamada que emite el panel de
búsqueda asistida (`pages/sales/assisted.tsx` itera sobre `PIECE_TYPE_OPTIONS`).

| Filtro | Candidatos | En surtido del PdV | Contenido |
|---|---:|---:|---|
| «Diadema» | **11** | 6 | las once diademas del catálogo; **todas** son diademas |
| «Broche» | 60 (tope de sobre-recuperación) | 29 | **ningún** impostor: ni diadema, ni gemelos, ni llavero |
| «Gemelos» | 4 | 2 | los cuatro gemelos |
| «Cinturón» | 1 | 1 | `Cinturón Ola Dorada` |
| «Llavero» | 1 | 1 en Taller Joia Bagur | `Llavero Cala Galdana` |

**Nota de entorno, no del change:** la ruta asistida está **apagada por defecto en local**
(`AiSearch:EnabledByDefault` es `false` y ningún punto de venta está en la lista de permitidos). Con
la puerta cerrada, `/api/ai/search` degrada a un listado de catálogo que **ignora el filtro de
categoría** y devuelve lo mismo para las cinco categorías. Fue el primer resultado observado, y no es
un fallo de este change: es la puerta de despliegue de C16 haciendo su trabajo. La verificación se
repitió con `AiSearch__EnabledByDefault=true` **como variable de entorno**, sin modificar ningún
fichero del repositorio.

En los 5 puntos de venta que no llevan llavero, el facet «Llavero» devuelve lista vacía. Es el
comportamiento correcto y declarado en `design.md` D5, y ya era cierto para `cadena`.

---

## 7. Suites, comparadas por nombre de test

| Suite | Línea base (antes del change) | Después | Veredicto |
|---|---|---|---|
| `ai-service` (`uv run pytest`) | **697 pasan, 0 fallan** | **704 pasan, 0 fallan** | conjunto de fallos idéntico: **vacío**. Los 7 nuevos son los tests de este change |
| `frontend` (`npm run test`) | **113 fallan / 455 pasan** (14 ficheros de 47) | **113 fallan / 456 pasan** | **conjunto de nombres de test fallidos idéntico** al de la línea base |
| `npm run build` | — | limpio, salida 0 | la puerta real del frontend |

Los 113 fallos del frontend son los preexistentes que documenta
[testing-frontend.md](../../testing-frontend.md); ninguno está en `materials-vocabulary.test.ts`.

Sin migraciones, ni de Alembic ni de EF Core. **`ai-service/openapi.json` sin diff** y
`test_openapi_snapshot_is_stable` en verde. **`prompts/enrichment/v1.md` sin diff**, para que los 1.178
perfiles que declaran venir de él sigan pudiendo demostrarlo.

---

## 8. Lo que queda anotado

- **El vocabulario está replicado en cinco sitios y ahora hay una medición de lo que cuesta moverlo:**
  cinco ficheros, cuatro tests fijados, dos lenguajes y dos specs vivas, para cuatro términos. El
  endpoint que agregue los tipos realmente presentes en el surtido sigue sin ficha propia.
- **`filigrana` sigue abierta** como laguna de `style_tags`, con su motivo actualizado en las
  exclusiones del overlay, y es el ejemplo al que apunta ahora el test guardián.
- **La línea del prompt sobre servicios y consumibles no tiene población medible** en este corpus —C18a
  retiró del índice las 32 no-joyas—, así que su valor es prospectivo. Lo que sí quedó medido, y no se
  esperaba, es que esa misma línea **puede comerse un canónico** si no se declara la precedencia.
- **`Llavero Cape Nao` Grande y pequeño comparten tipo por primera vez** y podrían formar familia. Correr
  la sugerencia de C18a sigue fuera de alcance.
