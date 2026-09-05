# FIX1 — mediciones de la exploración (`fix-enrichment-vocabulary-gaps`)

**Medido el 2026-09-05** contra el PostgreSQL local (`jpv-pv-postgres`, puerto 5433,
PostgreSQL 15.19), sobre los **1.168 documentos vivos** de `ai.product_document`, los
**1.200 perfiles** de `public."ProductAiProfiles"` y las filas de `ai.pos_projection` que
dejó C22.

**Todo en solo lectura.** No se escribió una fila en ninguna tabla, ni en `public` ni en `ai`.
**Sin llamadas a proveedor**: ni embeddings ni LLM. Las mediciones léxicas usan el `tsv`
generado que ya está en el índice.

Esta nota es el punto de partida de la HU y el ticket. **No es el informe del change**: ése
será `fix1-vocabulary-gaps-measurements.md`, que publicará la tabla antes/después de la
corrida de reenriquecimiento. Aquí sólo está el «antes», que es lo que hay que decidir sobre.

---

## 1. El hallazgo que cambia el alcance

La ficha de FIX1 en el §3 del plan cuenta **11 productos con `piece_type` nulo**. Es exacto.
Lo que no cuenta es la otra mitad:

```
Productos cuyo nombre lleva uno de los cuatro términos:  22
├── 11  piece_type NULL      ← lo que la ficha ve
├──  9  piece_type ERRÓNEO   ← lo que la ficha no ve
└──  2  piece_type CORRECTO  ← falsos amigos que NO se deben tocar
```

**El nulo no es el peor síntoma.** Un nulo es honesto: no casa con ningún facet y nadie miente.
Una etiqueta equivocada sí miente, y el filtro es **duro** —
[`search.py:135`](../../../ai-service/src/jbg_ai/retrieval/search.py) hace
`AND d.piece_type = :category`. Hoy el facet `broche` devuelve 85 documentos de los que
**6 no son broches**.

---

## 2. Medición 1 — la tabla de las 22 filas, estado «antes»

```sql
SELECT p."SKU", p."Price", COALESCE(a."PieceType",'<NULL>') AS tipo,
       a."ReviewStatus", p."IsActive", p."Name"
FROM public."Products" p
LEFT JOIN public."ProductAiProfiles" a ON a."ProductId" = p."Id"
WHERE lower(translate(p."Name",'áéíóúÁÉÍÓÚñÑ','aeiouAEIOUnN'))
      ~ '(diadema|gemelo|cinturon|llavero|zodiaco)'
ORDER BY tipo, p."SKU";
```

Las 22 filas. `ReviewStatus = 2` (**Approved**) e `IsActive = true` en las 22, sin excepción,
así que las 22 están en el índice y son buscables hoy.

| # | SKU | Precio | `piece_type` hoy | Nombre | Veredicto | ¿Cohorte? |
|---|---|---:|---|---|---|---|
| 1 | SKU498 | 650,00 | `<NULL>` | Diadema Calor del Volcán | falta tipo | ✅ cambia |
| 2 | SKU862 | 340,00 | `<NULL>` | Diadema Ola de Coral | falta tipo | ✅ cambia |
| 3 | SKU933 | 1040,00 | `<NULL>` | Diadema Reflejo de Coral | falta tipo | ✅ cambia |
| 4 | SKU1082 | 980,00 | `<NULL>` | Diadema de Hilo de Plata y Oro | falta tipo | ✅ cambia |
| 5 | SKU1090 | 425,00 | `<NULL>` | Diadema Sueños de Plata | falta tipo | ✅ cambia |
| 6 | SKU617 | 875,00 | **`broche`** | Diadema Luz de Luna | **mal etiquetado** | ✅ cambia |
| 7 | SKU821 | 340,00 | **`broche`** | Diadema Lira | **mal etiquetado** | ✅ cambia |
| 8 | SKU1105 | 205,00 | **`broche`** | Diadema Hilos de Encaje | **mal etiquetado** | ✅ cambia |
| 9 | SKU658 | 470,00 | **`colgante`** | Diadema Resplandor Volcánico | **mal etiquetado** | ✅ cambia |
| 10 | SKU720 | 180,00 | **`collar`** | Diadema Encanto de Hielo | **mal etiquetado** | ✅ cambia |
| 11 | SKU843 | 145,00 | **`collar`** | Diadema Virgo | **mal etiquetado** | ✅ cambia |
| 12 | SKU844 | 160,00 | `<NULL>` | Gemelos Hércules | falta tipo | ✅ cambia |
| 13 | SKU859 | 260,00 | `<NULL>` | Gemelos de Coral | falta tipo | ✅ cambia |
| 14 | SKU500 | 230,00 | **`broche`** | Gemelos Ardor Metálico | **mal etiquetado** | ✅ cambia |
| 15 | SKU667 | 830,00 | **`broche`** | Gemelos Brasa Elegante | **mal etiquetado** | ✅ cambia |
| 16 | SKU415 | 28,00 | `<NULL>` | Llavero Cala Galdana | falta tipo | ✅ cambia |
| 17 | SKU417 | 85,00 | `<NULL>` | Llavero Cape Nao pequeño | falta tipo | ✅ cambia |
| 18 | SKU416 | 155,00 | **`broche`** | Llavero Cape Nao Grande | **mal etiquetado** | ✅ cambia |
| 19 | SKU936 | 1300,00 | `<NULL>` | Cinturón Ola Dorada | falta tipo | ✅ cambia |
| 20 | SKU845 | 200,00 | `<NULL>` | Joya del Zodiaco | **intipificable** | ⚠️ sigue nulo |
| 21 | SKU822 | 275,00 | `broche` | Broche **Cinturón de Orión** | **correcto** | 🔒 control |
| 22 | SKU882 | 185,00 | `anillo` | Anillo **Cinturón de Orión** | **correcto** | 🔒 control |

**Los dos falsos amigos.** «Cinturón de Orión» es el nombre de la constelación, no el tipo de
pieza. Es el mismo patrón que la exclusión medida `piel → cuero` del overlay de C20, pero
éste no estaba documentado en ninguna parte. Añadir `cinturon` al vocabulario los pone en
riesgo: por eso entran en la corrida **como grupo de control que debe no moverse**.

**SKU845 «Joya del Zodiaco»** tiene la descripción vacía en el JSONL de origen
(`text_quality_tier = short`). Ningún término nuevo lo nombra: **seguirá nulo, y ése es el
resultado correcto.** Merece test propio en vez de aparecer como pendiente sin explicar.

---

## 3. Medición 2 — la contaminación que la cohorte «sólo los 11» dejaría intacta

```sql
SELECT COALESCE(a."PieceType",'<NULL>') AS tipo, COUNT(*)
FROM public."ProductAiProfiles" a WHERE a."ReviewStatus" = 2 GROUP BY 1 ORDER BY 2 DESC;
```

Distribución viva, idéntica en `ProductAiProfiles` y en `ai.product_document` — el índice está
sincronizado:

| tipo | documentos | impostores de las 22 | % contaminado |
|---|---:|---:|---:|
| pendientes | 275 | 0 | — |
| anillo | 268 | 0 | — |
| pulsera | 207 | 0 | — |
| colgante | 161 | **1** | 0,6 % |
| collar | 140 | **2** | 1,4 % |
| **broche** | **85** | **6** | **7,1 %** |
| tobillera | 14 | 0 | — |
| `<NULL>` | 11 | 11 | — |
| cadena | 7 | 0 | — |

`broche` es el cajón de sastre del extractor: seis de sus nueve piezas cuyo nombre no dice
«broche» son tres diademas, dos gemelos y un llavero. Corregirlas lo lleva de **76/85 (89 %)**
a **76/79 (96 %)** de acuerdo entre nombre y tipo.

---

## 4. Medición 3 — el criterio de aceptación de la ficha ya pasa hoy

La ficha fija la demostración de extremo a extremo así: *«buscar "diadema" pasa de cero a
resultados»*. Medido contra el `tsv` vivo:

```sql
SELECT 'diadema', COUNT(*) FROM ai.product_document
WHERE tsv @@ plainto_tsquery('spanish','diadema');
```

| consulta | documentos alcanzados **hoy** |
|---|---:|
| `diadema` | **11** |
| `gemelos` | **4** |
| `cinturon` | **3** |
| `llavero` | **3** |
| `tiara` | 0 |

**Ese criterio ya se cumple antes del change.** La rama léxica de C21 devuelve las once
diademas porque «Diadema» está en el `Nombre` y el `Nombre` está en `doc_text`. Un verificador
que lo ejecute tras FIX1 verá once resultados y firmará **verde por el motivo equivocado** —
la lección de C17 en su forma más sutil.

Lo que FIX1 cambia de verdad es **estructural, no léxico**:

| criterio honesto | antes | después (cohorte B+) |
|---|---:|---:|
| `piece_type = 'diadema'` | 0 | **11** |
| `piece_type = 'gemelos'` | 0 | **4** |
| `piece_type = 'llavero'` | 0 | **3** |
| `piece_type = 'cinturon'` | 0 | **1** |
| `piece_type IS NULL` | 11 | **1** *(SKU845)* |
| impostores en el facet `broche` | 6 de 85 | **0 de 79** |
| opciones del desplegable «Tipo de pieza» | 8 | **12** |

---

## 5. Medición 4 — alcance por punto de venta de los cuatro facets nuevos

El facet no se sirve del catálogo sino del **surtido**: el CTE de
[`search.py:66-73`](../../../ai-service/src/jbg_ai/retrieval/search.py) filtra por
`pos_id = :pos_id AND is_assigned_hint IS TRUE`. Hay **11 puntos de venta con surtido**
(12 en la proyección; uno sin nada asignado).

| tipo | piezas en catálogo | POS con ≥1 (de 11) | media por POS |
|---|---:|---:|---:|
| **diadema** | 11 | **11 / 11** | 6,8 |
| **gemelos** | 4 | **11 / 11** | 3,1 |
| **cinturon** | 1 | **10 / 11** | 1,0 |
| **llavero** | 3 | **6 / 11** | 1,5 |
| *— línea de flotación —* | | | |
| `cadena` *(ya en el desplegable desde C16)* | 7 | **6 / 11** | 2,8 |
| `tobillera` *(ya en el desplegable)* | 14 | 11 / 11 | 8,8 |
| `broche` | 85 | 11 / 11 | 47,6 |

**La comparación que decide es contra `cadena`**, no contra `broche`: siete productos, 6 de 11
tiendas, 2,8 de media, y lleva desde C16 en el desplegable sin que nadie lo cuestione.
`diadema` y `gemelos` están holgadamente por encima; `cinturon` supera su cobertura de tiendas
(10 frente a 6); `llavero` la empata exactamente. **Ninguno de los cuatro introduce un caso
peor que el que el repositorio ya acepta.**

Como `piece_type = :category` es filtro duro, en las 5 tiendas sin llavero el facet «Llavero»
devolverá lista vacía. No es un fallo —es el comportamiento ya vigente para `cadena`— pero es
la frase que hay que dejar dicha para que nadie lo descubra como bug.

> **Corrección de la exploración.** Durante la sesión afirmé que «Cinturón devolverá 0 en diez
> de las once tiendas». Medido, es al revés: el cinturón único está asignado en **10 de 11**.
> El error fue razonar desde el tamaño del catálogo (1 pieza) cuando lo que gobierna el facet
> es el surtido.

---

## 6. Hallazgos de código que no son mediciones

### 6.1 FIX1 mueve **dos** specs vivas, no una

La ficha nombra sólo `catalog-enrichment-pipeline`. Falta
[`openspec/specs/query-expansion/spec.md`](../../../openspec/specs/query-expansion/spec.md),
cuyo requisito *«Dictionary entries and exclusions are justified against the corpus»* incluye:

> `#### Scenario: Vocabulary gaps are not smuggled in as synonyms`
> `- **AND** those terms are recorded as belonging to the vocabulary-gap change`

Cerrado el gap, esa frase queda falsa. Es exactamente el argumento que justifica que FIX1 sea
change y no commit suelto: `openspec validate --all --strict` seguiría en verde con las dos
mintiendo, porque valida estructura y no verdad.

Forma de los deltas:

```
specs/catalog-enrichment-pipeline/spec.md
  ## MODIFIED Requirements
    ### Requirement: Real enrichment replaces the stub when stub mode is off
        (el escenario fija prompt_version = enrichment/v1 → v2)
    ### Requirement: Closed vocabularies reject unknown values and invent nothing
        (la lista canónica pasa de 8 a 12 términos)
  ## ADDED Requirements
    ### Requirement: Non-jewellery rows get a null piece type

specs/query-expansion/spec.md
  ## MODIFIED Requirements
    ### Requirement: Dictionary entries and exclusions are justified against the corpus
```

`MODIFIED` obliga a reescribir el requisito entero con todos sus escenarios, y el de
vocabularios cerrados tiene cuatro. Es la parte más voluminosa del change y no lleva ni una
línea de algoritmo.

### 6.2 Los alambres que saltan son **cuatro**, no dos

| # | Test | Cómo falla | ¿La ficha lo prevé? |
|---|---|---|---|
| 1 | `test_base_vocabulary_terms_are_pinned` — [`test_synonyms.py:103`](../../../ai-service/tests/retrieval/test_synonyms.py) | assert de tupla; falla claro | ✅ sí |
| 2 | `materials-vocabulary.test.ts` — [frontend](../../../frontend/src/lib/materials-vocabulary.test.ts) | assert de array; falla claro | ✅ sí |
| 3 | `test_vocabulary_gaps_are_recorded_as_exclusions_not_smuggled_in` — `:265` | exige `llavero/diadema/gemelos/cinturon` en `exclusions` del overlay | ❌ **no** |
| 4 | `test_overlay_anchor_absent_from_the_base_is_a_vocabulary_gap` — `:70` | **usa `diadema` como ejemplo de canónico desconocido**: deja de lanzar → `DID NOT RAISE` | ❌ **no** |

El cuarto es el peligroso: falla **en la dirección contraria** a lo esperado —no «la lista
cambió» sino «la guarda dejó de dispararse»—, y el arreglo correcto es **darle otro término
desconocido como ejemplo**, no borrarlo. Borrarlo elimina la guarda que impide colar gaps de
vocabulario disfrazados de sinónimos.

Consecuencia de alcance: **el overlay de C20 entra en el change**, pese a que la ficha lo lista
como fuera de alcance. Sus cuatro `exclusions` dicen literalmente *«pertenece a
`fix-enrichment-vocabulary-gaps`»*; dejarlas es documentación bien formada y falsa, el pecado
exacto que justifica este change.

### 6.3 `PROMPT_VERSION` y la ruta del prompt están desacopladas

```python
# enrichment/constants.py:5
PROMPT_VERSION = "enrichment/v1"
# enrichment/pipeline.py:51
_PROMPT_RELATIVE = Path("prompts") / "enrichment" / "v1.md"
```

Dos sitios. Bumpear uno y no el otro sella los perfiles como `enrichment/v2` habiendo sido
producidos por `v1`, y desmonta en silencio el argumento del §0 del plan —*«el perfil
problemático es el que no dice con qué prompt nació»*—: el campo lo diría, y sería mentira.
**Decidido arreglarlo en este change** (decisión 7 del §7).

`v1.md` **no se edita ni se borra**: 1.178 perfiles seguirán afirmando venir de él y esa afirmación tiene
que seguir siendo verificable.

### 6.4 El vocabulario está replicado en cinco sitios

```
                   ┌──────────────────────────────────────────┐
                   │  enrichment/vocabularies.yaml            │  ← única fuente real
                   │  piece_type.terms  (8)                   │
                   └───┬──────────┬──────────┬────────────┬───┘
        deriva (C20)   │  duplica │  espeja  │ normativiza │
                       ▼          ▼          ▼             ▼
              SynonymDictionary  v1.md   materials-    specs/catalog-enrichment-pipeline
              _base_layer()      prompt  vocabulary.ts specs/query-expansion
```

Con los cuatro términos nuevos pasa de 8 a 12 entradas replicadas a mano, **+50 % de coste de
mantenimiento**. La alternativa mejor está escrita desde C16 en el docstring de
[`materials-vocabulary.ts`](../../../frontend/src/lib/materials-vocabulary.ts) y en la
decisión 6 del diseño: un endpoint que agregue los valores realmente presentes en el surtido
del punto de venta. Está **anotada para C28 por coincidencia de zonas** (frontend +
`Application/`), pero **no está en el alcance de C28**, cuya ficha es pantalla de revisión de
perfiles y métricas de corrección; ni su objetivo ni sus cuatro tests mencionan facets.

FIX1 no abre esa puerta: **le sube el precio a no cruzarla y le entrega la primera prueba.**
Desde C09 la lista nunca se había movido, así que el argumento era teórico; después de este
change habrá quedado demostrado que mover un término cuesta cinco ficheros y cuatro tests en
dos lenguajes. Material para el §0 del plan, y probablemente para que la nota deje de estar
adosada a C28 y pase a ficha propia. **No se toca en este change.**

### 6.5 El prompt no lo puede probar la suite unitaria

`test_service_and_consumable_rows_get_null_piece_type` con un `EnrichLlm` falso **no prueba
nada sobre el enunciado**: el falso devuelve lo que se le programe, y la spec viva prohíbe
abrir sockets a proveedores en la suite. Dos salidas honestas: renombrarlo a lo que realmente
prueba, y aceptar que **la corrida de reenriquecimiento ES la evaluación**, con su tabla
antes/después en `fix1-vocabulary-gaps-measurements.md`.

Matiz incómodo: la línea del prompt sobre servicios y consumibles **no tiene población
medible**, porque C18a ya retiró del índice los 32 no-joyas. Su valor es prospectivo —la
próxima ingesta real—. Conviene decirlo en la HU en vez de fingir que se demuestra.

### 6.6 Efecto colateral que se declara y no se ejecuta

`Llavero Cape Nao Grande` (SKU416, hoy `broche`) y `Llavero Cape Nao pequeño` (SKU417, hoy
nulo) son **dos variantes de tamaño de la misma pieza**. El agrupador de C18a agrupa por
`(piece_type, root)` — [`grouping.py:164`](../../../ai-service/src/jbg_ai/families/grouping.py) —
así que hoy no pueden formar familia, y con la cohorte «sólo los 11» seguirían sin poder: uno
sería `llavero` y el otro `broche`. **Sólo la cohorte completa los deja en condiciones.**
Correr la sugerencia de familias está fuera de alcance; dejarlo escrito, no.

### 6.7 La corrida no pierde revisión humana, pero hay que comprobarlo

[`ProductAiProfileService.Upsert`](../../../backend/src/JoiabagurPV.Application/Services/ProductAiProfileService.cs)
limpia `ReviewedByUserId` y `ReviewedAt` y fija `ReviewOrigin = AutoBulk` en cada
reenriquecimiento, registrando `enrich_profile_review_reset`. Los 1.200 perfiles son
`enrichment/v1` en modo `AutoBulk`, así que **no hay revisión humana que perder** — pero es
algo a comprobar antes de la corrida, no a suponer.

`SourceHash` se calcula del **texto de origen del producto**, no del perfil, así que no cambia
al reenriquecer: `request.Force` es imprescindible *(el §0 del plan lo llamaba `ignoreHash`,
que no existe)*. Y como `doc_text` lleva la línea `Tipo:`
([`source_text.py:88`](../../../ai-service/src/jbg_ai/indexing/source_text.py)), el hash del
documento sí cambia y **el indexador incremental reembebe exactamente esas filas**. Sin
migración y sin tocar `embedding_version`.

---

## 7. Las siete decisiones, tomadas el 2026-09-05

| # | Decisión | Consecuencia en la HU / el ticket |
|---|---|---|
| 1 | **Cohorte B+: los 22 SKU**, con SKU822 y SKU882 como **grupo de control que no debe moverse** | Criterio de aceptación con tres mitades: 19 ganan o corrigen tipo, SKU845 sigue nulo, 2 no cambian |
| 2 | **`filigrana` queda fuera** | Es gap de `style_tags`, otro eje, y alcanza sus 66 documentos sola por vía léxica. Hay que actualizar su `why` para que no diga que espera a FIX1 |
| 3 | **Los cuatro términos entran en el desplegable** | +4 entradas en `PIECE_TYPE_OPTIONS`, +4 líneas en su test fijado. Coste marginal cero: el fichero ya estaba en el alcance |
| 4 | **Canónico `gemelos`** (plural, como `pendientes`) | La reducción de plurales va singular←plural, así que `gemelo` necesita forma de superficie en el overlay |
| 5 | **`cinturon` sin tilde**, label «Cinturón» | El `value` viaja al filtro duro por igualdad exacta; sigue el precedente de `pequeno` |
| 6 | **Informe propio** `fix1-vocabulary-gaps-measurements.md` | Tabla de las 22 filas antes/después, incluidos los dos de control |
| 7 | **`load_prompt()` deriva la ruta de `PROMPT_VERSION`** | `Path("prompts") / f"{PROMPT_VERSION}.md"` más un test de que el encabezado `# …` del fichero cargado coincide con la constante |

### Por qué la cohorte B+ y no los 11 de la ficha

El «fuera de alcance» de la ficha excluye reenriquecer los 1.200 porque *«podría reclasificar
productos existentes de forma difusa y sin que nadie lo pidiera»*. El motivo es correcto y se
respeta: **los 1.200 siguen fuera**. Pero no aplica a estos nueve, donde la reclasificación es
**enumerada, nominal y auditable** —nueve filas, cada una con el término en el nombre, cada
una hoy en una categoría que demostrablemente no es la suya—. Es lo contrario de difusa.

Y sin ellos el change entrega un desplegable que ofrece «Diadema» y devuelve **5 de 11
diademas**:

| término | en catálogo | cohorte «sólo nulos» | cohorte B+ |
|---|---:|---:|---:|
| diadema | 11 | 5 (**45 %**) | 11 (100 %) |
| gemelos | 4 | 2 (**50 %**) | 4 (100 %) |
| llavero | 3 | 2 (**67 %**) | 3 (100 %) |
| cinturon | 1 | 1 (100 %) | 1 (100 %) |

Un facet al 45 % es precisamente el fallo que el docstring de `materials-vocabulary.test.ts`
declara intolerable —*«"nothing of this in your shop", a sentence that would be false»*— en su
versión peor: no dice cero, dice cinco. Sin error, sin traza y con resultados en pantalla.
**Es la firma de C17 otra vez.** El coste de evitarlo son nueve llamadas al modelo.

### Por qué los dos de Orión entran como control y no se excluyen

Reenriquecerlos convierte el riesgo mayor de `v2` —que `cinturon` en la lista arrastre nombres
propios— de suposición a medición. Si Orión se mueve, el prompt está sobreajustado y se sabe
dentro del change, no seis semanas después cuando alguien filtre por «Broche». Da además un
test de regresión con nombre propio, en el idioma que este repositorio ya usa para `piel`.

---

## 8. Qué queda pendiente de medir

- **El diff completo de los 22**, no sólo `piece_type`: reenriquecer con `v2` puede mover
  `materials`, `stone_type` y los tres juegos de etiquetas. Es el riesgo que la ficha manda
  comprobar y no suponer, y a 22 filas se revisa a mano.
- **Si algún perfil de los 22 tiene `ReviewedByUserId` no nulo** antes de la corrida (§6.7).
- **El efecto sobre `ts_rank`** de añadir la línea `Tipo:` a 19 documentos: 1,6 % del corpus,
  previsiblemente ruido, pero C21 se calibró contra un corpus quieto y conviene decirlo.
- **Si la pareja `Llavero Cape Nao`** formaría familia al reejecutar la sugerencia de C18a
  (§6.6). No se ejecuta en este change.
