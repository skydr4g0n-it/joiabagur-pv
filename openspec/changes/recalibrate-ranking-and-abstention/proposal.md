## Why

C24 entregó el juez imparcial y, al usarlo, dejó al descubierto que **la fusión híbrida de C21 no
fusiona: concatena**. Con la rama léxica sumando 1,00 votos en dos listas y la vectorial 0,33 en
una, un documento léxico en el peor puesto posible (rango 60) puntúa 0,008333 y el mejor
documento que sólo vio la rama vectorial puntúa 0,005410: **los 60 documentos léxicos ganan al #1
vectorial en toda consulta, siempre**. Medido en el run publicado, el grado 2 que la vectorial
pone en el primer puesto cae a la **posición 33** en tres consultas distintas, con los 32
anteriores sólo léxicos y la cola conservando exactamente el orden vectorial. La categoría más
grande del golden set —`descripcion-sin-anclaje`, 12 consultas— saca **0,172** con el híbrido
frente a **0,431** con la rama vectorial sola.

A la vez quedan tres deudas que este change es el primero que puede pagar: la penalización de
disponibilidad que C22 entregó **no se disparó ni una vez** en la evaluación (el golden set corre
sin punto de venta, así que `qty_bucket` llega nulo); la abstención está en **0,000** sobre
fuera-de-dominio contra un objetivo de 0,80; y `sales_30d`, `sales_90d` y `last_sale_at` llevan
persistidos desde C22 con un test que prohíbe leerlos hasta que exista un golden set con el que
calibrarlos.

## What Changes

- **Fusión en dos etapas con pesos por rama.** Las dos listas léxicas se fusionan entre sí y el
  resultado se fusiona con la vectorial, de modo que el voto total de la rama es exactamente
  `w_lex` sin depender de cuántas de sus listas dispararon, y la rama léxica entra con 60
  documentos en vez de con hasta 120. La **fusión plana se conserva como modo seleccionable**
  para que la línea base publicada siga siendo reproducible.
- **Regla adaptativa por cobertura**, sin parámetros: el peso léxico se multiplica por la
  proporción de la consulta que casó su mejor documento. Consume el `coordination` que hoy se
  calcula, viaja en el *hit* y nadie lee.
- **Señal de punto de venta separada del alcance**: un parámetro que lee la proyección por
  `LEFT JOIN` frente al que la restringe por `INNER JOIN`, para medir la reordenación sin pagar
  el coste de recall del prefiltro.
- **`sales_30d` entra en la ruta de recuperación** como desempate declarado y no calibrado.
  **BREAKING (interno):** cae el test guardián `test_the_retrieval_path_cannot_read_the_sales_figures`.
- **Score continuo en el último bloque de la clave de degradación**, conservando lexicográfico lo
  que el operador tecleó.
- **Métrica `nDCG@5 operativo`**, derivada de los juicios existentes sin re-etiquetar, con la
  relevancia pura como guardarraíl. Las dos se publican.
- **Regla de abstención re-fijada**, después de medir la distribución del mejor acierto por
  consulta — la cantidad que decide y que no existe en ningún artefacto.
- **Golden set ampliado**: `fuera-de-dominio` de 5 a 15-20 consultas, partición de ajuste crecida,
  y *pooling* de lo que las configuraciones nuevas promuevan, con juicios apendables.
- **Barrido en dos fases**: con proveedor para la fusión, y re-puntuado en memoria para las
  señales.
- **Tabla de ablations de seis filas**, con una fila que aísla la fusión de las señales, y las
  seis re-corridas bajo una sola tupla de procedencia.
- **Dos puntos de la ficha del plan se retiran, refutados por medición**: la penalización de
  variante ambigua dentro de familia (es presentación, y pertenece a C30/C36) y la calibración de
  `1-2` frente a `3+` (no tiene función objetivo posible).
- **El criterio absoluto de aceptación del diseño §11.2 se sustituye por un criterio relativo** y
  la brecha se declara como limitación del README.

## Capabilities

### New Capabilities

- `business-signals-ranking`: la disponibilidad y la rotación del punto de venta como reordenación
  blanda calibrada contra el golden set — la señal leída sin restringir el conjunto de candidatos,
  los pesos en configuración, la métrica operativa que hace calibrable lo que la relevancia pura
  no puede ver, y el barrido por re-puntuado sobre ventanas persistidas.
- `retrieval-abstention`: la regla que decide **si contestar**, fijada con la distribución del
  mejor acierto por consulta y no con un escalar sobre distancias por documento, más la
  composición del golden set que la hace medible.

### Modified Capabilities

- `hybrid-fusion`: los pesos pasan de ser **por lista** a ser **por rama**, con una etapa de
  fusión interna en la rama léxica; se añade la ponderación adaptativa por cobertura; y la
  profundidad se reparte por rama y no por lista.
- `pos-projection`: los agregados de venta dejan de ser *«read by none of it»*; la disponibilidad
  deja de degradar como bloque binario de una clave lexicográfica y pasa a puntuar de forma
  continua dentro del último bloque — conservando el requisito de que lo tecleado la supera.
- `retrieval-evaluation`: se levanta la prohibición de mover el umbral de distancia, que
  pertenecía a C24; se añade la métrica operativa junto a las lecturas graduada y binaria; y la
  regla de cambio de un valor por defecto cambia de lectura decisoria, porque la partición de
  ajuste está saturada y contaminada.

## Impact

- **`ai-service/` es el único componente con código nuevo.**
  - `src/jbg_ai/retrieval/`: `orchestrator.py`, `search.py`, `lexical.py`, `ports.py`, `filters.py`
  - `src/jbg_ai/config/settings.py`: pesos por rama, valores por defecto de las señales, umbral
  - `src/jbg_ai/evals/`: `metrics.py`, `configs.py`, `sweep.py`, `cli.py`, `report.py`
  - `evals/configs/`, `evals/golden/`, `evals/results/`
  - `tests/retrieval/`, `tests/evals/`
- **Sin migración.** `ai.pos_projection` ya tiene `sales_30d`, `sales_90d`, `last_sale_at` y
  `computed_as_of` por fila.
- **Sin cambio de contrato.** `ai-service/openapi.json` no se mueve: no se añade campo a la
  respuesta de recuperación, y la señal de familia se deja al change que la consuma.
- **Sin diff en `backend/`, `frontend/`, `terraform/` ni `.github/workflows/`.**
- **Rendimiento:** el `p95` de recuperación está en 128,6 ms contra un presupuesto de 500 ms; el
  change añade un `LEFT JOIN` sobre un CTE que ya se materializa y aritmética sobre ≤60
  candidatos.
- **Aguas abajo:** desbloquea **C26** (sustitutos, que se construyen sobre este ranking) y **C27**.
  Deja preparada la retirada de la fusión plana, que es un change posterior de limpieza
  (`clean-plain-fusion`), ejecutable sólo cuando la decisión de fusión esté congelada y publicada.
- **Documentación:** `ai-service/README.md`, `ai-service/tests/README.md`,
  `Documentos/epicas.md`, la ficha C25 y el §0 del plan de changes, y el §11.2 del diseño RAG.
