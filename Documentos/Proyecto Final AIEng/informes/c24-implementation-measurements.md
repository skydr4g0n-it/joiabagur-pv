# C24 — mediciones de la implementación (arnés de evaluación, golden set y líneas base)

**Medido el 2026-09-07** contra el PostgreSQL local (`jpv-pv-postgres`, puerto 5433), sobre los
**1.168 documentos vivos** de `ai.product_document`, y contra el proveedor real de embeddings
(`openai/text-embedding-3-small`). Procedencia de la corrida: golden set `1:1474bfc3aa3a`,
huella del índice `051a6b06021efc3f…`, revisión `a03b4adc0f0c`.

> **A diferencia de la exploración, este informe sí midió.** La exploración del 2026-09-06
> declaró por delante que no había abierto sesión contra la base ni llamado a ningún proveedor,
> y que todas sus cifras estaban citadas de informes anteriores. Todo lo que sigue está medido
> en esta máquina, contra ese índice y contra ese proveedor.

---

## 0. El titular: la decisión 12, por fin con un número

La pregunta que sostiene el proyecto entero —*¿la búsqueda semántica mejora el buscador que la
joyería tenía?*— no tenía ninguna medición. Ahora la tiene, sobre 48 consultas juzgadas a mano
con relevancia graduada:

| Configuración | nDCG@5 | nDCG@5 binario | Recall@5 | P@3 | MRR | coste/consulta |
|---|---:|---:|---:|---:|---:|---:|
| `v0-nombre` — el buscador que había | **0,082** | 0,077 | 0,071 | 0,035 | 0,104 | $0 |
| `v0-fts` — el degradado en español | **0,454** | 0,518 | 0,500 | 0,493 | 0,592 | $0 |
| `v1-vectorial` — sólo la rama vectorial | **0,548** | 0,580 | 0,571 | 0,563 | 0,645 | $0,0000002 |
| `v2-hibrido` — lo que se envía hoy | **0,603** | 0,634 | 0,625 | 0,597 | 0,690 | $0,0000002 |

Leído como el informe de exploración pedía que se leyera, en dos saltos:

```
 subcadena → FTS español      +0,372   gratis, sin IA, veinticinco líneas de to_tsvector
 FTS → híbrido                +0,149   el proveedor, el índice HNSW, la expansión y la fusión
```

**Las dos filas eran necesarias y el argumento de D1 se sostiene con datos**: con una sola no se
podría separar lo que aporta tokenizar en español de lo que aporta la recuperación semántica. Lo
primero es la mayor parte del salto. Lo segundo es un tercio de él, y no es pequeño: `v0-nombre`
responde **cero** en siete de las ocho categorías medibles.

---

## 1. P1, el pleito mayor: el veredicto se invierte

La única medición que existía —la rúbrica «tipo de pieza y material correctos» de C21— daba
**67 de 120** a la rama vectorial contra **107** a la léxica. Con un juez que no es la función
objetivo de una de las partes:

| | rúbrica de C21 | golden set graduado |
|---|---:|---:|
| Rama vectorial sola | 67 / 120 | **nDCG@5 0,548** |
| Rama léxica sola / `v0-fts` | 107 / 120 | nDCG@5 0,454 |

**La rama vectorial no aporta siete puntos de ciento veinte: bate a la línea léxica.** Es el
tercer episodio del mismo patrón en este proyecto y el segundo en tres días —el 2026-09-06 el
corpus de conocimiento invirtió su propio veredicto al cambiar el embebedor sustituto por el
real—, y confirma la sospecha que motivó el change: *un juez con parentesco con una de las partes
le da la razón*.

Dónde se ve el mecanismo, en el desglose por categoría (nDCG@5):

| Configuración | descripción sin anclaje | léxico exacto | materiales | piedra | sinónimos | subjetiva | variante/talla |
|---|---:|---:|---:|---:|---:|---:|---:|
| `v0-nombre` | 0,000 | 0,902 | 0,068 | 0,000 | 0,000 | 0,000 | 0,000 |
| `v0-fts` | 0,035 | 1,000 | 0,938 | 0,918 | 0,241 | 0,357 | 0,827 |
| `v1-vectorial` | **0,431** | 0,500 | 0,682 | 0,785 | 0,729 | 0,502 | 0,817 |
| `v2-hibrido` | 0,172 | 1,000 | 0,968 | 0,747 | 0,984 | 0,665 | 0,830 |

La categoría de descripción sin anclaje es la que el change existe para medir: doce consultas
cuyo mejor documento la rama léxica **no puede alcanzar ni con expansión de sinónimos**. Ahí la
rama léxica saca 0,035 y la vectorial 0,431. Bajo la rúbrica de C21 esa diferencia era invisible
por construcción, porque la rúbrica no tenía diana para esas consultas.

**Y aparece un hallazgo que nadie esperaba, en la misma fila.** El híbrido saca **0,172** donde
la rama vectorial sola saca **0,431**: con `wC=0,33` las dos listas léxicas superan en votos a la
vectorial justo donde la vectorial es la única que sabe la respuesta. La fusión vigente destruye
más de la mitad de la ventaja de su propia rama semántica en el caso que la justifica.

---

## 2. El barrido direccional y la regla de D13

La regla se escribió antes de medir, en `evals/sweep.py`: *se mueve un default si y sólo si el
delta de nDCG@5 supera 0,05, **y** el signo es el mismo en las tres lecturas, **y** ninguna
categoría empeora más de 0,05*. El barrido explora sólo hacia arriba, por el argumento de P2.

| wC | profundidad | nDCG@5 global | sólo ajuste | sólo nuevas |
|---:|---:|---:|---:|---:|
| 0,33 **(vigente)** | 60 | 0,603 | 0,942 | 0,535 |
| 0,5 | 60 | 0,632 | 0,931 | 0,572 |
| 0,75 | 60 | 0,659 | 0,924 | 0,606 |
| **1,0** | 60 | **0,659** | 0,918 | 0,608 |
| 1,5 | 60 | 0,639 | 0,809 | 0,605 |
| 2,0 | 60 | 0,639 | 0,802 | 0,606 |

**Veredicto: NO se mueve el default.** Y merece la pena leer por qué, porque es el caso que la
regla estaba escrita para arbitrar y sale del lado incómodo:

- delta global **+0,057** — supera el margen;
- consultas nuevas **+0,073** — mejora, y es la lectura menos contaminada;
- conjunto de ajuste **−0,024** — **empeora**, y ahí se para la regla.

Las ocho consultas del conjunto de ajuste son exactamente aquellas con las que C21 fijó
`wC=0,33`. Que empeoren al mover el peso no es sorprendente: es la definición de sobreajuste
vista desde dentro. Pero la regla no dice «ignora la lectura contaminada», dice «el signo tiene
que ser el mismo en las tres», y **cambiarla ahora que se conoce el resultado sería exactamente
el ajuste *post hoc* que escribirla antes servía para evitar**. Así que el default no se mueve y
el hallazgo se documenta.

Dos cosas quedan dichas para C25, que sí puede actuar sobre ellas:

- con n=8, una consulta es el 12,5 % de la lectura de ajuste, y −0,024 está muy dentro del ruido
  que un conjunto de este tamaño no resuelve;
- el óptimo medido está en **`wC` entre 0,75 y 1,0**, con una meseta plana entre ambos, y la
  profundidad 40 y 60 se separan por milésimas — el hallazgo de C21 de que la profundidad tiene
  meseta en 40-60 **sí sobrevive** al cambio de juez.

---

## 3. La contaminación del conjunto de ajuste, cuantificada

D4 pedía tres lecturas y advertía que incluir las consultas de C20/C21 sin marcarlas sería medir
sobre el conjunto de ajuste. La cifra es más grande de lo que la advertencia sugería:

| Configuración | global (48) | sólo ajuste (8) | sólo nuevas (40) |
|---|---:|---:|---:|
| `v0-nombre` | 0,082 | 0,042 | 0,090 |
| `v0-fts` | 0,454 | 0,440 | 0,457 |
| `v1-vectorial` | 0,548 | 0,660 | 0,526 |
| `v2-hibrido` | **0,603** | **0,942** | **0,535** |

**El híbrido saca un 0,942 casi perfecto sobre las ocho consultas con las que se calibró y un
0,535 sobre las cuarenta que no vio nunca.** Ese hueco de 0,407 es la medida directa del
sobreajuste, y no aparece en ninguna otra fila: las líneas base, que nadie calibró, se comportan
casi igual en las tres lecturas. Es la comprobación más contundente de por qué las tres lecturas
tenían que publicarse.

**Desviación declarada:** entran **8** de las 24 consultas de C20/C21, no las 24. Once de las
restantes nombran un tipo de pieza o un material que las expulsa de la categoría cuyo pleito
arbitran —una consulta subjetiva que dice `collar` resuelve a un campo del 99 % de cobertura y
deja de aislar la propiedad emergente— y cuatro (`anillo de plata numero 1/2/3` y `anillo de
plata`) son casi duplicadas entre sí. Con n=8, la lectura de ajuste es de baja potencia y se lee
como indicio, no como medición.

---

## 4. Abstención y distribución de distancias: la entrada que C25 necesita

| Configuración | tasa de abstención sobre las 5 consultas fuera de dominio |
|---|---:|
| `v0-nombre` | **1,000** |
| `v0-fts` | 0,000 |
| `v1-vectorial` | 0,000 |
| `v2-hibrido` | 0,000 |

Exactamente lo que D8 predijo: *«el número dirá que `v0-nombre` abstiene al 100 % —no encuentra
nada nunca— y que el híbrido no. Cierto y engañoso.»* La frase que D8 mandaba escribir literal se
escribe: **la abstención medida aquí es un artefacto de la mecánica de ramas, no una decisión de
confianza; el umbral 0,65 deja pasar el corpus entero (C21 §9) y su re-fijación es alcance de
C25.**

Y la respuesta a la pregunta que C24 sí contestaba, sobre 3.926 juicios:

| grado | documentos | mínimo | mediana | máximo |
|---|---:|---:|---:|---:|
| 0 | 2.119 | 0,3268 | 0,5338 | 0,8710 |
| 1 | 852 | 0,2745 | 0,4668 | 0,7465 |
| 2 | 955 | 0,2071 | 0,5167 | 0,8008 |

```
 conocimiento (C23)   [0,2485 … 0,5062] ▏hueco de 8 milésimas▕ [0,5145 … 0,9135]   → hay umbral
 productos   (C24)    relevantes hasta 0,8008 · irrelevantes desde 0,3268           → NO hay
```

**Las dos poblaciones se solapan en casi medio punto de distancia.** No existe ningún escalar que
las separe, así que **queda demostrado que la re-fijación del umbral necesita un cuantil por
consulta y no un valor único** — que es lo que el §9 de C21 hacía esperar y lo que C25 tenía que
saber antes de intentar un barrido. Es un resultado, no una tarea pendiente.

Detalle que conviene no perder: la mediana del grado **1** (0,4668) está por debajo de la del
grado **2** (0,5167). La distancia coseno no ordena por relevancia dentro del corpus juzgado;
ordena por parecido superficial, y la pieza «correcta en la talla equivocada» se parece más al
texto de la consulta que la correcta. Un umbral no puede arreglar eso.

---

## 5. El corpus sintético estorba, y ahora se puede decir cuál de las dos cosas es

`desplazamiento_sintetico@5` — fracción de consultas con respuesta real en las que un producto
sintético irrelevante aparece por delante del primer relevante real:

| Configuración | porción real (41 consultas) | porción sintética (27) |
|---|---:|---:|
| `v0-nombre` | 0,000 | 0,000 |
| `v0-fts` | **0,220** | 0,120 |
| `v1-vectorial` | **0,220** | 0,240 |
| `v2-hibrido` | **0,220** | 0,080 |

**En un 22 % de las consultas con respuesta real, un sintético irrelevante se cuela por delante**,
y la cifra es idéntica en las tres configuraciones que recuperan algo. La hipótesis del §8.1.1 del
diseño queda contestada: el corpus sintético **no es sólo más fácil, también es ruido activo**, y
el ruido no depende de la configuración sino del corpus. Nadie podía separar esas dos cosas antes
de esta métrica.

El desglose por origen, con la recuperación siempre sobre los 1.168 documentos:

| Configuración | origen | n | nDCG@5 | Recall@5 |
|---|---|---:|---:|---:|
| `v0-fts` | real | 41 | 0,384 | 0,400 |
| `v0-fts` | sintético | 27 | 0,250 | 0,281 |
| `v1-vectorial` | real | 41 | 0,439 | 0,389 |
| `v1-vectorial` | sintético | 27 | 0,368 | 0,430 |
| `v2-hibrido` | real | 41 | **0,494** | **0,483** |
| `v2-hibrido` | sintético | 27 | 0,366 | 0,393 |

**La porción real es 41 consultas, no las ~25-30 que la exploración estimó.** La pregunta abierta
4 del ticket queda resuelta por encima de su umbral de 20, así que el criterio de aceptación sobre
la porción real **es concluyente** y no hay que declararlo indeterminado. Lo que sí se declara es
que el criterio no se cumple: `Recall@5 = 0,483` sobre la porción real frente al 0,85 que el
§8.1.1 fija, con un intervalo de ±0,13 que **no** alcanza a cubrir la diferencia.

---

## 6. `v0-cag`: por qué existe la recuperación, medido

Catálogo completo compactado a `sku · nombre · tipo · materiales`, una línea por producto y sin
precio. Modelo `openai/gpt-4o-mini` a temperatura 0, medido el 2026-09-07.

| | valor |
|---|---:|
| Catálogo compactado | **17.583 tokens** para los 1.168 productos |
| Documentos omitidos | **0** (presupuesto 100.000) |
| Coste por consulta | **$0,00267** |
| Recall@5 sobre las 12 consultas sin anclaje | **0,133** |

Curva de escala, lineal porque el contexto lo es —una línea por producto—:

| catálogo | tokens | ¿cabe en 100.000? |
|---:|---:|---|
| 1.168 | 17.583 | sí |
| 2.500 | 37.635 | sí |
| 5.000 | 75.270 | sí, apurado |
| ~6.600 | ~100.000 | **no** |

Y la comparación que da sentido a la columna de coste, sobre **el subconjunto que más favorece a
CAG** —las doce consultas donde tener el catálogo entero delante debería ser una ventaja
decisiva—:

| Configuración | Recall@5 sobre las 12 sin anclaje | coste/consulta |
|---|---:|---:|
| `v0-nombre` | 0,000 | $0 |
| `v0-fts` | 0,083 | $0 |
| **`v0-cag`** | **0,133** | **$0,00267** |
| `v2-hibrido` | 0,283 | $0,0000002 |
| **`v1-vectorial`** | **0,483** | **$0,0000002** |

**CAG con el catálogo entero delante saca menos de un tercio de lo que saca la rama vectorial
sola, y cuesta trece mil veces más.** Respondió literalmente `NINGUNO` en **10 de las 12**
consultas: con 1.168 líneas en el contexto, el modelo no encuentra la pieza que describe una
paráfrasis, aunque la tenga delante. La frase que el marco de decisión de S10 exige queda
respaldada por una medición y no por un argumento:

> RAG cuesta **cuatro órdenes de magnitud menos** que CAG por consulta, acierta **3,6 veces más**
> en el terreno más favorable a CAG, y no tiene techo de catálogo.

*Declarado:* llama a un modelo de lenguaje, así que no es reproducible bit a bit ni a temperatura
0. Es una fila fechada con su modelo, no una configuración que se re-ejecute en cada corrida.

---

## 7. Latencia: dos columnas, y los dos huérfanos de C21 §12 adjudicados

Cifras de la corrida **que quedó versionada**, `d9222333`. Son las únicas de este informe que
se mueven entre ejecuciones —las métricas de relevancia son deterministas y la latencia no—, así
que se leen de la tabla del informe de la corrida y no de una pasada anterior:

| Configuración | p50 recup. | **p95 recup.** | p50 e2e | p95 e2e | p50 rama léxica | primera ejecución |
|---|---:|---:|---:|---:|---:|---:|
| `v0-nombre` | 10,0 | 15,4 | 10,0 | 15,4 | — | 9,9 |
| `v0-fts` | 155,2 | 240,0 | 155,2 | 240,0 | — | 153,0 |
| `v1-vectorial` | 79,3 | 90,6 | 79,4 | 90,8 | — | 80,9 |
| `v2-hibrido` | 104,0 | **128,6** | 104,0 | 128,6 | **19,1** | 105,2 |

96 muestras por configuración (48 consultas × 2 repeticiones en caliente; la primera de cada
consulta se descarta y se reporta aparte).

**El criterio del diseño §11.2 se cumple**: `p95` de recuperación **128,6 ms** contra los 500 ms
acordados, con 371 ms de margen. Leído a una sola columna habría sido un rojo que no es de este
change, que es exactamente lo que D12 anticipó. Una pasada anterior del mismo código daba 136,8 ms
para la misma fila: es la dispersión entre ejecuciones de una medición de tiempo, y es la razón de
que el criterio se lea contra un margen de casi cuatro veces y no contra la tercera cifra decimal.

**Los dos pendientes que C21 §12 dejó sin dueño, adjudicados:**

1. **Latencia real de la rama léxica dentro del orquestador: p50 19,1 ms.** Es el 18 % del tiempo
   del híbrido y se solapa por completo con la espera del proveedor, así que su coste marginal en
   la ruta viva es **cero**. La decisión D10 de C21 —correr la rama léxica contra el proveedor en
   lugar de contra la búsqueda vectorial— queda confirmada.
2. **Efecto del singleton del cliente de embeddings**, medido aparte porque los vectores
   congelados lo eliminan por construcción de la tabla de arriba:

   | | p50 | p95 |
   |---|---:|---:|
   | En frío (fallo de caché, llamada real) | **223,4 ms** | **831,7 ms** |
   | En caliente (acierto de caché del singleton) | **0,0 ms** | **0,0 ms** |

   El singleton no reduce el p95 del proveedor: **lo elimina** en la segunda consulta idéntica.
   La cifra en frío confirma el rango 170-1707 ms que C16 midió, y explica por qué un `p95`
   extremo a extremo con proveedor real rondaría los 900 ms y el criterio de 500 ms no puede
   aplicarse a esa columna.

**Nota de lectura sobre `v0-fts`:** sus 180 ms no son una propiedad del buscador degradado de
.NET, sino de la réplica: recompone `to_tsvector` sobre `name ‖ sku ‖ descripción` en cada
ejecución, sobre las 1.168 filas y sin índice sobre esa expresión, mientras el original consulta
una columna generada con GIN. La fidelidad que se buscaba era **semántica**, no de rendimiento.

---

## 8. El reranking, con su número

| Configuración | consultas con un grado 2 en el top-20 pero fuera del top-5 |
|---|---:|
| `v0-fts` | 4 de 48 (8,3 %) |
| `v1-vectorial` | 1 de 48 (2,1 %) |
| `v2-hibrido` | **1 de 48 (2,1 %)** |

**Un reranker sobre la configuración viva podría arreglar, como máximo, una consulta de
cuarenta y ocho.** A ~250 ms de cross-encoder sobre un presupuesto de 2.500 ms, eso es el 10-15 %
del presupuesto para un techo del 2 % de las consultas. El «no» al reranking deja de ser un
argumento y pasa a ser una división: el protocolo queda ejecutable —añadir un reranker es un
`configs/v2-rerank.yaml` más una corrida— y el número que lo haría decidible, medido.

---

## 9. Lo que se movió respecto a la exploración

| # | Lo que la exploración decidió | Lo que la implementación encontró |
|---|---|---|
| 1 | «436 productos reales de 1.200» | De los **1.168 documentos vivos**, **404** son reales y 764 sintéticos. La cifra de 436 es sobre los 1.200 productos del catálogo, no sobre el índice |
| 2 | `brazalete de cuero` (C20) como consulta de materiales, por el falso amigo `piel`→`cuero` | **No tiene respuesta posible**: el catálogo tiene exactamente **un** artículo de cuero, `SKU1178`, y es un **colgante**. Habría sido una sexta consulta fuera de dominio en la categoría equivocada. Sustituida por `aros de plata`, también de C20 |
| 3 | Porción real estimada en ~25-30 consultas; si baja de 20, criterio no concluyente | Son **41**. El criterio es concluyente, y **no se cumple**: 0,483 frente a 0,85 |
| 4 | *Pooling* estimado en ~1.500-2.000 juicios | **3.926**, porque el criterio admite como grado 1 el fallo de un atributo nombrado y eso puebla las categorías de talla y de piedra más de lo previsto |
| 5 | Las 24 consultas de C20/C21 entran marcadas | Entran **8**. Once quedan fuera por incompatibilidad de categoría y cuatro por ser casi duplicadas; se nombran en el §3 |
| 6 | `Recall@5` clásico | Se publica **acotado** a `min(5, |relevantes|)` además del clásico. Con consultas de 90 documentos relevantes, la lectura clásica tiene techo en 0,055 y mide el tamaño del catálogo, no el recuperador. **Desviación declarada** |
| 7 | El *pool* define lo juzgado | Se añaden **respuestas declaradas por el autor**: documentos que responden a la consulta y que **ninguna** configuración devolvió. Sin ellos, cuatro de las doce consultas sin anclaje habrían tenido cero relevantes y el denominador de recall sólo habría contenido lo que los sistemas ya encuentran. **Desviación declarada** |
| 8 | Precios orientativos | **Verificados** el 2026-09-07 contra `developers.openai.com/api/docs/pricing`: `text-embedding-3-small` $0,02/1M, `gpt-4o-mini` $0,15 y $0,60/1M. Coinciden con los estimados |

**Lo que no se movió:** las trece decisiones se aplicaron tal como se cerraron. El desempate
determinista, los vectores congelados, la tupla de procedencia, la escala 0-2 con lectura binaria
publicada, el desglose por origen sobre el corpus completo, el *pooling* adaptativo, los juicios
apendables, la persistencia opcional y la regla de defaults escrita antes de medir están todos
implementados como se diseñaron.

---

## 10. Estado del contrato, la migración y la suite

- **`openapi.json` byte a byte idéntico.** `GET /v1/evals/runs` deja de ser stub sin tocar ningún
  modelo: sirve desde `ai.eval_run`, ordenado por fecha descendente, y una historia vacía es una
  lista vacía con 200. Bajo perfil de producción la ruta sigue sin montarse.
- **Una revisión de Alembic**, `d7c4e91b25a0`, aditiva: `ai.eval_run`, `ai.eval_case` y
  `ai.eval_result`. `upgrade` y `downgrade` verificados contra la base local; el `downgrade` no
  deja ni tablas ni tipos huérfanos.
- **Suite completa: 903 pasan, 0 fallan.** La línea base medida antes de tocar nada era **799
  pasan, 0 fallan**. Comparado por nombre de test, el conjunto de fallos es el mismo —vacío— y
  las 104 pruebas nuevas son las del arnés, el desempate y el esquema.
- **Juicios apoyados en un texto que ya cambió: 0.** El anclaje por `source_hash` no detecta
  ninguna deriva, que es lo esperado: `FIX1` reenriqueció sus 22 productos antes de etiquetar.

---

## 11. Limitaciones, declaradas

1. **No hay acuerdo entre anotadores.** El diseño prometía doble etiquetado con conciliación entre
   dos personas; el proyecto lo desarrolla una sola, así que esa mitigación **no se aplicó**. Lo
   que la sustituye es el criterio escrito antes de etiquetar, el agrupamiento por categoría y la
   relectura diferida. Los valores absolutos llevan el sesgo de un juicio único; **lo comparable
   entre configuraciones sigue siendo válido, porque el sesgo es el mismo en todas las filas.**
2. **El etiquetador escribió parte del corpus**: los 764 productos sintéticos salieron de C06b.
   Irreducible. Es una de las razones por las que el desglose por origen se publica.
3. **El conjunto es pequeño.** Con 41 consultas en la porción real, el intervalo de confianza del
   criterio de aceptación es de ±0,13: no distingue 0,80 de 0,88, y no distingue las tres
   milésimas que separan `wC=0,75` de `wC=1,0`.
4. **El coste del prefiltro por punto de venta en recall queda sin medir.** El golden set se
   etiqueta sin escopar, decisión tomada en C22 para no mezclar calidad de recuperación con
   cobertura de surtido, y la fila escopada quedó recortada por decisión declarada.
5. **`v0-fts` es fiel en semántica, no en latencia.** Ver el §7.
6. **La medición de `v0-cag` no es reproducible bit a bit.** Ver el §6.

---

## 12. Qué hereda C25

- La **distribución de distancias por grado**, con el resultado de que **no hay hueco**: un umbral
  escalar no puede separar relevantes de irrelevantes en el corpus de productos, y hace falta un
  cuantil por consulta.
- El **óptimo medido del peso de la rama vectorial**, `wC` entre 0,75 y 1,0, con la regla de D13
  bloqueando el cambio por la lectura de ajuste y el detalle de por qué.
- El **golden set con juicios apendables** por `(query_id, product_id)` y `unjudged@5` reportado,
  para que `v3-señales` profundice el *pool* sin re-etiquetar y sepa cuándo su fila no es
  comparable.
- La **tabla de ablations reproducible con un comando**: `uv run evals run --all`.
- El **hallazgo del §1**: la fusión vigente pierde más de la mitad de la ventaja de su rama
  vectorial en las consultas sin anclaje léxico. Es el sitio donde una recalibración tiene más
  que ganar.
