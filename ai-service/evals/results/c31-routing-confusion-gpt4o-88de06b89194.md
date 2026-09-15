# Matriz de confusión del enrutador de intención — 88de06b89194

- `git_sha`: `e3f0403`
- `prompt_version`: `router/v3`
- modelo: `openai/gpt-4o`
- tomada el: 2026-09-14T23:04:22+00:00
- casos: **119**

## Matriz

Filas: clase esperada. Columnas: clase predicha.

| esperada \ predicha | catalog | knowledge | both | ambiguous | not_in_catalogue | out_of_domain | degraded | n | acierto |
|---|---|---|---|---|---|---|---|---|---|
| `catalog` | **17** | 0 | 0 | 0 | 0 | 0 | 31 | 48 | 35% |
| `knowledge` | 0 | **6** | 0 | 0 | 0 | 0 | 26 | 32 | 19% |
| `both` | 0 | 0 | 0 | 0 | 0 | 0 | 10 | 10 | 0% |
| `ambiguous` | 0 | 0 | 0 | **1** | 0 | 0 | 3 | 4 | 25% |
| `not_in_catalogue` | 0 | 0 | 0 | 0 | **6** | 0 | 14 | 20 | 30% |
| `out_of_domain` | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 5 | 0% |

## Las dos cifras, que **no son sumables**

| cifra | valor | mecanismo |
|---|---|---|
| Rechazo del **enrutador** | 5.04% | clasifica **antes** de recuperar |
| Abstención del **retriever** | 10.00% | lee el perfil de distancias **después** de recuperar |

> The two rates are NOT summable and must never be presented as one figure. The retriever's abstention reads the shape of the distance profile AFTER retrieving; the router's refusal classifies BEFORE retrieving. They are measured over different sets by different mechanisms, and the whole reason this change exists is being able to publish them as two numbers.

Procedencia de la abstención: C25, `evals/results/c25-sweep-fase-a.md`; measured over the 43 answerable queries the golden set held before C26 added the five `sustituto` ones.

## El falso positivo sobre la clase contestable, como cifra propia

**0.00%** de las consultas de `catalog` quedaron silenciadas.

> The rate at which a query the shop CAN answer is refused. Reported as a figure of its own because it is the one that decides whether the router is served at all, and because it is not the complement of any accuracy here.

## El veto

Criterio: zero «descripcion-sin-anclaje» queries silenced; a single one rejects the configuration however many impossible ones it catches.
Declarado antes de medir: **True**.

**PASA** — 0 consulta(s) contestable(s) silenciada(s).

## Desglose por categoría del golden set

| categoría | catalog | knowledge | both | ambiguous | not_in_catalogue | out_of_domain | degraded |
|---|---|---|---|---|---|---|---|
| `ambigua` | 0 | 0 | 0 | 1 | 0 | 0 | 3 |
| `descripcion-sin-anclaje` | 10 | 0 | 0 | 0 | 0 | 0 | 2 |
| `fuera-de-dominio` | 0 | 0 | 0 | 0 | 6 | 0 | 14 |
| `lexico-exacto` | 2 | 0 | 0 | 0 | 0 | 0 | 2 |
| `materiales` | 0 | 0 | 0 | 0 | 0 | 0 | 5 |
| `piedra` | 2 | 0 | 0 | 0 | 0 | 0 | 2 |
| `sinonimos` | 1 | 0 | 0 | 0 | 0 | 0 | 5 |
| `subjetiva` | 0 | 0 | 0 | 0 | 0 | 0 | 5 |
| `sustituto` | 0 | 0 | 0 | 0 | 0 | 0 | 5 |
| `variante-talla` | 2 | 0 | 0 | 0 | 0 | 0 | 5 |

## Limitaciones declaradas

1. The ten `both` cases are CONSTRUCTED and derived from the corpus's own `eval_question` markers: they measure whether the router recognises a compound query, not how often an operator writes one.
2. The twenty `not_in_catalogue` queries were CHOSEN to be unsatisfiable, so the precision measured over them is an UPPER BOUND on what a real counter would see.
3. The classifier's prompt was written from `enrichment/vocabularies.yaml` and the corpus README, and NOT from the `note` fields of the golden set nor the `why` fields of this manifest, both of which state the classification rule in words.
