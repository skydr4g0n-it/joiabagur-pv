# C25bis — corrida de verificación tomada DESPUÉS del borrado

Ejecutado el 2026-09-12 contra 1168 documentos vivos de `ai.product_document`, en solo lectura sobre el índice.

| procedencia | valor |
|---|---|
| versión del golden set | `1:198c4af44506` |
| huella del conjunto indexado | `051a6b06021efc3f…` |
| revisión del código | `59f63ef04738+dirty` |
| identificador de la ejecución | `e0a10740-4c61-466c-b86d-56a6df94b1a0` |

Dos ejecuciones cuya procedencia no coincida **no son comparables**, y el arnés lo dice en lugar de compararlas igualmente.

## Tabla de ablations v0 → v3

| configuración | fusión | nDCG@5 | nDCG@5 bin | nDCG@5 oper | Recall@5 | P@3 | MRR | no juzgado@5 | coste/consulta |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `v0-nombre` | `none` | 0.092 | 0.086 | — | 0.079 | 0.039 | 0.116 | 0.000 | $0.0000000 |
| `v0-fts` | `none` | 0.507 | 0.579 | — | 0.558 | 0.550 | 0.661 | 0.000 | $0.0000000 |
| `v1-vectorial` | `none` | 0.612 | 0.648 | — | 0.637 | 0.628 | 0.720 | 0.000 | $0.0000002 |
| `v2b-fusion` | `branch` | 0.740 | 0.770 | — | 0.758 | 0.713 | 0.834 | 0.000 | $0.0000002 |
| `v3-senales` | `branch` | 0.729 | 0.755 | 0.732 | 0.744 | 0.698 | 0.824 | 0.000 | $0.0000002 |

> **La lectura operativa** aplica `g_efectivo = grado` si `qty_bucket ≠ '0'` y `máx(grado − 1, 0)` si es `'0'`, declarada el **2026-09-11 antes de calcular ninguna métrica**. No inventa una constante: reutiliza la escala de `criterion.md`, donde el grado 1 ya es *«sustituto plausible que el operador ofrecería como segunda opción»* y una pieza que no se puede poner sobre el paño es exactamente eso. Una fila con proyección **ausente conserva su grado**, porque la ausencia no es evidencia de stock cero. `judgements.jsonl` no se modifica: es una tercera lectura de la misma anotación, y la relevancia pura es su **guardarraíl** — una configuración que mejore la operativa y degrade la pura más de 0,05 no se adopta. Un guion significa que esa fila no reordena por ninguna señal de negocio, no que puntúe cero.

`Recall@5` se publica con el denominador acotado a min(5, |relevantes|): con consultas que tienen decenas de documentos relevantes, la lectura clásica está limitada por el tamaño del conjunto relevante y mide el catálogo en vez del recuperador. Las dos cifras están en el JSONL por consulta.

Las dos lecturas ordenan las configuraciones **igual**, así que la comparación es robusta a la elección de escala. Ésa es la objeción del apunte de S10 —que el binario es más consistente entre anotaciones— contestada con datos en lugar de con argumento.

## Las tres lecturas de la partición de ajuste

Una decisión de configuración **no se da por confirmada** si no apunta en el mismo sentido en las tres.

**`v0-nombre`** — Buscador anterior (subcadena sobre el nombre + SKU exacto)

| lectura | n | nDCG@5 | nDCG@5 bin | Recall@5 | P@3 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| global | 43 | 0.092 | 0.086 | 0.079 | 0.039 | 0.116 |
| tuning | 8 | 0.042 | 0.042 | 0.025 | 0.042 | 0.125 |
| new | 35 | 0.103 | 0.095 | 0.091 | 0.038 | 0.114 |

**`v0-fts`** — Buscador degradado (FTS español sobre nombre, SKU y descripción)

| lectura | n | nDCG@5 | nDCG@5 bin | Recall@5 | P@3 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| global | 43 | 0.507 | 0.579 | 0.558 | 0.550 | 0.661 |
| tuning | 8 | 0.440 | 0.569 | 0.550 | 0.583 | 0.653 |
| new | 35 | 0.523 | 0.581 | 0.560 | 0.543 | 0.663 |

**`v1-vectorial`** — Rama vectorial sola

| lectura | n | nDCG@5 | nDCG@5 bin | Recall@5 | P@3 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| global | 43 | 0.612 | 0.648 | 0.637 | 0.628 | 0.720 |
| tuning | 8 | 0.660 | 0.715 | 0.725 | 0.708 | 0.754 |
| new | 35 | 0.601 | 0.632 | 0.617 | 0.610 | 0.713 |

**`v2b-fusion`** — Fusión por rama con cobertura adaptativa

| lectura | n | nDCG@5 | nDCG@5 bin | Recall@5 | P@3 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| global | 43 | 0.740 | 0.770 | 0.758 | 0.713 | 0.834 |
| tuning | 8 | 0.936 | 1.000 | 1.000 | 1.000 | 1.000 |
| new | 35 | 0.695 | 0.718 | 0.703 | 0.648 | 0.796 |

**`v3-senales`** — Señal de disponibilidad sobre la fusión por rama

| lectura | n | nDCG@5 | nDCG@5 bin | Recall@5 | P@3 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| global | 43 | 0.729 | 0.755 | 0.744 | 0.698 | 0.824 |
| tuning | 8 | 0.944 | 1.000 | 1.000 | 1.000 | 1.000 |
| new | 35 | 0.680 | 0.699 | 0.686 | 0.629 | 0.783 |

> **Saturación de la partición de ajuste.** `v0-fts` 2/8, `v1-vectorial` 3/8, `v2b-fusion` 6/8, `v3-senales` 6/8 consultas ya están **en el techo** del nDCG@5. Una lectura saturada no puede registrar una mejora: sólo empatar o caer. Por eso `tuning` se publica como **diagnóstico de contaminación** y no veta una decisión — la lectura que decide es `new`, y el lector puede ver aquí cuánto margen tenía la otra.

## Desglose por origen del dato

La recuperación corre **siempre sobre el catálogo completo**. Lo que se agrupa es la consulta, por el origen de sus documentos relevantes, y lo que se cuenta son sólo los relevantes de ese origen. Restringir el corpus a un origen no es una configuración disponible: daría un problema más fácil y una cifra de titular inflada.

| configuración | origen | n | nDCG@5 | Recall@5 | desplazamiento sintético@5 |
|---|---|---:|---:|---:|---:|
| `v0-nombre` | real | 41 | 0.088 | 0.078 | 0.000 |
| `v0-nombre` | synthetic | 27 | 0.013 | 0.007 | 0.000 |
| `v0-fts` | real | 41 | 0.384 | 0.400 | 0.220 |
| `v0-fts` | synthetic | 27 | 0.250 | 0.281 | 0.120 |
| `v1-vectorial` | real | 41 | 0.439 | 0.389 | 0.220 |
| `v1-vectorial` | synthetic | 27 | 0.368 | 0.430 | 0.240 |
| `v2b-fusion` | real | 41 | 0.559 | 0.537 | 0.171 |
| `v2b-fusion` | synthetic | 27 | 0.379 | 0.407 | 0.080 |
| `v3-senales` | real | 41 | 0.569 | 0.551 | 0.171 |
| `v3-senales` | synthetic | 27 | 0.326 | 0.363 | 0.120 |

## Por categoría

| configuración | descripcion-sin-anclaje | fuera-de-dominio | lexico-exacto | materiales | piedra | sinonimos | subjetiva | variante-talla |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `v0-nombre` | 0.000 | 0.000 | 0.902 | 0.068 | 0.000 | 0.000 | 0.000 | 0.000 |
| `v0-fts` | 0.035 | 0.000 | 1.000 | 0.938 | 0.918 | 0.241 | 0.357 | 0.827 |
| `v1-vectorial` | 0.431 | 0.000 | 0.500 | 0.682 | 0.785 | 0.729 | 0.502 | 0.817 |
| `v2b-fusion` | 0.417 | 0.000 | 1.000 | 0.959 | 0.747 | 0.969 | 0.682 | 0.830 |
| `v3-senales` | 0.407 | 0.000 | 1.000 | 0.959 | 0.708 | 0.965 | 0.648 | 0.830 |

## Latencia

Dos columnas siempre. El criterio de aceptación se aplica a `p95 recuperación`, que excluye el ida y vuelta del proveedor de embeddings; `p95 extremo a extremo` se publica junto al presupuesto acordado. Se descarta la primera ejecución de cada consulta y se promedian las repeticiones, para que el percentil no describa un arranque en frío.

| configuración | p50 recup. | p95 recup. | p50 e2e | p95 e2e | p50 léxica | p50 en frío | muestras |
|---|---:|---:|---:|---:|---:|---:|---:|
| `v0-nombre` | 7.0 | 10.0 | 7.0 | 10.0 | — | 7.3 | 126 |
| `v0-fts` | 146.5 | 240.3 | 146.5 | 240.3 | — | 151.4 | 126 |
| `v1-vectorial` | 71.5 | 93.6 | 71.5 | 93.6 | — | 72.6 | 126 |
| `v2b-fusion` | 90.7 | 180.1 | 90.7 | 180.1 | 14.2 | 90.6 | 126 |
| `v3-senales` | 86.8 | 141.2 | 86.8 | 141.2 | 13.4 | 87.5 | 126 |

## Abstención

**La regla vigente es relativa por consulta**, y su forma la eligió una medición bajo un criterio escrito **antes** de tomarla. Un umbral escalar sobre la distancia no puede servir aquí: el mejor acierto de las contestables llega más lejos que el de las imposibles, así que el rango de éstas cae **dentro** del de aquéllas y ningún valor único las separa. La regla cuenta cuántos candidatos caen en una banda alrededor del mejor —lee la **forma** del perfil y no su nivel—, corre **después** de la fusión y **no altera el conjunto de candidatos**, que es lo que mantiene válidas las ventanas persistidas del barrido. La distribución por consulta de la que sale se publica más abajo.

**Qué cuenta exactamente esta columna.** Las dos maneras que tiene una configuración de no contestar con confianza —la regla de abstención y `low_confidence`, que mide desacuerdo entre ramas— terminan en la misma bandera de la respuesta, así que la cifra es su **unión** y no la tasa de la regla sola. Una fila con la regla apagada no marca cero: marca su `low_confidence`. Las dos caras del intercambio de cada regla candidata —cuántas imposibles calla y cuántas contestables silencia— se publican en el informe de implementación de C25, que es donde la regla se fijó.

| configuración | sin respuesta confiada sobre fuera de dominio |
|---|---:|
| `v0-nombre` | 1.000 |
| `v0-fts` | 0.050 |
| `v1-vectorial` | 0.100 |
| `v2b-fusion` | 0.150 |
| `v3-senales` | 0.150 |

## El número que haría decidible el reranking

Consultas cuyo documento de grado máximo está dentro de la ventana que un reranker reordenaría pero fuera de los cinco que se muestran. Es exactamente lo que un cross-encoder podría arreglar, y por tanto el denominador del «no» al reranking: sin esta cifra la decisión se argumenta, con ella se mide. Este change **no** implementa el reranker; deja el protocolo ejecutable y el número.

| configuración | consultas con grado 2 en el top-20 y fuera del top-5 |
|---|---:|
| `v0-nombre` | 0.000 (0 de 43) |
| `v0-fts` | 0.093 (4 de 43) |
| `v1-vectorial` | 0.023 (1 de 43) |
| `v2b-fusion` | 0.047 (2 de 43) |
| `v3-senales` | 0.047 (2 de 43) |

## Distribución de distancias por grado

| grado | documentos | mínimo | mediana | máximo |
|---|---:|---:|---:|---:|
| grade_0 | 2119 | 0.3268 | 0.5338 | 0.8710 |
| grade_1 | 852 | 0.2745 | 0.4669 | 0.7465 |
| grade_2 | 955 | 0.2071 | 0.5167 | 0.8008 |

Máxima distancia de un documento relevante: **0.8008**. Mínima de uno irrelevante: **0.3268**. Hueco: **-0.4739**.

Las dos poblaciones **se solapan**: no existe un valor único que las separe, de modo que un umbral escalar no puede ser la respuesta y hace falta un cuantil por consulta. Eso es un resultado, no una tarea pendiente.

## Distribución del mejor acierto **por consulta**

La distribución de arriba es **por documento** y contesta otra pregunta. Lo que decide la abstención es el **mejor acierto de cada consulta**: un solape total entre las distancias de documentos relevantes e irrelevantes no implica que el mejor acierto de una consulta contestable no pueda separarse del de una imposible. Son preguntas distintas, y la regla sale de ésta.

| población | n | mín | mediana | máx |
|---|---:|---:|---:|---:|
| contestables | 43 | 0.2071 | 0.3983 | 0.7118 |
| fuera de dominio | 20 | 0.4469 | 0.5320 | 0.6271 |

**Ningún valor las separa.** El máximo de las contestables es 0.7118 y el mínimo de las de fuera de dominio 0.4469, de modo que el rango entero de éstas cae **dentro** del de aquéllas (hueco -0.2649). Por eso la regla adoptada es **relativa por consulta** y no un umbral escalar, y por eso corre **después** de la fusión sin alterar el conjunto de candidatos.

## Juicios y coste

- Juicios que se apoyan en un texto que ya cambió desde el etiquetado: **0**.
- Precios: `as_of: 2026-09-07`, fuente `https://developers.openai.com/api/docs/pricing`, **verificados** el día de la corrida.
- Lo no juzgado cuenta grado 0, que es el supuesto estándar del *pooling*. Por eso `no juzgado@5` se publica por configuración: una fila con buena parte de su top-5 sin juzgar es visiblemente no comparable, no silenciosamente injusta.

## Notas

- wall clock 87.2 s
