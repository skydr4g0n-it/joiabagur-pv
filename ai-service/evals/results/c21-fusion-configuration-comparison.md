# C21 — hits at ten by fusion configuration

Measured 2026-09-02 against 1168 live rows of `ai.product_document`, read-only, with `openai/text-embedding-3-small`.

`k` = 60, branch depth = 60 (symmetric across the three lists), distance threshold = 0.65.

**The rubric is the lexical branch's own objective function.** A hit is a top-ten result with the piece type and a material the query named, read off the expansion's resolved terms. `doc_text` carries canonical `Tipo:` and `Materiales:` lines and the expansion aims at them, so a lexical arm scores well here by construction. These figures fix a **starting point, not a verdict**: the judge is C24's graded golden set with a paraphrase category, where the vector branch wins what this rubric cannot see.

Queries marked `recorded` come from the .NET telemetry table; the rest are the curated list C20 used. Both are developer-written, which is the limitation the README declares.

| query | source | expected | vector-only | lexical-only | fused-default |
|---|---|---|---:|---:|---:|
| `gargantilla dorada` | curated | collar | 6/10 | 10/10 | 10/10 |
| `collares de plata` | curated | collar/plata | 10/10 | 10/10 | 10/10 |
| `criollas de oro` | curated | pendientes/oro | 1/10 | 3/10 | 5/10 |
| `sortija de plata` | curated | anillo/plata | 4/10 | 10/10 | 10/10 |
| `aros de plata` | curated | pendientes/plata | 9/10 | 10/10 | 10/10 |
| `brazalete de cuero` | curated | pulsera/cuero | 0/10 | 0/10 | 0/10 |
| `pendiente de oro` | curated | pendientes/oro | 6/10 | 10/10 | 10/10 |
| `bano de oro` | curated | baño de oro | 3/10 | 10/10 | 10/10 |
| `aro de dedo de plata` | curated | anillo/plata | 7/10 | 10/10 | 10/10 |
| `anillo pequeno` | curated | anillo | 10/10 | 10/10 | 10/10 |
| `dije de plata` | curated | colgante/plata | 0/10 | 10/10 | 10/10 |
| `alfiler dorado` | curated | broche | 2/10 | 10/10 | 10/10 |
| `algo dorado para el dia de la madre` | recorded | - | 10/10 | 10/10 | 10/10 |
| `anillo de filigrana tradicional menorquina` | recorded | anillo | 6/10 | 10/10 | 10/10 |
| `anillo de plata` | recorded | anillo/plata | 10/10 | 10/10 | 10/10 |
| `anillo de plata numero 1` | recorded | anillo/plata | 10/10 | 10/10 | 10/10 |
| `anillo de plata numero 2` | recorded | anillo/plata | 10/10 | 10/10 | 10/10 |
| `anillo de plata numero 3` | recorded | anillo/plata | 10/10 | 10/10 | 10/10 |
| `collar elegante para una boda` | recorded | collar | 8/10 | 10/10 | 10/10 |
| `joya con forma de concha marina` | recorded | - | 10/10 | 10/10 | 10/10 |
| `pendientes con motivo de caracola` | recorded | pendientes | 5/10 | 10/10 | 10/10 |
| `pendientes de oro con piedra azul` | recorded | pendientes/oro | 3/10 | 6/10 | 9/10 |
| `pulsera de plata con motivos marinos` | recorded | pulsera/plata | 8/10 | 10/10 | 10/10 |
| `un anillo de plata para regalar` | recorded | anillo/plata | 9/10 | 10/10 | 10/10 |

## Totals

| configuration | hits | of |
|---|---:|---:|
| vector-only | 157 | 240 |
| lexical-only | 219 | 240 |
| fused-default | 224 | 240 |
