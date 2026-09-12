# C28 — mediciones de exploración: la cola que no existe, y el error que la confianza no puede ver

**Change:** `add-profile-review-ui-and-metrics` *(sin crear todavía)* · **Fecha:** 2026-09-12
**Árbol explorado:** `ai-eng` en `151c949` · **Rama de implementación:** `c28-add-profile-review-ui-and-metrics`
**Corpus:** Postgres local `:5433/joiabagur_pv` · **1.200 perfiles** · 1.168 documentos vivos
**Huella del índice:** `051a6b06021efc3fb18891ffc7acfa2c6e3499f161aa81e9e96dd061233e073b`

*(`index_set_hash` canónico: SHA-256 sobre los `product_id` en formato `D`, orden de bytes,
concatenados en UTF-8 — la función que documenta
[`indexing/set_hash.py`](../../../ai-service/src/jbg_ai/indexing/set_hash.py). La huella de 32 hex que
publicó el informe de C26 no se reproduce con md5 sobre ids ni sobre SKU; se deja constancia del
método en vez de fabricar un número en una convención desconocida.)*

Siete mediciones tomadas antes de escribir una línea del change. **Tres puntos de la ficha del plan
resultan falsos del árbol**, y el más caro invalida su premisa operativa entera: la ficha se apoya en
que el enrutado híbrido de la decisión 5 acota la cola de revisión, y **sobre este corpus no acota
nada**.

---

## 1. La vía revisada está vacía, y no hay ningún estado donde poner la cola

```sql
SELECT "ReviewStatus", "ReviewOrigin", count(*),
       count("ReviewedByUserId") AS con_revisor,
       count("ReviewDurationMs") AS con_cronometro
FROM "ProductAiProfiles" GROUP BY 1,2;
```

| `ReviewStatus` | `ReviewOrigin` | perfiles | con revisor | con cronómetro |
|---|---|---:|---:|---:|
| `Approved` | `AutoBulk` | **1.168** | 0 | 0 |
| `Rejected` | `AutoBulk` | **32** | 0 | 0 |

**Ninguna fila en `Pending`, ninguna en `Human`.** Dos consecuencias que la ficha no anticipa:

1. La casilla del §16 —*métricas de revisión humana del enriquecimiento*— **no tiene hoy un solo dato
   del que salir**, y el §11.5 ya lo advertía: *«no existen sin la vía revisada»*.
2. **Una pantalla que filtre por `ReviewStatus = Pending` sale vacía.** «La cola» no es un estado que
   exista: hay que definirla, y esa definición es trabajo de diseño del change, no de implementación.

---

## 2. El enrutado híbrido de la decisión 5 no acota la cola. Cero.

```sql
SELECT "FieldSourceJson", count(*) FROM "ProductAiProfiles" GROUP BY 1 ORDER BY 2 DESC;
```

Solo existen **siete** formas distintas sobre 1.200 filas, y el patrón es rotundo:

| campo | `rule` | `inferred` | ausente |
|---|---:|---:|---:|
| `size_label` | **539** | 0 | 661 |
| `piece_type` | 0 | **1.173** | 27 |
| `materials` | 0 | **1.200** | 0 |
| `stone_type` | 0 | **629** | 571 |

**`size_label` es el único campo que el extractor marca `rule`; ningún otro lo hace jamás.** La
política del §7.8 —*«sensible inferido → revisión; sensible por regla → no»*— se traduce, sobre estos
datos, en que **el 100 % de los productos entra en la cola** con dos o tres campos sensibles cada uno.

El mecanismo está bien construido y correctamente probado. Su **efecto de filtrado sobre el corpus
real es nulo**, y por tanto la ficha no puede apoyarse en él para dimensionar el lote. Quien decide
qué se revisa tiene que ser un criterio de muestreo explícito, y hoy no está escrito en ningún
documento del proyecto.

---

## 3. La confianza no es una probabilidad: es un escalón de evidencia, y es ciega a la omisión

[`enrichment/confidence.py`](../../../ai-service/src/jbg_ai/enrichment/confidence.py) es explícito
desde su primera línea — *«The model's own score is never copied»* — y produce **cuatro valores**, no
un continuo:

| valor | constante | significado real |
|---|---|---|
| `1,00` | `CONFIDENCE_RULE` | Regla determinista (solo talla) |
| `0,85` | `CONFIDENCE_SPAN` | **La frase del vocabulario aparece literalmente** en nombre+descripción |
| `0,45` | `CONFIDENCE_NO_SPAN` | El modelo afirmó un valor **cuya frase no está en el texto** |
| `0,20` | `CONFIDENCE_ABSENT` | Ausente (`[]` o `null`) |

Es una buena decisión de diseño —no fiarse del autoinforme del modelo— y tiene una consecuencia
estructural que decide el muestreo de C28:

> **La heurística de span solo puede cazar falsos positivos. Es ciega, por construcción, a las
> omisiones.** Si el texto dice *«plata y baño de oro»* y el extractor devuelve `["plata"]`, la frase
> está en el texto → confianza **0,85** → la fila parece impecable y es incorrecta.

**No es teórico. Está medido:**

```sql
WITH t AS (SELECT lower(coalesce(p."Name",'')||' '||coalesce(p."Description",'')) txt,
                  pr."MaterialsJson"::jsonb m,
                  (pr."FieldConfidenceJson"::jsonb->>'materials')::numeric conf
           FROM "ProductAiProfiles" pr JOIN "Products" p ON p."Id" = pr."ProductId")
SELECT count(*) FILTER (WHERE txt LIKE '%hilo%' AND NOT m ? 'hilo') AS falta_hilo, ...
FROM t;
```

| material nombrado en el texto y **no** extraído | productos | de ellos, en el estrato de máxima confianza |
|---|---:|---:|
| `hilo` | 60 | 56 |
| `perla` | 35 | 26 |
| `plata` | 3 | 3 |
| `acero`, `latón` | 0 | 0 |
| **productos distintos afectados** | **94** | **81 (86 %)** |

**Una cola ordenada por confianza ascendente —el orden intuitivo, el que cualquiera escribiría— no
vería 81 de los 94 errores de omisión que hay en el catálogo.** Éste es el hallazgo que convierte el
muestreo en la decisión de más valor del change.

*(Cautela sobre `hilo`: puede aparecer en el texto como técnica —«hilo de plata»— y no como material,
en cuyo caso un revisor legítimamente no lo añadiría. Es exactamente el tipo de duda que la revisión
humana resuelve y ninguna métrica automática puede; el número es una **cota superior** de la clase,
no un recuento de errores confirmados.)*

---

## 4. Los tres estratos, con sus tamaños

Tomando el **peor** de los tres campos sensibles por producto (`stone_type` ausente no penaliza: la
mayoría de las joyas no lleva piedra):

| estrato | definición | productos | real | sintético |
|---|---|---:|---:|---:|
| **A · ausencia** | peor ≤ 0,20 | 148 | 8 | 114 |
| **B · sin evidencia** | peor ≤ 0,45 | 291 | 65 | 220 |
| **C · con evidencia** | peor = 0,85 | 761 | 331 | 430 |
| | | **1.200** | **404** | **764** |

Dos lecturas:

1. **En B, 270 de los 291 son `stone_type`:** el modelo afirma una piedra que el texto no nombra. Es
   el mayor riesgo individual del catálogo, y el estrato donde deberían concentrarse las **retiradas**.
2. **El corpus real vive casi entero en C** (331 de 404): su texto asistido es rico, así que los spans
   se encuentran. **Cruzar el muestreo por `data_origin` es inviable**: el estrato A solo tiene **8**
   productos reales, y no se puede llenar una celda de 30 con 8. El §15 no lo exige —dice
   expresamente que las métricas de enriquecimiento *«no se ven afectadas, porque miden al extractor
   y no la verdad del dato»*—, así que `data_origin` se reporta **descriptivamente** y no se diseña
   como eje de la muestra.

---

## 5. Los 32 rechazados no son fallos del extractor: son la tienda de regalos

```sql
SELECT pr."PieceType", pr."MaterialsJson", p."Name"
FROM "ProductAiProfiles" pr JOIN "Products" p ON p."Id" = pr."ProductId"
WHERE pr."ReviewStatus" = 3;
```

Velas (6), palo santo, cajas, postales, imanes y llaveros: artículos de regalo del catálogo, sin
`piece_type` en el vocabulario cerrado. **El rechazo es correcto**, y 26 de los 32 caen en el
estrato A.

Si el muestreo tirase de las 1.200, **~18 % de la cuota del estrato A se gastaría en confirmar que una
vela no es una joya** — y además inflaría artificialmente la tasa de acierto de ese estrato.

**Corrección al diseño del muestreo: la cola se dibuja sobre los 1.168 `Approved`**, el corpus que
realmente está indexado y que el sistema usa para vender. Los estratos quedan en **A 122 · B 285 ·
C 761**.

**Y una excepción, con un candidato ya a la vista.** Los 32 se revisan aparte, en una pasada corta,
con la pregunta invertida —*¿hay algún rechazo incorrecto?*— porque uno de ellos **no encaja con los
demás**: `Presión Oro`, con `piece_type: anillo` y `materials: ["oro"]`, está rechazado y tiene toda
la pinta de ser una sortija vendible que ha quedado fuera del índice. Si lo es, es un hallazgo con más
valor comercial que cualquier tasa.

---

## 6. El cronómetro: lo que C18b enseñó, y lo que C28 está a punto de repetir

```sql
SELECT count(*), count("ReviewSeconds"), avg("ReviewSeconds"),
       min("ReviewSeconds"), max("ReviewSeconds")
FROM "FamilyReviewVerdicts";
```

| juicios | cronometrados | media | mínimo | máximo |
|---:|---:|---:|---:|---:|
| 64 | **6** | **16,0 s** | 0,6 s | 34,6 s |

El informe de C18b (§ *«El tiempo medio no está, y decir por qué es más útil que estimarlo»*) explica
el 6 de 64 sin adornos: *«el cronómetro vivía en el estado del componente y moría con la pestaña»*. La
columna se añadió después, y **la media del entregable no existe para aquella ejecución**.

**C28 tiene la misma trampa, agravada:** su ficha pide **aprobación masiva por campo**, y el docstring
de `ReviewDurationMs` establece —correctamente— que en masa queda a `null`.

```text
  Si el lote se aprueba mayoritariamente en masa:
     tasa de corrección  →  sale, y sale baja (una aprobación es un cero)
     tiempo medio        →  NULL sobre casi todo el lote
  → la casilla del §16 se queda a medias por segunda vez
```

---

## 7. Lo que ya está puesto: el change es más barato de lo que su ficha sugiere

| Pieza que necesita | Estado medido |
|---|---|
| `ProposedProfileJson` | Presente, con `value` + `source` + `confidence` por campo. **La tasa de corrección es un diff de dos columnas** |
| `ReviewDurationMs`, `ReviewedByUserId`, `ReviewedAt` | Presentes y nulables |
| **Migración** | **Ninguna.** C08 reservó el almacenamiento por escrito y cumplió |
| `POST /api/product-families` | **Ya existe** (C07, `ProductFamiliesController:110`). Crear familia desde la revisión es **frontend puro** |
| Reindexado tras corregir | **Automático.** `IndexFeedRepository:41-47` incluye `profile.UpdatedAt` en la marca de agua, y `IsActive`/`ReviewStatus` viajan en la fila: una corrección se reindexa y una baja se propaga |
| Texto contra el que juzgar | `Products`: media **220 caracteres** de nombre + descripción, y solo **28** sin descripción |
| Superficie .NET que falta | `IProductAiProfileService` tiene **una** operación (`EnrichBatch`). No hay ruta de lectura, ni de aprobación, ni de métricas |
| Pantalla heredada | `family-review.tsx`, **920 líneas**, monolítica, `shadcn/Table` (no TanStack), **cero manejadores de teclado** |

**Aviso sobre `PromptVersion`.** Hay **1.178 en `enrichment/v1` y 22 en `v2`** — los de `FIX1`
(diadema, llavero, gemelos, broche, cinturón), todos sintéticos. El plan obliga a reportar por
`PromptVersion` para no mezclar poblaciones, y así se hará; pero **22 filas son una nota al pie, no
una comparación de versiones de prompt**, y el §11.6 no debe venderse con esto.

---

## 8. Las decisiones que la exploración deja tomadas

| # | Decisión | Alternativas descartadas, y por qué |
|---|---|---|
| **1** | **La cola es `ReviewOrigin = AutoBulk` sobre `Approved`**; revisar es pasar a `Human`. El estado gobierna el índice, el origen gobierna la métrica | **Abrir lote a `Pending`**: el feed selecciona `Approved`, así que los N saldrían del índice a mitad de sesión y se reindexarían al reaprobar. **Entidad `ReviewBatch`**: séptima migración, justo lo que C08 pagó por evitar. La independencia estado/origen ya es un requisito vivo de la spec |
| **2** | **Muestra estratificada A/B/C**, cuotas **60/60/60 = 180** (12-15 % del corpus, lo que el §15 ya declara). Tasa por estrato **y** total ponderado | **Peor confianza primero**: ciega a 81 de los 94 errores de omisión, y la tasa publicada sale sesgada al alza respecto al catálogo. **Aleatoria simple**: gasta el 63 % de la atención en el estrato C sin separar poblaciones, y no responde a *«¿sirve el span como triaje?»* |
| **3** | **Muestra determinista por semilla**: `hash(ProductId + semilla)` ordenado dentro de cada estrato. El lote es reproducible **sin persistirlo** | Persistir el lote exigiría migración. La semilla se declara en el informe de implementación y cualquiera reproduce los 180 |
| **4** | **El criterio del revisor es la fidelidad al texto de origen**, nunca la verdad de la pieza | Hay **0 fotos y 0 embeddings visuales**; los 764 sintéticos y el texto de los 404 reales los escribió un LLM. El criterio de verdad **no es ejecutable**, y el de fidelidad es exactamente lo que el §11.5 afirma medir. Va como requisito de spec, con el texto completo visible junto a cada fila |
| **5** | **La corrección se reporta con dirección**: adición (omisión cazada) / retirada (alucinación cazada) / sustitución / confirmación | Reportar solo *«corregido: sí/no»* tira justo lo que el diseño estratificado fue a buscar. Predicción falsable: adiciones concentradas en **C**, retiradas en **B** |
| **6** | **Dos poblaciones separadas en métricas**: revisado ítem a ítem (cronometrado) y aprobado en masa (sin tiempo). Nunca una media mezclada. Cronómetro **persistido en cada guardado** | Es el patrón ya entregado y probado en `FamilyReviewMetricsDto` (`TimedJudgements`, `null` en vez de cero). La aprobación masiva se permite **solo dentro de un estrato y un campo**, y queda marcada |
| **7** | **En el estrato C la pregunta al revisor es «¿falta algo?»**, no «¿es correcto?» | Son tareas cognitivas distintas. Si la pantalla pide la equivocada, el revisor confirma sin leer la descripción entera — que es exactamente cómo se pierden las 81 omisiones |
| **8** | **Extracción de carcasa estrecha**: `useItemStopwatch()`, `<ThreeStateList>`, `useReviewKeyboard()`. Tabla, barra masiva y tarjeta de métricas **se copian** | Extraer las 920 líneas enteras es refactorizar una pantalla ya validada por una persona **con la suite de frontend en rojo de base (118 de 482)**: la regresión no la cuenta nadie. Solo se generaliza lo que tiene **dos consumidores reales** |
| **9** | **Los atajos llegan a las dos pantallas**, vía el hook extraído | Si solo llegan a la de perfiles, la **tarea 6.4 de C18b sigue siendo falsa en el archivo**. Con dos consumidores, la extracción del hook queda además justificada por sí misma |
| **10** | **Crear familia desde la revisión entra**, como **requisito separado en la spec de `family-review`**, con los 9 SKU heredados como caso de prueba | Mezclarlo con la revisión de perfiles cruzaría dos capacidades dentro de un requisito. Dejarlo fuera obligaría a abrir un change que hoy no está en el plan. El `POST` ya existe: el coste es de frontend |
| **11** | **El A/B de teclado se fabrica a propósito**: primeros ~40 ítems a ratón, resto con teclado, alternando estratos | Los atajos van en el mismo change, así que **no existe un «antes» salvo que se reserve**. El efecto aprendizaje juega a favor del teclado y **se declara**, igual que el §15 declara el etiquetador único del golden set |

---

## 9. Las refutaciones de la ficha, en una tabla

| Lo que decía la ficha | Lo que la medición obliga | Motivo |
|---|---|---|
| Se apoya en el enrutado híbrido para acotar la revisión | **El enrutado no acota nada**; hace falta un criterio de muestreo explícito | `size_label` es el único campo `rule` que el extractor produce: el 100 % de los productos tiene dos o tres campos sensibles inferidos |
| No dice de dónde sale el lote | **Muestra estratificada A/B/C, determinista, sobre los 1.168 `Approved`** | Sin criterio escrito la tasa de corrección no es interpretable; y cualquier orden por confianza es ciego a 81 de los 94 errores de omisión medidos |
| «aprobación masiva por campo», sin más | Permitida **solo dentro de un estrato y un campo**, marcada, y con las dos poblaciones **reportadas aparte** | Vacía la segunda métrica del §16 — el fallo exacto que C18b ya cometió (6 tiempos de 64 juicios) |
| **Zona:** frontend + `Application/` | Correcta, **más `API/Controllers/` y `Tests/`** — y el frontend toca **dos** pantallas, no una | Crear familia y los atajos aterrizan también en `family-review.tsx`. Es la enésima vez que la zona de una ficha se queda corta |
| *(nada sobre el criterio de revisión)* | **Fidelidad al texto de origen**, declarado en la spec y visible en pantalla | 0 fotos en el sistema: el criterio de verdad de la pieza no es ejecutable |
| *(nada sobre la dirección de la corrección)* | **Adición / retirada / sustitución / confirmación** | Es lo que separa omisión de alucinación, y sin ello el diseño estratificado no rinde |
| «tiempo medio de revisión» | Cronómetro **persistido en cada guardado**, jamás acumulado en el componente | C18b perdió 58 de sus 64 tiempos exactamente por eso |

---

## 10. Lo que este change no puede cerrar solo

**C28 no está terminado cuando compila.** Su entregable es un número, y el número no existe hasta que
haya **una sesión real de 180 ítems**. Eso es una tarea de `tasks.md` que no es código, y es la que
puede quedarse sin hacer: el precedente está en C18b, que entregó el mecanismo y dejó la media sin
medir. A 16 s/ítem medidos para un juicio binario de familia, y con tres a cinco campos por producto
aquí, la estimación razonable es **30-40 s/ítem → 1,5-2 h**, una sesión.

**Capacidad estadística de las cuotas elegidas.** Con n = 60 por estrato, el intervalo de confianza al
95 % sobre una tasa del 0,35 es de aproximadamente **±0,12**. Suficiente para separar B de C si el
efecto es grande —que es la hipótesis que la exploración deja planteada—, insuficiente para un
intervalo fino. Se declara así en el informe de implementación y no se presenta como una precisión que
no se tiene.
