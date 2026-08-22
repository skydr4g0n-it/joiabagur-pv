# C06a — Informe de enriquecimiento del catálogo real

Corpus: [`data/catalog/real/generated/catalog-real-enriched.jsonl`](../../../data/catalog/real/generated/catalog-real-enriched.jsonl)
Sidecar: [`catalog-real-enriched.meta.json`](../../../data/catalog/real/generated/catalog-real-enriched.meta.json)
Scripts: [`scripts/catalog/`](../../../scripts/catalog/) · `generator_version`: `c06a-assist/v2` · semilla: `20260822` · `model`: `null`

El JSONL **no** lleva `variant_group_key`, `variant_label` ni `family_seed`. El tercer tier se llama **`original`**: copia la `Description` del xlsx, no la vacía.

## Conteos de agrupación

Heurística **interna** (no serializada): stem de nombre normalizado + sufijo de talla (`xs`/`s`/`m`/`l`/`xl`, mini, adjetivos de talla, `mm`/`cm`). Un sufijo de material (`oro`/`plata`/`dorado`, `plata y oro`) **solo se recorta si va acompañado de talla**, para no fusionar la versión en oro y la versión en plata de la misma pieza. Los conteos viven en el sidecar como traza de pipeline.

| Métrica | Valor | Referencia de exploración |
|---|---|---|
| Productos | 436 | 436 |
| Grupos | **354** | ~403 |
| Multi-variante | **44** | ~23 |
| Unarios | 310 | — |

La diferencia respecto a ~403/~23 no es un umbral de aceptación. El spike no fue patológico (ni un solo grupo, ni 436 unarios con tallas visibles a ojo). Las familias multi-variante son sobre todo S/M/L/XL del mismo motivo (p. ej. colgantes erizo de mar, estrellas de mar).

## Ratios por `text_quality_tier` y `text_provenance`

Medidos **por producto**. Ventana exigida: 70/20/10 ±3 pp.

| `text_quality_tier` | Productos | % | Ventana |
|---|---|---|---|
| `rich` | 293 | **67.20** | 67–73 |
| `sparse` | 94 | **21.56** | 17–23 |
| `original` | 49 | **11.24** | 7–13 |

| `text_provenance` | Productos | % |
|---|---|---|
| `ai_assisted` (`rich` + `sparse`) | 387 | 88.76 |
| `merchant` (`original`) | 49 | 11.24 |

De los 49 `original`, 43 conservan texto del xlsx (p. ej. «plata de ley») y 6 siguen vacíos porque el export ya lo estaba. Ninguno se vació a propósito.

El sorteo parte de `hash(stem interno, seed)` con cortes 0.70 / 0.90. Como el hash opera por **familia** y la puerta es por **producto**, un rebalanceo determinista mueve las familias más pequeñas del cubo sobrante al deficitario hasta entrar en la ventana. Ningún grupo interno mezcla tiers.

## Determinismo (7.3)

Re-ejecutar agrupación + tiers con semilla `20260822` reproduce el mapa SKU → `text_quality_tier` del JSONL commiteado (cero desajustes sobre 436). El test `test_generator_is_deterministic_for_same_seed` (fixture) permanece en verde. Las descripciones no se reescriben salvo `--regenerate-text`.

## Ingesta local

Snapshot previo: `data/catalog/real/products-snapshot-pre-c06a.csv` (gitignored; 436 filas `SKU, Name, Description, Price, CollectionId` de `public."Products"` en `localhost:5433` / `joiabagur_pv`).

**Unmatched:** **0.** Ingesta del JSONL v2 el 2026-08-22 contra `localhost:5433` / `joiabagur_pv`: `updated=436`. Coincidentes tienen la `Description` del JSONL; la ingesta no inserta filas.

## Muestras antes / después

Texto original = columna `Description` del xlsx. Texto asistido = JSONL v2. En `original`, antes y después coinciden con el xlsx.

### SKU01 · `rich` · 48.00 €

**Nombre:** Pendientes botón erizo de mar mini
**Colección:** Colección Biniacolla
**Antes:** plata de ley
**Después:** Los pendientes con botón erizo de mar, en tamaño mini, en plata de ley. El motivo de botón erizo de mar se recorta nítido sobre el lóbulo. Es de plata de ley, con un brillo claro y frío. Se apoyan en el lóbulo y el motivo se lee de frente. Pieza ligera, de uso diario, que no disputa la atención.

### SKU100 · `rich` · 355.00 €

**Nombre:** Pendientes caracola oro
**Colección:** Colección Sa Mesquida
**Antes:** 18kl
**Después:** Pendientes caracola oro, en oro de 18k. El dibujo de caracola ocupa el frente de la pieza. En oro de 18k, el color se mantiene uniforme al girar la pieza. El motivo ocupa el centro de la oreja y se lee de frente. Pieza de peso contenido, con un brillo que se sostiene a la luz del día, y en la oreja el dibujo queda estable.

### SKU115 · `rich` · 55.00 €

**Nombre:** Anillo mini conchiglie
**Colección:** Colección Cala Pregonda
**Antes:** plata de ley
**Después:** El anillo con conchiglie, en tamaño mini, en plata de ley. El motivo de conchiglie queda arriba, con el relieve al cerrar el puño. La plata de ley deja un destello limpio sobre el motivo. Abraza el dedo y el relieve se lee de frente al apoyar la mano. Discreta de cerca y legible de frente; cabe en el día a día.

### SKU130 · `rich` · 48.00 €

**Nombre:** Tobillera
**Colección:** Composturas
**Antes:** plata de ley
**Después:** La tobillera, en plata de ley. La plata de ley deja un destello limpio sobre el motivo. Sigue el tobillo con un trazo ligero. Discreta de cerca y legible de frente; cabe en el día a día. Pertenece a Composturas.

### SKU136 · `rich` · 115.00 €

**Nombre:** Brazalete suspiro
**Colección:** Colección Suspiro
**Antes:** plata de ley
**Después:** Brazalete suspiro, en plata de ley. El dibujo de suspiro es el centro de la silueta. En plata de ley, el metal se ve satinado o pulido según la luz. El arco se abre al pasar la muñeca y el motivo queda al frente. Se ve entera de un vistazo: silueta nítida y metal a la vista.

### SKU06 · `sparse` · 65.00 €

**Nombre:** Colgante erizo de mar S
**Colección:** Colección Biniacolla
**Antes:** plata de ley
**Después:** El colgante con erizo de mar, en talla S, en plata de ley. Cae centrado sobre el pecho y el relieve se lee de cerca.

### SKU105 · `sparse` · 55.00 €

**Nombre:** Pulsera plata caracola
**Colección:** Colección Sa Mesquida
**Antes:** plata de ley
**Después:** Pulsera plata caracola, en plata de ley. Ciñe la muñeca sin rígido; el dibujo se lee al apoyar la mano.

### SKU117 · `sparse` · 48.00 €

**Nombre:** Pendientes mini conchiglie
**Colección:** Colección Cala Pregonda
**Antes:** plata de ley
**Después:** Los pendientes con conchiglie, en tamaño mini, en plata de ley. El motivo ocupa el centro de la oreja y se lee de frente.

### SKU101 · `original` · 72.00 €

**Nombre:** Pendientes caracola largos
**Colección:** Colección Sa Mesquida
**Antes:** plata de ley
**Después:** plata de ley — `text_provenance: merchant`

### SKU120 · `original` · 58.00 €

**Nombre:** Pendientes aro conchiglie
**Colección:** Colección Cala Pregonda
**Antes:** plata de ley
**Después:** plata de ley — `text_provenance: merchant`

## Limitación §15

El catálogo de origen tiene **0 fotos** y 0 embeddings visuales; C06a no ve la pieza. El texto `rich`/`sparse` se redactó **como lo haría un vendedor con la pieza delante**: silueta, cómo sienta o cae, brillo del metal que ya consta. Eso **no** se afirma en las descripciones del JSONL (no se menciona la foto ni la ficha). Lo visual no verificable es **plausible, no certificado**. No se inventan piedras ni accesorios ausentes del nombre o de la `Description` original. La afirmación defendible de este corpus es «catálogo **realista**», no «real tal cual». El ~11 % `original` deja el texto del comerciante (corto, irregular, a veces en blanco) como control para C09: no se reescribe ni se vacía.
