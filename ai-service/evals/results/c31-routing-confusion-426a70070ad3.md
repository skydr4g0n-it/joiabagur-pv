# Matriz de confusión del enrutador de intención — 426a70070ad3

- `git_sha`: `e3f0403`
- `prompt_version`: `router/v1`
- modelo: `openai/gpt-4o-mini`
- tomada el: 2026-09-14T22:55:04+00:00
- casos: **119**

## Matriz

Filas: clase esperada. Columnas: clase predicha.

| esperada \ predicha | catalog | knowledge | both | ambiguous | not_in_catalogue | out_of_domain | degraded | n | acierto |
|---|---|---|---|---|---|---|---|---|---|
| `catalog` | **23** | 0 | 0 | 10 | 4 | 11 | 0 | 48 | 48% |
| `knowledge` | 0 | **21** | 0 | 4 | 0 | 7 | 0 | 32 | 66% |
| `both` | 4 | 0 | **2** | 2 | 0 | 0 | 2 | 10 | 20% |
| `ambiguous` | 0 | 0 | 0 | **3** | 0 | 1 | 0 | 4 | 75% |
| `not_in_catalogue` | 1 | 0 | 0 | 0 | **19** | 0 | 0 | 20 | 95% |
| `out_of_domain` | 0 | 0 | 0 | 0 | 0 | **5** | 0 | 5 | 100% |

## Las dos cifras, que **no son sumables**

| cifra | valor | mecanismo |
|---|---|---|
| Rechazo del **enrutador** | 39.50% | clasifica **antes** de recuperar |
| Abstención del **retriever** | 10.00% | lee el perfil de distancias **después** de recuperar |

> The two rates are NOT summable and must never be presented as one figure. The retriever's abstention reads the shape of the distance profile AFTER retrieving; the router's refusal classifies BEFORE retrieving. They are measured over different sets by different mechanisms, and the whole reason this change exists is being able to publish them as two numbers.

Procedencia de la abstención: C25, `evals/results/c25-sweep-fase-a.md`; measured over the 43 answerable queries the golden set held before C26 added the five `sustituto` ones.

## El falso positivo sobre la clase contestable, como cifra propia

**31.25%** de las consultas de `catalog` quedaron silenciadas.

> The rate at which a query the shop CAN answer is refused. Reported as a figure of its own because it is the one that decides whether the router is served at all, and because it is not the complement of any accuracy here.

## El veto

Criterio: zero «descripcion-sin-anclaje» queries silenced; a single one rejects the configuration however many impossible ones it catches.
Declarado antes de medir: **True**.

**NO PASA** — 15 consulta(s) contestable(s) silenciada(s).

| id | categoría | consulta |
|---|---|---|
| `q02` | `descripcion-sin-anclaje` | la lagartija que toma el sol en las paredes |
| `q03` | `descripcion-sin-anclaje` | el calzado tipico que se lleva en las fiestas de la isla |
| `q05` | `descripcion-sin-anclaje` | una brujula para no perder el rumbo |
| `q06` | `descripcion-sin-anclaje` | la campanita que se cuelga a los bebes para protegerlos |
| `q07` | `descripcion-sin-anclaje` | la raiz retorcida de un arbol viejo |
| `q08` | `descripcion-sin-anclaje` | follaje seco que cae en septiembre |
| `q09` | `descripcion-sin-anclaje` | el fruto de la encina |
| `q10` | `descripcion-sin-anclaje` | una bicicleta antigua |
| `q11` | `descripcion-sin-anclaje` | el bicho con puas que se pisa en las rocas |
| `q12` | `descripcion-sin-anclaje` | un molusco que se agarra a las piedras |
| `q34` | `sinonimos` | bano de oro |
| `q36` | `sinonimos` | dije de plata |
| `q40` | `lexico-exacto` | SKU355 |
| `q41` | `lexico-exacto` | SKU98 |
| `q72` | `sustituto` | se ha acabado el anillo de caracola, que le ofrezco |

## Desglose por categoría del golden set

| categoría | catalog | knowledge | both | ambiguous | not_in_catalogue | out_of_domain | degraded |
|---|---|---|---|---|---|---|---|
| `ambigua` | 0 | 0 | 0 | 3 | 0 | 1 | 0 |
| `descripcion-sin-anclaje` | 0 | 0 | 0 | 2 | 1 | 9 | 0 |
| `fuera-de-dominio` | 1 | 0 | 0 | 0 | 19 | 0 | 0 |
| `lexico-exacto` | 2 | 0 | 0 | 0 | 0 | 2 | 0 |
| `materiales` | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| `piedra` | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| `sinonimos` | 3 | 0 | 0 | 1 | 2 | 0 | 0 |
| `subjetiva` | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| `sustituto` | 2 | 0 | 0 | 2 | 1 | 0 | 0 |
| `variante-talla` | 7 | 0 | 0 | 0 | 0 | 0 | 0 |

## Limitaciones declaradas

1. The ten `both` cases are CONSTRUCTED and derived from the corpus's own `eval_question` markers: they measure whether the router recognises a compound query, not how often an operator writes one.
2. The twenty `not_in_catalogue` queries were CHOSEN to be unsatisfiable, so the precision measured over them is an UPPER BOUND on what a real counter would see.
3. The classifier's prompt was written from `enrichment/vocabularies.yaml` and the corpus README, and NOT from the `note` fields of the golden set nor the `why` fields of this manifest, both of which state the classification rule in words.
