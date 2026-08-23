# C06b — Informe de ampliación sintética del catálogo

Corpus: [`data/catalog/synthetic/generated/catalog-synthetic.jsonl`](../../../data/catalog/synthetic/generated/catalog-synthetic.jsonl)
Sidecar: [`catalog-synthetic.meta.json`](../../../data/catalog/synthetic/generated/catalog-synthetic.meta.json)
CLI: [`ai-service/src/jbg_ai/data/`](../../../ai-service/src/jbg_ai/data/README.md) · `generator_version`: `c06b-synth/v3` · `prompt_version`: `catalog-synth/v3` · semilla: `20260822` · `model`: `openai:gpt-4o` · `generated_at`: `2026-08-22T20:41:16Z`

El JSONL **no** lleva `variant_group_key`, `variant_label`, `family_seed`, `materials` ni `product_id`. El tercer tier se llama **`short`** (nunca `empty` ni `original`). `data_origin` y `text_provenance` son **siempre** `synthetic`.

Ancla real (no se toca): 436 productos en [`catalog-real-enriched.jsonl`](../../../data/catalog/real/generated/catalog-real-enriched.jsonl). Híbrido: **1.200** (436 + 764). Holgura vs objetivo 1.200: **0**.

## Recuentos

| Métrica | Valor |
|---|---|
| Productos sintéticos | **764** |
| SKUs | `SKU440` … `SKU1203` (esquema del real; ninguno coincide con el JSONL C06a) |
| Colecciones de diseño | **10** (entre 8 y 12) |
| Sin colección | **153** (20,03 %) |
| Familias léxicas (stem con 2+ tallas) | 87 grupos, **306** miembros (~40 % del corpus) |
| De esos miembros, familia completa S/M/L/XL | 60,13 % |
| Familia incompleta (2 o 3 tallas) | 39,87 % |

Los cupos de colección son **desiguales** (no se parten a partes iguales). «Hotel», «Aeropuerto», «Turista», «Atelier» y sinónimos de canal **no** aparecen como `collection_name`.

## Colección (nombre de diseño) vs público / POS pensado

El público es metadato de generación (sidecar `collection_audiences`). **No** es `Collection.Name` ni columna en `Product`.

| `collection_name` | Productos | Público / POS pensado |
|---|---|---|
| Fuego | 154 | hotel |
| *(vacío → `CollectionId` NULL)* | 153 | — |
| Cielo estrellado | 126 | atelier clásico |
| Coral negro | 100 | hotel |
| La Pomada | 78 | tienda clásica |
| Filigrana | 58 | atelier clásico |
| Marea viva | 41 | aeropuerto / turista |
| Tramontana | 27 | diseño menorquín |
| El Jaleo | 16 | turista |
| Umbra | 8 | hotel |
| Caliza | 3 | diseño menorquín / marino |

«El Jaleo» es el **jaleo de cavalls de Menorca** (riendas, caballos, plata de montura), no flamenco.

## Ratios por `text_quality_tier`

Medidos **por producto**. Ventana exigida: 70/20/10 ±5 pp.

| `text_quality_tier` | Productos | % | Ventana |
|---|---|---|---|
| `rich` | 504 | **65,97** | 65–75 |
| `sparse` | 173 | **22,64** | 15–25 |
| `short` | 87 | **11,39** | 5–15 |

| `text_provenance` | Productos | % |
|---|---|---|
| `synthetic` | 764 | 100 |

Longitud del copy (caracteres, tras recorte por **frases enteras**):

| Tier | Media | Rango | Vacías |
|---|---|---|---|
| `rich` | 240,5 | 151–501 | 0 |
| `sparse` | 85,1 | 54–138 | 0 |
| `short` | 15,5 | 0–32 | **22** (25,3 % de los `short`) |

Referencia C06a `ai_enriched`: `rich` ~289 / `sparse` ~115 / `original` ~14. El 70/20/10 se **declara** (no se hereda la pobreza del export). Dentro de cada bucket, la longitud se aproxima a esas medias. Si la primera frase no cabe, la descripción queda vacía; no se corta a mitad de oración. Los 22 `short` vacíos son más que el cupo ~20 % porque algunas primeras frases no entraban en 32 caracteres **y** el código vacía además ~20 % de stems `short`.

El código asigna el tier **antes** del draft (un slot / familia, un bucket). Hermanos de talla comparten `description`, `collection_name` y tier; solo cambian el sufijo y el precio (1.00 / 1.15 / 1.30 / 1.50). Ejemplo: `SKU440`–`SKU443` «Collar Lava Ardiente» S/M/L/XL, misma prosa, 780.00 / 897.00 / 1014.00 / 1170.00 €.

## Determinismo (7.3)

El reservador de SKU y el planner de colecciones/familias son deterministas a igual semilla y mismos ocupados (`test_sku_allocator_is_deterministic_for_same_seed`, tests de mix 11.2/11.3). El **texto no lo es**: temperatura > 0; el JSONL escrito el 2026-08-22 es la fuente. Sin `--regenerate-text` no se pisa. «Mismas descripciones a igual semilla» **no aplica**.

## Ingesta local

Snapshot previo (gitignored, no se commitea):

- `data/catalog/synthetic/products-snapshot-pre-c06b.csv` — 436 filas `SKU, Name, Description, Price, CollectionId`
- `data/catalog/synthetic/collections-snapshot-pre-c06b.csv` — 28 filas `Id, Name`

**Ingesta** el 2026-08-22 contra `localhost:5433` / `joiabagur_pv`: `collections=10` `products=764`. Recuentos posteriores: `"Products"` **1200**, `"Collections"` **38**, `"ProductFamilies"` **0**, `"ProductFamilyMembers"` **0**. Los 764 sintéticos tienen `IsActive=true`; 153 tienen `CollectionId` NULL. El validador de ingest aborta si muta una fila real o escribe familia; no abortó. El JSONL **no** ganó `product_id`.

**GET familia (9.3).** `GET /api/products/{id}/family` autenticado sobre `SKU440` (`f4eb90e4-5b83-4a7c-8a73-3f023d57fb6e`) → **204**. El mismo endpoint sobre un Guid inexistente → **404**. No se implementa C18.

## Muestras por tier

Texto = campo `description` del JSONL v3. Ninguna sigue el molde C06a «El anillo con X, en talla Y, en plata de ley…».

### SKU440 · `rich` · 780.00 € · Fuego

**Nombre:** Collar Lava Ardiente S
**Público pensado (no es el nombre):** hotel
**Descripción:** El collar Lava Ardiente evoca la belleza y el misterio de la lava en erupción. Con un impresionante colgante de ámbar incandescente rodeado de hilos de oro rojo, captura la esencia del fuego en su estado más salvaje. Las cadenas de plata añaden un contraste frío que realza su intensidad.

### SKU1173 · `rich` · 150.00 € · El Jaleo

**Nombre:** Pendientes Riendas de Plata
**Público pensado:** turista
**Descripción:** Estos exquisitos pendientes capturan la esencia de las riendas de los caballos menorquines, creando un delicado juego de curvas en plata pulida. Cada hebra de metal recuerda el arte ecuestre en movimiento, convirtiéndolos en una celebración de la tradición y la elegancia.

### SKU1201 · `rich` · 240.00 € · Caliza

**Nombre:** Collar Cala Salina
**Público pensado:** diseño menorquín / marino
**Descripción:** Este collar evoca la pureza de las calas menorquinas con su piedra caliza blanca central, rodeada de diminutas perlas que recuerdan al suave salitre del mar. La cadena de plata envejecida, diseñada para reflejar la textura de las arenas de la isla, envuelve el cuello con elegancia. Una pieza que captura la esencia del verano mediterráneo, perfecta para quienes buscan llevar un pedazo del mar siempre consigo.

### SKU631 · `sparse` · 320.00 € · Fuego

**Nombre:** Anillo Llama Eterna v2 S
**Descripción:** Un anillo que captura el resplandor del fuego, con ámbar ardiente y metal brillante.

### SKU635 · `sparse` · 450.00 € · Fuego

**Nombre:** Collar Lava Fluyente S
**Descripción:** Este collar emula el flujo de la lava, combinando oro rojo y ónix.

### SKU693 · `sparse` · 120.00 € · *(sin colección)*

**Nombre:** Colgante Esfera de Luna S
**Descripción:** Un delicado colgante que captura la esencia etérea de la luna llena, elaborado en plata pulida.

### SKU673 · `short` · 89.00 € · *(sin colección)*

**Nombre:** Collar Brisa Lunar S
**Descripción:** Collar de plata y perla.

Hermanos M/L/XL (`SKU674`–`SKU676`): misma descripción; precios 102.00 / 116.00 / 134.00.

### SKU726 · `short` · 150.00 € · Fuego

**Nombre:** Anillo Lava Viva v2 S
**Descripción:** Intenso como el magma.

### SKU692 · `short` · 165.00 € · *(sin colección)* · descripción vacía

**Nombre:** Gargantilla Horizonte Marfil
**Descripción:** *(vacía)*

### SKU832–SKU835 · `short` · Cielo estrellado · descripción vacía (familia completa)

**Nombres:** Anillo Orión S / M / L / XL · 120.00 / 138.00 / 156.00 / 180.00 €
**Descripción:** *(vacía en las cuatro tallas)*

## Limitación §15

Este corpus **lo escribe un LLM**. No es un clon estadístico del export C06a: SKUs, colecciones y copy no reutilizan el ancla real. Las piezas no existen; materiales y precios son **razonados, no verificados**. No hay fotos ni embeddings visuales (igual que C06a).

C24 debe **desglosar métricas por `data_origin`**. El número que va al README como resultado principal sigue siendo el de la porción **`real`**. El umbral de aceptación no se mide sobre estos 764. Sin este change, el corpus se queda en los 436 y el README declara que no hubo ampliación.

La afirmación defendible del híbrido es «catálogo **realista** de ~1.200», no «catálogo real de 1.200». El texto `rich`/`sparse`/`short` es voz de escaparate inventada, no ficha de comerciante.
