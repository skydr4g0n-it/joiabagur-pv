# C20 — reach of the query expansion dictionary

Measured 2026-09-01 against 1168 live rows of `ai.product_document`, read-only.

The queries are **curated, not sampled**: `public."ProductSearchEvents"` holds 31 rows and 12 distinct texts, all written by the developer in canonical vocabulary, so there is no observed demand to draw on. C24 re-measures this with graded relevance.

Counts are candidate sets, not precision. What the expansion is worth in ranking terms is nDCG@5 on the golden set, which is C24's job and the reason the flag exists.

## Operator queries

| query | without expansion | with expansion | gained | terms resolved |
|---|---:|---:|---:|---:|
| `gargantilla dorada` | 0 | 64 | +64 | 2 |
| `collares de plata` | 0 | 66 | +66 | 2 |
| `criollas de oro` | 1 | 102 | +101 | 2 |
| `sortija de plata` | 3 | 144 | +141 | 2 |
| `aros de plata` | 22 | 205 | +183 | 2 |
| `brazalete de cuero` | 0 | 0 | +0 | 2 |
| `pendiente de oro` | 92 | 102 | +10 | 2 |
| `bano de oro` | 0 | 154 | +154 | 1 |
| `aro de dedo de plata` | 6 | 144 | +138 | 2 |
| `anillo pequeno` | 11 | 15 | +4 | 2 |
| `dije de plata` | 0 | 112 | +112 | 2 |
| `alfiler dorado` | 0 | 34 | +34 | 2 |

## Overlay entries

| field | canonical | overlay form | form alone | with its class | gained |
|---|---|---|---:|---:|---:|
| piece_type | pendientes | `zarcillos` | 0 | 300 | +300 |
| piece_type | pendientes | `arete` | 4 | 300 | +296 |
| piece_type | pendientes | `aretes` | 4 | 300 | +296 |
| piece_type | pendientes | `criolla` | 9 | 300 | +291 |
| color_tags | dorado | `dorada` | 145 | 436 | +291 |
| color_tags | dorado | `dorados` | 145 | 436 | +291 |
| piece_type | pendientes | `aros` | 24 | 300 | +276 |
| piece_type | pendientes | `aro` | 32 | 300 | +268 |
| piece_type | anillo | `aro de dedo` | 6 | 268 | +262 |
| piece_type | colgante | `medalla` | 0 | 195 | +195 |
| piece_type | colgante | `dije` | 1 | 195 | +194 |
| materials | baño de oro | `banado en oro` | 0 | 154 | +154 |
| piece_type | collar | `choker` | 0 | 140 | +140 |
| materials | hilo | `cordon` | 0 | 104 | +104 |
| materials | hilo | `cuerda` | 0 | 104 | +104 |
| piece_type | broche | `prendedor` | 0 | 86 | +86 |
| piece_type | broche | `alfiler` | 2 | 86 | +84 |
| materials | latón | `bronce` | 3 | 80 | +77 |
| piece_type | pendientes | `pendiente` | 275 | 300 | +25 |
| materials | resina | `acrilico` | 0 | 4 | +4 |
| materials | acero | `acero inoxidable` | 1 | 3 | +2 |
| size_label | pequeno | `pequeño` | 134 | 134 | +0 |
