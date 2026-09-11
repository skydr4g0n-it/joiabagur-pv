# C24 — decisiones de la exploración (arnés de evaluación, golden set y líneas base)

**Explorado el 2026-09-06**, sobre `ai-eng` limpia tras el merge de C23 (PR #29) y su recalibración
posterior (`5ec4b95`), con `openspec list` devolviendo **cero changes activos**. Este informe es la
entrada de `/enrich-us`: recoge los pleitos que el golden set tiene que dirimir, las trece
decisiones de arquitectura cerradas con el desarrollador y la composición del golden set, categoría
a categoría.

> **Limitación del método, declarada por delante.** Esta exploración **no midió nada**. No se
> abrió sesión contra PostgreSQL, no se llamó al proveedor de embeddings ni a ningún LLM. Todas
> las cifras que aparecen aquí están **citadas de informes anteriores** —C20, C21, C22, C23 y
> `FIX1`— o **leídas del código**. Es una diferencia de fondo con las exploraciones de C21 y C22,
> que sí midieron, y se declara en lugar de disimularse: lo que este informe aporta no son
> números nuevos, sino la **lectura conjunta** de los que ya existen y las decisiones que se
> derivan de ellos.
>
> Consecuencia operativa: la primera tarea del change es **verificar el entorno** (§10) y, si
> alguna de las tres precondiciones falla, **parar y configurarlo** antes de tocar código. Sin
> base y sin clave no hay *pool*, y sin *pool* no hay golden set.

---

## 1. Punto de partida verificado en el repositorio

| Hecho | Dónde | Consecuencia para C24 |
|---|---|---|
| Los **nueve knobs de recuperación son parámetros de la firma**, no sólo settings, y el docstring dice literalmente *«C24 sweeps configurations inside one process»* | [`retrieval/orchestrator.py`](../../../ai-service/src/jbg_ai/retrieval/orchestrator.py) | **El barrido de configuraciones ya está construido.** C24 no toca la firma ni el `openapi.json` congelado |
| `ai.eval_run`, `ai.eval_case` y `ai.eval_result` **no existen**: la migración fundacional no los crea | [`f46c55c056e2`](../../../ai-service/migrations/versions/f46c55c056e2_ai_schema_foundation.py) | **C24 abre una revisión de Alembic.** Es la única migración del change |
| `GET /v1/evals/runs` **está publicado en el `openapi.json` congelado** y su stub nombra a C24 por escrito como quien lo entregará | [`api/routers/evals.py`](../../../ai-service/src/jbg_ai/api/routers/evals.py) | Cerrar C24 sin las tablas convertiría esa nota en una mentira. Decide D10 |
| `data_origin` es columna `NOT NULL` de `ai.product_document` | migración fundacional | El desglose real/sintético no necesita infraestructura nueva |
| Patrón «CLI de medición → informe versionado en `evals/results/`», ejecutado dos veces | [`c20-…md`](../../../ai-service/evals/results/c20-query-expansion-reach.md), [`c21-…md`](../../../ai-service/evals/results/c21-fusion-configuration-comparison.md) | El sitio y la forma del informe están fijados; C24 escribe al lado |
| Patrón «fixture + Recall + MRR + abstención + comparación de arms» | [`knowledge/measure.py`](../../../ai-service/src/jbg_ai/knowledge/measure.py) | La forma del `Report` se hereda; no se inventa |
| `indexing/set_hash.py` calcula huella estable de un conjunto, con el orden **sin signo** que C17 descubrió por las malas | [`set_hash.py`](../../../ai-service/src/jbg_ai/indexing/set_hash.py) | Es el `index_set_hash` de la tupla de procedencia (D2) |
| El corpus: **1.200 productos** (436 reales + 764 sintéticos), **1.168 filas vivas** indexadas | informes C06b y C21 | Denominador de todas las cifras del informe |
| El cliente de embeddings de recuperación **ya es singleton** con caché acotada | `api/main.py`, desde C21 | La condición que bloqueaba la hipótesis del §0 del plan —embeber también la forma canónica— **se cumplió** y nadie la ha vuelto a mirar (P4) |
| **El 2026-09-06, después de archivar C23, el umbral de conocimiento se recalibró contra el índice real: 0,81 → 0,51.** El 0,81 salido del sustituto offline **citaba 4 de las 5 preguntas fuera de dominio** | [c23-implementation-measurements §8](c23-implementation-measurements.md) | **Precedente decisivo para D2 y P1.** Un juez sustituto no dio un número impreciso: dio un mecanismo inoperante, y **revirtió el veredicto sobre la rama léxica** |

---

## 2. Los ocho pleitos que el golden set tiene que dirimir

C24 no es «medir». Es **arbitrar pleitos que hoy están decididos por argumento y no por número**.
Cada uno tiene una cifra medida, un juez recusado y una consecuencia si no se dirime.

```
                        medido      juez usado          juez recusado porque…
 P1 vector vs léxica    67 vs 107   rúbrica tipo+mat.   es la función objetivo de la léxica
 P2 peso wC=0,33        36 configs  la misma rúbrica    idem — y el óptimo está en meseta
 P3 coordinación        111→114     la misma rúbrica    «es un collar» ≠ «sirve para boda»
 P4 expansión C20       +alcance    recuento candidatos alcance ≠ ranking
 P5 umbral 0,65         1168/1168   ninguno             nunca se midió abstención real
 P6 prefiltro POS       llenado     tasa de llenado     llenar ≠ llenar bien
 P7 decisión 12         —           NINGUNO             nunca se ha medido
 P8 reranking           —           NINGUNO             se argumentó, no se midió
```

### P1 · ¿La rama vectorial vale lo que cuesta? — el pleito mayor

Medido en el [informe de exploración de C21 §6](c21-hybrid-exploration-measurements.md), 12
consultas, aciertos en el top-10:

| Configuración | aciertos / 120 |
|---|---:|
| Vectorial sola | **67** |
| Léxica sola | **107** |
| Fusión `wC=1,0` (paridad) | 96 |
| Fusión `wC=0,33`, profundidad 60 | 111 |
| Fusión `wC=0,33`, profundidad 40-50 | **113-114** |

La rama vectorial —el proveedor externo, los 170-1707 ms, la clave de OpenAI, el índice HNSW y la
mitad de la arquitectura— **aporta 7 puntos de 120** según la única medición que existe.

El juez está recusado por el propio informe que lo usó:

> *«La rúbrica es la función objetivo de la propia rama léxica. `doc_text` lleva líneas canónicas
> `Tipo:` y `Materiales:`, y la expansión apunta justo ahí; medir "tipo correcto y material
> correcto" premia por construcción a quien casa esas líneas.»*

Y da el contraejemplo exacto: en `joya con forma de concha marina` la rama léxica entierra en
B23/B24 los *Colgante Caracola Marina* y *Pendientes caracola Marina* que la vectorial pone en
C1/C2, y la fusión los sube al top-5 — *«la rúbrica no tiene diana para esa consulta, así que ese
acierto no aparece en la tabla»*.

El mecanismo está en el §2 de ese mismo informe: en el corpus, **`concha` casa 0 documentos,
`madre` 0, `bonito` 0, `algo` 0**. Las consultas donde la rama vectorial es la única que puede
responder son, por construcción, invisibles para una rúbrica léxica.

**Requisito que impone al golden set:** ≥12 consultas con al menos un documento de grado 2 cuyo
`doc_text` **no contenga ningún término de la consulta tras expansión**. Sin esa garantía
explícita, el golden set saldrá dominado por consultas del tipo `<tipo> de <material>` —que es
como piensa quien conoce el vocabulario del catálogo— y **confirmará C21 por construcción**.

**Si no se dirime:** el PF entrega una arquitectura RAG cuya pieza central nunca se demostró
necesaria, con una tabla que sugiere que veinticinco líneas de `to_tsvector` habrían bastado. Y no
porque el número sea malo: porque no se sabrá si lo es.

> **Y el pleito ya tiene precedente, medido en otro corpus el 2026-09-06.** En el corpus de
> conocimiento, C23 midió con un embebedor sustituto que *«la rama léxica gana +6,2 pp de
> Recall@3»*. Al re-medir contra el proveedor real, el veredicto **se dio la vuelta**: el recall es
> **93,8 % en las dos configuraciones** y la rama léxica ya no gana recuperación, sólo orden
> (MRR 0,891 frente a 0,854). El informe lo escribe sin rodeos: *«el +6,2 pp del §1 era un efecto
> del sustituto léxico, no una propiedad del sistema»*.
>
> Es exactamente la forma de P1 —un juez con parentesco con una de las partes le dio la razón— y ya
> no es una hipótesis mía: es lo que pasó hace unas horas en el otro índice de este mismo sistema.
> Refuerza dos decisiones: **D2** (nada de sustitutos: se mide contra el proveedor real) y la
> propia existencia de C24.

### P2 · El peso `wC = 0,33` y la profundidad 40-60

Barrido de 36 configuraciones (§6 y §10 del informe C21). `wC=0,33` gana **en todas** las
profundidades; la profundidad tiene meseta en 40-60 y decae monótonamente a partir de 100.

| Hallazgo | ¿Sobrevive a un juez imparcial? |
|---|---|
| `profundidad ≈ k` (no son parámetros independientes) | **Sí.** Es aritmética de RRF, no depende de la rúbrica |
| `wC=1,0` es la peor fusión | **Probablemente sí**: la causa es que el vector devuelve 60 candidatos siempre (§9 de C21), no la rúbrica |
| `wC=0,33` es **el óptimo** | **No necesariamente.** Con relevancia graduada y consultas sin anclaje léxico, el óptimo puede subir |

Nótese la asimetría: la rúbrica sesgada **infravalora** al vector por construcción, así que el
óptimo verdadero está en `wC ≥ 0,33`, nunca por debajo. El barrido de C24 es **direccional**: sólo
hay que explorar hacia arriba.

### P3 · La regla de coordinación y los campos escasos

Cobertura por línea de `doc_text` (§2 del informe C21), que es lo que decide qué puede filtrar:

| Línea | Documentos | % | ¿Cuenta para coordinación? |
|---|---:|---:|---|
| `Tipo:` | 1.157 | 99 % | **Sí** |
| `Descripción:` | 1.143 | 98 % | literal, cuenta |
| `Materiales:` | 1.042 | 89 % | **Sí** |
| **`Piedra:`** | **630** | **54 %** | **SIN DECIDIR** |
| `Talla:` | 529 | 45 % | no |
| `Colores:` | 224 | 19 % | no |
| `Ocasiones:` | 150 | 13 % | no |
| `Estilo:` | 133 | 11 % | no |

La regla adoptada por C21 —*un grupo cuenta si y sólo si la ausencia de su término es evidencia*—
ganó 111 → 114/120 sin una sola pérdida. Pero el informe declara dos honestidades:

> *«La rúbrica no puede juzgar lo que la pregunta plantea. "Es un collar" es lo que se puntúa;
> "sirve para una boda" no.»*
>
> *«Si `stone_type` (54 %) debe contar para la coordinación o no: está en la frontera entre el
> bloque alto (89-99 %) y el escaso (11-19 %), y **ninguna de las doce consultas lo aísla**.»*

**Dos requisitos directos sobre el golden set**, ninguno de los cuales está en la ficha:

1. **Categoría subjetiva** (ocasión / estilo / regalo). Con `boda` casando 5 documentos y `regalo`
   7 de 1.168, es la única forma de comprobar si la propiedad emergente que C21 reivindica
   —*«cuando la consulta es mayoritariamente subjetiva, la rama vectorial decide por defecto»*— es
   real o es un deseo.
2. **Consultas que aíslan la piedra.** Cifras re-medidas contra `ai.product_document` en el
   [informe de implementación de C23 §5](c23-implementation-measurements.md): `ónix` **124**,
   `coral` **23**, `perla` **34 en texto pero 0 en `materials`** — el extractor la clasifica sólo
   como piedra. Esa última es una trampa útil: `anillo de perla` mide si el sistema encuentra por
   `stone_type` lo que no está en `materials`. **Cuatro consultas cierran una pregunta que C21
   dejó explícitamente abierta en su §12.**

### P4 · La expansión de sinónimos: alcance medido, ranking no

El [informe C20](../../../ai-service/evals/results/c20-query-expansion-reach.md) mide candidatos,
no precisión, y se autolimita por escrito: *«what the expansion is worth in ranking terms is
nDCG@5 on the golden set, which is C24's job and the reason the flag exists»*. `gargantilla
dorada` 0 → 64, `dije de plata` 0 → 112, `sortija de plata` 3 → 144.

Pasar de 0 a 112 candidatos es **necesario** —sin ello la rama léxica no devuelve nada— pero no
dice si los 112 están bien ordenados.

Los tres tipos de entrada del diccionario **no son intercambiables** y el golden set debe cubrir
los tres:

```
 artefacto del stemmer   collares → collar      (1 documento vs 140)
 sinónimo comercial      dije → colgante        (1 vs 195)
 puente direccional      dorado → baño de oro   asimétrico: el sentido inverso
                                                arrastra 282 piezas de oro macizo
```

**Y una hipótesis abierta que hay que cerrar aquí.** El §0 del plan (entrada del 2026-09-01) dejó
escrito: *«una configuración que **embeba también la forma canónica** y fusione por RRF es
defendible en cuanto el cliente sea singleton»*. El cliente **es singleton desde C21**. La
condición se cumplió y nadie la ha vuelto a mirar: entra como cuarto arm de la ablación de
sinónimos, a coste de un embedding adicional por consulta.

### P5 · El umbral 0,65 y la abstención

Medido en el §9 del informe C21 — documentos que pasan `distancia ≤ 0,65`:

| Consulta | pasan de 1.168 | umbral que dejaría 60 |
|---|---:|---:|
| `sortija de plata` | **1.168** | 0,447 |
| `gargantilla dorada` | **1.168** | 0,445 |
| `collar elegante para una boda` | 1.090 | 0,493 |
| `bano de oro` | 268 | 0,594 |
| `xyzzy quimbombo alfanumerico` | **0** | 0,778 |

Tres lecturas, todas relevantes para el golden set: el umbral **no filtra** (lo que corta es el
`LIMIT`); el vector **sí abstiene, pero sólo ante texto sin sentido**; y un umbral que cortara de
verdad **sería un cuantil por consulta, no un escalar**.

**Consecuencia directa sobre la categoría *Fuera de dominio*.** Si esas consultas se escriben como
texto sin sentido, **todas las configuraciones abstienen al 100 %** y la métrica no discrimina
nada. Sólo informan si son **plausibles pero imposibles**:

```
 ✗ inútil   «xyzzy quimbombo alfanumerico»          todos abstienen: 0 información
 ✓ útil     «reloj sumergible de titanio»           joyería, pero no se vende
 ✓ útil     «pendientes talla XXL»                  XXL medido: 0 documentos (C23 §5)
 ✓ útil     «collar de madera de olivo»             material fuera del vocabulario cerrado
 ✓ útil     «anillo de compromiso con diamante      plausible, fuera de banda de precio
             de dos quilates»
```

Es la diferencia entre una métrica de seguridad —el *suelo* del que habla S16— y un test que se
aprueba solo.

### P6 · El prefiltro por punto de venta: llenar no es llenar bien

El [informe de implementación de C22 §4](c22-implementation-measurements.md) mide tasa de llenado
y se autocritica:

> *«El 60 no es una medida de calidad: es la profundidad de rama […]. El change garantiza que la
> página se llena, **no que se llene bien**. Ordenar bien dentro del surtido es la pregunta que
> C24 mide con el golden set, y el golden set está etiquetado **sin escopar** precisamente para no
> mezclar calidad de recuperación con cobertura de surtido.»*

Esa decisión es correcta y deja un hueco declarado: **la tabla de ablations describe una
configuración que en producción nadie ejecuta** (`JPV_POS_PREFILTER_ENABLED=true` por defecto).
Surtidos medidos: de 241 (FORNELLS) a 1.082 (MAO-TALLER); **HT-ARTRUTX tiene surtido 0 y devuelve
503**, así que cualquier medición escopada tiene que excluirlo explícitamente.

### P7 · La decisión 12: ¿la búsqueda semántica bate a la que había?

**Cero mediciones.** Es la fila que sostiene la afirmación del proyecto entero y la única del
§11.2 del diseño con anotación explícita: *«es la comparación "búsqueda actual vs semántica" que
pide la decisión 12»*.

Lo que sí se sabe por lectura de código:
[`ProductService.cs:342`](../../../backend/src/JoiabagurPV.Application/Services/ProductService.cs)
hace `p.Name.Contains(normalizedQuery)` — subcadena de **la consulta completa**, sin tokenizar.
Predicción falsable, escrita antes de medir para que la medición pueda desmentirla:

```
 «gargantilla dorada»               → 0     ningún nombre contiene esa subcadena
 «un anillo de plata para regalar»  → 0
 «SKU0442»                          → 1     SKU exacto: su único punto fuerte
 «anillo»                           → 268   subcadena suelta, orden alfabético
```

Recall@5 esperado sobre las siete categorías medibles: **~0,05-0,10**, concentrado casi todo en
*Léxico exacto*.

### P8 · El reranking, que no se implementa pero sí se protocoliza

El diseño §11.2 lo descarta y §15.5 lo declara como limitación: *«no se ha medido, sólo argumentado
y protocolizado»*. Lo que C24 resuelve aquí es que **el protocolo sea ejecutable y no retórico**:
añadir un reranker debe ser `configs/v2-rerank.yaml` más un run.

Y deja medido gratis el número que haría defendible el «no»: **cuántas consultas tienen su
documento de grado 2 dentro del top-20 pero fuera del top-5** — que es exactamente lo que un
reranker podría arreglar. Con el proveedor de embeddings en 170-1707 ms y el presupuesto de C16 en
2.500 ms, un cross-encoder de ~250 ms sería el 10-15 % del presupuesto, no un factor 8; el
denominador correcto lo fija el marco de decisión de S10.

---

## 3. Hallazgos de código que no son mediciones

### 3.1 Ninguna de las dos sentencias de recuperación tiene desempate determinista

```sql
-- retrieval/search.py:99    ORDER BY d.embedding <=> CAST(:q AS vector) ASC
-- retrieval/search.py:124   ORDER BY coordination DESC, ts_rank DESC
```

Sin tercera clave y con `LIMIT 60`, **qué filas sobreviven al corte cuando hay empate no está
definido en PostgreSQL**. En la rama léxica los empates son masivos: `coordination` toma tres
valores y `ts_rank` se repite entre documentos con el mismo patrón de campos. Dos ejecuciones
idénticas pueden dar listas distintas, y el efecto entra directo en nDCG@5.

**Sin esto, `test_run_is_reproducible_for_same_config_and_seed` es un test que miente, y el arnés
deja de servir para detectar regresiones — que es el uso que S16 llama el valioso.** Se corrige
dentro de C24 (D2), como desviación declarada.

### 3.2 El precio se lee pero **nunca se emite**

```python
# retrieval/ports.py, SearchHit.price
#: Carried for the demoting filters of C21 and **never** emitted: the boundary
#: rule is that .NET owns price.
```

`price` es columna de `ai.product_document` y la usan los filtros de degradación, pero
`RetrievalResult` no la lleva. **Meter precios en un prompt sería la primera vez que un precio
cruza desde `ai` hacia una superficie generativa**, justo lo que el validador anti-alucinación de
C38 existe para vigilar. Decide la forma del contexto de CAG (D6).

### 3.3 CAG no existe en ninguna parte del sistema

Búsqueda exhaustiva de «CAG» en repositorio y documentación:

```
 diseño §11.2          | v0-cag | Catálogo del POS entero en contexto, sin retrieval |
 diseño §16            README con … CAG/RAG/agente/evaluación/despliegue
 plan, ficha C24       configs `v0-lexico` … y `v0-cag`
 plan, ficha C39       README del PF (… CAG/RAG/agentes/evaluación/despliegue …)

 ai-service/README.md  →  CERO menciones
 código                →  CERO líneas
```

El enunciado del PF pide *«escala desde un prototipo CAG hasta un sistema RAG»* y que el README
describa *«CAG/RAG»* como componentes. **`v0-cag` es el único artefacto que puede hacer que esa
sección hable de algo medido en vez de explicar qué es CAG en general.** Decide D6.

### 3.4 `doc_text` es un superconjunto de lo que ve el buscador .NET

`build_source_text` renderiza `SKU · Nombre · Descripción · Colección · Tipo · Materiales · Piedra
· Talla · Familia · Variante · Colores · Estilo · Ocasiones`. El buscador degradado de .NET indexa
`Name + SKU + Description`. **Un FTS sobre `doc_text` no es una réplica: es una cota superior.** Y
`ai.product_document` no tiene columna `description`. Decide D1.

### 3.5 C21 dejó dos mediciones pendientes que nadie adjudicó

Su §12 lista, entre lo que queda por medir: *«latencia real de la rama léxica dentro del
orquestador»* y *«efecto del singleton del cliente de embeddings sobre el p95, en frío y en
caliente»*. **Las dos caen de este arnés gratis** y entran en el alcance de C24 explícitamente —
si no, se quedan sin dueño para siempre.

---

## 4. Las trece decisiones, cerradas

### D1 · `v0-lexico` son **dos filas**, no una

Hay dos «buscadores actuales» en el repositorio y no son el mismo:

| | Dónde | Qué hace |
|---|---|---|
| **A. El de siempre** | `ProductService.SearchProductsAsync` | `Name.Contains(consulta)` + SKU exacto, orden alfabético |
| **B. El degradado** | `AssistedSearchRepository.SearchLexicalAsync` | `to_tsvector('spanish', Name+SKU+Description)`, `websearch_to_tsquery`, términos OR, orden por `ts_rank` |

**B lo construyó el propio trabajo de IA** (C15/C16, la ruta de circuito abierto). No es «lo que
había».

**Decisión: las dos, con nombres que no mientan — `v0-nombre` y `v0-fts`.**

*Alternativas descartadas:* sólo A responde la decisión 12 pero expone a la objeción de hombre de
paja; sólo B es un baseline justo pero **no responde la decisión 12** y además es casi el
`mode=lexical` del propio pipeline, o sea ya está en la escalera de ablación.

*Razón:* el argumento decisivo no es de justicia sino de **información**. Con una sola fila no se
sabe qué parte de la ganancia viene de tokenizar en español —gratis, sin IA— y qué parte viene de
la recuperación semántica. Con las dos, el informe puede decir *«pasar de subcadena a FTS español
da X; pasar de FTS a híbrido da Y»*, y si Y resulta pequeño **ése es un hallazgo del proyecto, no
un fracaso**.

**Fidelidad del texto:** `v0-fts` recompone en la sentencia `name ‖ sku ‖ <línea Descripción de
doc_text>` y hace `to_tsvector` sobre eso. Fiel a .NET, sin salir del esquema `ai`, sin romper la
regla dura del puerto (*«implementations must not read `public`»*). Un test fija el prefijo
`Descripción: ` como contrato del renderizador.

### D2 · Reproducibilidad: vectores congelados, procedencia como «seed», y desempate

**Decisión:**

1. **Congelar los vectores de las consultas** en `golden/query_vectors.jsonl`, con **6 decimales**
   (~700 KB, legible y diffeable; la pérdida de precisión es órdenes de magnitud menor que la
   separación entre distancias medidas, 0,366 a 0,700), indexados por `model_version_key`.
2. **«Seed» deja de ser un RNG** y pasa a ser una tupla de procedencia que cada `eval_run` guarda:
   `(golden_set_version, config_id, index_set_hash, embedding_model_version_key, git_sha)`. Un run
   que no puede reproducir esa tupla no es comparable, y el informe lo dice.
3. **Añadir `, d.product_id`** a los dos `ORDER BY` de `retrieval/search.py`, **dentro de C24**,
   con su test.

*Alternativas descartadas:* el patrón offline de C23 (`LocalEmbeddingClient`) es inservible para P1
—un embebedor de solape léxico *es* la rama léxica y no puede arbitrar el pleito entre ambas— y
volvería sin sentido el coste y el p95; llamar al proveedor en cada run no es reproducible.

> **Esta alternativa dejó de ser una objeción teórica el 2026-09-06.** Al ejecutar `sync-knowledge`
> contra el índice real, el umbral 0,81 que C23 había calibrado con el sustituto offline resultó
> **citar 4 de las 5 preguntas fuera de dominio**: no un número impreciso, sino *«el mecanismo de
> abstención inoperante»*. El valor correcto contra el embebedor real es **0,51**, y las dos
> distribuciones no se parecen en nada.
>
> Y la causa de fondo, que C24 tiene que evitar en el diseño de sus tests: había una constante
> `CALIBRATED` que servía **a la vez** para dirigir la medición offline y para afirmar que el
> default de `Settings` valía lo mismo. *«Ese test pasaba en verde mientras el defecto se enviaba,
> porque ataba dos números que viven en escalas distintas.»*
>
> **Regla que C24 hereda:** ninguna constante del arnés puede a la vez gobernar una medición y
> aseverar un default de producción. Si un test compara los dos, comprueba que son **distintos** y
> explica por qué copiarlos vuelve a romperlo.

*Sobre el punto 3, desviación declarada:* la ficha describe C24 como un change de evaluación, y
esto toca ruta viva. Se hace igualmente porque **C24 sin desempate determinista no es un arnés de
regresión, es un generador de ruido**, y el coste son dos líneas y un test. El precedente existe:
C22 abrió una revisión de Alembic contra su propia ficha y lo escribió.

### D3 · Relevancia graduada 0-2 con anclas mecánicas, publicando también la lectura binaria

El apunte S10 recomienda binario (*«consistente entre anotaciones»*); el diseño §11.1 manda 0/1/2.

**Decisión: 0-2, con las anclas escritas y versionadas en `golden/criterion.md` antes de etiquetar,
y el informe publica también la lectura binaria.**

```
 2  Se lo enseño al cliente como respuesta a ESA consulta.
 1  Mismo piece_type o misma familia, pero falla UN atributo que la consulta
    nombró explícitamente (talla, uno de varios materiales, color, piedra).
    O bien: sustituto plausible que el operador ofrecería como segunda opción.
 0  Todo lo demás.
```

*Razón:* el binario destruye la categoría crítica del dominio —«anillo correcto, talla
equivocada» no es 0 ni 2—, que es justo lo que C18 construyó. La frase que hace el trabajo es *«un
atributo que la consulta nombró explícitamente»*: convierte el grado 1 en una comprobación de
solape entre consulta y ficha, no en una impresión, y es lo que mitiga la deriva del anotador único
sin renunciar a la graduación.

*Y la lectura binaria sale gratis:* `relevante ⇔ grado ≥ 1`. Si las dos lecturas ordenan igual las
configuraciones, la robustez queda **demostrada**; si difieren, es un hallazgo. Contesta la
objeción del apunte con datos en vez de con argumento.

*Regla de proceso:* **etiquetar por categoría, no por orden de id.** Las seis de sinónimos seguidas
mantienen la vara más quieta que seis dispersas entre 48.

### D4 · Tamaño derivado de los pleitos: **48 juzgadas, 56 escritas**

Las 60-70 del diseño se fijaron en agosto, **antes** de que existieran las mediciones de
C20/C21/C22 que ahora dicen exactamente qué hay que medir. El tamaño se re-deriva desde abajo, una
fila por pleito, sin categorías de relleno. Composición cerrada en el §5. Las cifras son de orden
de magnitud: si al escribirlas sale alguna consulta más, no es un incumplimiento.

**Decisión adicional, contaminación del conjunto de ajuste:** las 24 consultas de C20/C21 —12
curadas + 12 de `ProductSearchEvents`— **se usaron para fijar `wC=0,33`, la profundidad 40-60 y la
regla de coordinación**. Incluirlas sin marcar sería medir sobre el conjunto de ajuste.

Se incluyen **marcadas con `in_tuning_set: true`**, y el informe publica **tres lecturas**: global
· sólo ajuste · sólo consultas nuevas.

*Razón:* excluirlas tiraría las 12 únicas consultas no inventadas por el harness y rompería la
comparabilidad con C21. Marcarlas hace la contaminación **visible y cuantificada**: si `wC=0,33`
gana en las tres lecturas, la decisión de C21 queda confirmada de verdad; si sólo gana en las de
ajuste, se ha encontrado un sobreajuste — y encontrarlo es el trabajo.

**Advertencia de potencia estadística, adoptada del apunte S10 y escrita en el informe:**

```
 umbral    Recall@5 ≥ 0,85 sobre la porción real
 tamaño    ~25-30 consultas reales de las 48 (436 de 1.200 productos)
 IC 95 %   ±0,13
 lectura   el umbral NO distingue 0,80 de 0,88. Lo comparable entre
           configuraciones sigue siendo válido, porque el sesgo del
           anotador único es el mismo en todas las filas de la tabla.
```

**Categorías no medibles hoy:** *sustituto / sin stock* (C26, `/v1/retrieval/substitutes` es 501) y
*ambigua → requiere aclaración* (C30, es decisión del agente). Se escriben **4 + 4 consultas
declaradas con `pooled_in: []` y sin juicios**, para que C26 y C30 hereden el formato y etiqueten
sólo su incremento.

*Razón:* etiquetarlas ahora produciría juicios sesgados hacia lo que devuelve el recuperador
general, porque **no existe configuración que las recupere y por tanto no se pueden agrupar**.

### D5 · «Reportado por `data_origin`»: agrupar por consulta, contar por juicio

**Decisión: la recuperación corre SIEMPRE sobre los 1.168 documentos.** Las consultas se agrupan
por el origen de sus documentos relevantes, y la métrica cuenta sólo los relevantes de ese origen.

*Alternativa descartada:* restringir la recuperación a `data_origin='real'` daría un corpus de 436
—**más fácil**— e inflaría el número del titular. Contradice el §8.1.1 del diseño, cuya frase *«si
el global cumple y el real no, el corpus sintético es demasiado fácil»* sólo tiene sentido si ambos
corren sobre el mismo corpus.

**Métrica adicional, que nadie había pedido:**

```
 desplazamiento_sintetico@5 = fracción de consultas reales en las que un producto
 sintético de grado 0 aparece por delante del primer grado 2 real
```

Es la prueba directa de la hipótesis del §8.1.1. Si sale alto, el corpus sintético no es «más
fácil»: es **ruido activo** que degrada la porción real. Distinción que hoy nadie puede hacer.

### D6 · `v0-cag`: medición acotada, fechada y declarada

**Decisión.** CAG no es una fila de calidad: es **la prueba medida de por qué existe RAG**. Produce
tres cosas y nada más:

1. **Tokens y coste** del corpus completo compactado.
2. **Recall@5 sobre un subconjunto de 12** — las de descripción natural sin anclaje léxico, que es
   donde CAG debería brillar por tener el catálogo entero delante.
3. **Curva de escala**: tokens frente a tamaño de catálogo, extrapolada a 2.500 y 5.000.

**Contexto compactado y sin precio:** `sku · nombre · tipo · materiales`, una línea por producto.

*Razón para excluir el precio:* §3.2. `RetrievalResult` no emite precio y la regla de frontera es
que .NET es su autoridad; meterlo en un prompt sería la primera vez que cruza hacia una superficie
generativa. Si alguna consulta necesita precio para responderse, **CAG falla y eso es un resultado,
no un defecto**.

*Alternativas descartadas:* quitarlo dejaría la sección CAG del README sin evidencia —y con ella la
columna de coste a cero (D11)—; la fila completa de ablación mezcla una medición no reproducible
con filas que sí lo son y cuesta cuatro veces más para responder una pregunta cualitativa.

*Razón del subconjunto de 12:* el resultado que importa es grande y cualitativo. Si CAG con el
catálogo entero delante no bate al híbrido en las consultas que más le favorecen, no lo bate en
ninguna. Coste estimado: 12 llamadas × ~26.000 tokens ≈ **$0,05**.

**El test se reescribe.** `test_cag_baseline_respects_context_budget` **no** significa «cabe» —eso
se cae el día que el catálogo crezca—, sino:

> Dado un corpus mayor que el presupuesto, la configuración **trunca de forma determinista** (orden
> estable por `product_id`) y registra `documents_omitted: N` en el `eval_run`, de modo que su
> Recall se lea sabiendo qué parte del catálogo nunca vio.

*Declaración:* CAG llama a un LLM. Ni con temperatura 0 es reproducible bit a bit. Es **una fila de
una sola medición**, con su fecha y su modelo, no una configuración que se re-ejecute en cada run.

### D7 · *Pooling* de profundidad adaptativa con regla de parada

El *pool* es la unión, sin repetir, de lo que devuelve cada configuración; se juzga esa unión a
mano y **todo lo que queda fuera se asume grado 0**. La profundidad es cuántos se toman de cada
lista antes de unir. No mejora las métricas de las configuraciones que están en el pool —esas sólo
necesitan sus cinco primeros juzgados—: compra un **denominador de recall honesto** y **cobertura
para el futuro** (C25, C26 y cualquier reranking reordenan y pueden subir documentos que nadie
juzgó, que contarían 0).

Aritmética con 48 consultas, a ~4,6 s por juicio (80 % son ceros evidentes de ~2 s, 20 % de borde
de ~15 s):

| Profundidad | Docs únicos/consulta | Juicios | Tiempo |
|---:|---:|---:|---|
| 10 × 4 configs | ~20 | 960 | ~1 h 15 |
| 20 × 4 | ~37 | 1.780 | ~2 h 20 |
| 40 × 4 | ~70 | 3.360 | ~4 h 20 |
| 60 × 4 | ~120 | 5.760 | ~7 h 20 |

**Decisión: profundidad adaptativa.**

```
 1. Base 20 en las cuatro configuraciones, siempre.  (= el top_k×3 que recibe .NET)
 2. Se continúa en bloques de 10 mientras el bloque anterior haya dado
    ≥1 documento de grado ≥1.
 3. Tope 60 = branch_depth: más allá, el pipeline vivo no puede mostrarlo,
    así que juzgarlo no informa de nada.
 4. Se registra judged_depth por consulta en el fichero.
```

Estimación: **~3 h 15**, repartidas en **tres sesiones agrupadas por categoría** (~1 h cada una),
que es la mitigación de la fatiga sin coste en consultas — y la misma disciplina que D3 pide por
otro motivo.

*Alternativas descartadas:* profundidad fija 10 da un denominador optimista y deja el agujero de
C25 abierto; profundidad fija 60 gasta la mayor parte del esfuerzo en ceros evidentes —para `joya
con forma de concha marina` sólo existen ~4 piezas de caracola, y las posiciones 20 a 60 son 40
juicios de 0 garantizados— y siete horas seguidas activan exactamente el modo de fallo que el plan
nombra: *«un etiquetador cansado y único es el fallo que el doble etiquetado ya no puede
corregir»*.

*El tope de 2 h de la ficha no es vinculante:* se escribió cuando la restricción era un calendario
que dejó de existir el 2026-08-31 (prórroga abierta).

**Y la mecánica que salva la tabla de C25:** los juicios van por clave `(query_id, product_id)` y
son **apendables**. C25 profundiza más adelante sin re-etiquetar nada, y el **`unjudged@5`
reportado por configuración** hace que una fila con el 40 % de su top-5 sin juzgar sea
*visiblemente* no comparable en vez de silenciosamente injusta.

### D8 · Abstención: C24 mide y publica la distribución; **C25 calibra**

**Decisión.** C24 mide la abstención tal como sale **y publica la distribución de distancias por
grado de relevancia** (grado 2 frente a grado 0). No calibra.

*Razón:* con 0,65 dejando pasar 1.168/1.168, el número dirá que `v0-nombre` abstiene al 100 % —no
encuentra nada nunca— y que el híbrido no. Cierto y engañoso. Y la ficha de C25 ya reclama
*«re-fijación del umbral con la distribución empírica»*; además el §9 de C21 demostró que hace
falta un **cuantil por consulta, no un escalar**, lo que no es un barrido sino un rediseño.

El histograma «distancia del grado 2 vs distancia del grado 0» **no existe hoy** y es exactamente
el insumo que a C25 le falta para decidir si un cuantil es viable.

**Y ya se sabe qué forma tiene la respuesta buena, porque el corpus de conocimiento la dio el
2026-09-06.** Allí el histograma mostró un **hueco limpio**: las 32 preguntas con respuesta llegan
como mucho a 0,5062 y las 5 fuera de dominio empiezan en 0,5145 — ocho milésimas de margen, y con
eso la regla se aplica literalmente y sale 0,51.

```
 conocimiento (32+5 preguntas)   [0,2485 … 0,5062]  ▏hueco▕  [0,5145 … 0,9135]   → hay umbral
 productos     (C21 §9)          0,65 deja pasar 1.168/1.168 · el corte es el LIMIT
                                 y el umbral que dejaría 60 varía 0,445 → 0,594   → ¿hay hueco?
```

**La pregunta que C24 contesta con su histograma es si el corpus de productos tiene ese hueco o no
lo tiene.** Si lo tiene, C25 fija un escalar como hizo C23. Si no —que es lo que el §9 de C21 hace
esperar—, queda demostrado que hace falta un cuantil por consulta, y **eso es un resultado**, no una
tarea pendiente.

*Frase que va literal al informe de implementación:* «la abstención medida aquí es un artefacto de
la mecánica de ramas, no una decisión de confianza; el umbral 0,65 deja pasar el corpus entero (C21
§9) y su re-fijación es alcance de C25».

### D9 · Anclaje de las etiquetas: `product_id` + `source_hash`

**Decisión.** Cada juicio guarda el `source_hash` que el documento tenía **en el momento de
etiquetar**, y el runner reporta *«N documentos etiquetados cambiaron de texto desde el
etiquetado»*.

*Razón:* `FIX1` reenriqueció 22 productos el 2026-09-05 y su plazo duro era *«entrar antes de que
C24 etiquete»*. Esa ventana se cumplió **por planificación**; con `source_hash` deja de depender de
ella. La columna ya existe: `CHAR(64) NOT NULL` en `ai.product_document`.

### D10 · *Artifact-first*, con las tres tablas escritas sólo bajo `--persist`

```
 runner  ──produce──▶  Report (objeto en memoria)
                          │
                          ├──▶ report.py      → Markdown + JSONL en git   [SIEMPRE]
                          └──▶ repository.py  → ai.eval_run/case/result   [SÓLO --persist]

 El runner no importa repository.py: no sabe que la base de datos existe.
```

**Decisión: las tres tablas, con su migración, escritas sólo con `--persist`. El golden set es un
fichero en git, nunca una tabla.**

*Razón, dicha sin adornos:* **no es de utilidad, es de contrato.** Nadie va a hacer SQL contra esas
tablas —los informes están en git y son diffeables, que es más cómodo—, pero `GET /v1/evals/runs`
**está publicado en el `openapi.json` congelado** y su stub nombra a C24 por escrito. En un
proyecto que lleva veinticinco changes declarando cada desviación, dejar una ruta mintiendo cuesta
más explicarlo que implementarlo. Y C38 (*«todo integrado en el runner e informe de C24»*) hereda
el sitio.

*Alternativas descartadas:* sin tablas obligaría a reescribir la nota del README y del stub y a
declarar desviación contra el diseño §7.2; sólo `ai.eval_run` cumpliría el contrato publicado
—`EvalRunsResponse` devuelve exactamente eso— pero exige desviación escrita sobre las otras dos.

*Y lo que no cambia en ningún caso:* **cambiar la vara de medir pasa por revisión de código.** El
golden set vive en `ai-service/evals/golden/`, versionado.

### D11 · Coste por consulta: `pricing.yaml`, ligado a D6

**Decisión.** Se conserva la columna de coste y el test, **porque se conserva `v0-cag`**. Precios
de facturación de proveedor por millón de tokens, en fichero versionado con fecha y fuente, a
**verificar contra la fuente el día de la implementación**:

```yaml
# ai-service/evals/golden/pricing.yaml
as_of: 2026-09-XX          # verificar antes de fijar
source: https://openai.com/api/pricing/
models:
  openai/text-embedding-3-small:  { input_per_1m_usd: 0.02 }
  openai/gpt-4o-mini:             { input_per_1m_usd: 0.15, output_per_1m_usd: 0.60 }
```

*Razón, que es la parte que importa:*

```
 v0-nombre     0 tokens                          $0
 v0-fts        0 tokens                          $0
 v1-vectorial  ~10 tokens de consulta embebida   $0,0000002
 v2-hibrido    ~10 tokens                        $0,0000002
 v0-cag        ~26.000 tokens de contexto        $0,0039        ← cuatro órdenes de magnitud
```

**Sin `v0-cag` la columna es una columna de ceros y no informa de nada** — cinco millones de
consultas por dólar es contablemente irrelevante. D6 y D11 son la misma decisión: la columna existe
para que la comparación CAG↔RAG sea un número, y es lo que permite escribir en el README la frase
que el marco de decisión de S10 exige —*la ganancia se lee contra un coste*—:

> «RAG cuesta cuatro órdenes de magnitud menos que CAG por consulta y no tiene techo de catálogo.
> Ésa es la razón de la arquitectura, medida y no argumentada.»

Uso secundario que sobrevive: fija el denominador del «no» al reranking (P8).

### D12 · Latencia: dos columnas, en caliente, tres ejecuciones

El criterio del diseño §11.2 —*«p95 de retrieval < 500 ms»*— **no se puede cumplir tal como está
escrito**:

```
 embed (proveedor)   170 – 1707 ms    1707 ms en 1 de cada 4 llamadas (C16)
 vector SQL          14,8 – 33,1 ms   con CTE escopado (C22 §3)
 lexical SQL         «ruido» sobre 1.168 filas con GIN
 presupuesto C16     2500 ms temporales
```

Un p95 extremo a extremo será ~1.700 ms, no 500.

**Decisión: dos columnas siempre.** `p95_retrieval` (pipeline sin el ida y vuelta del proveedor) es
a la que se aplica el criterio de aceptación —que es lo que el diseño quiso decir—; `p95_e2e` va al
README junto al presupuesto de C16. La instrumentación **ya existe**: el orquestador emite
`latency_ms` por etapa (`expand`, `embed`, `projection`, `lexical`, `search`, `fuse`); el harness
sólo los recoge.

**Higiene, adoptada del apunte S10:** medir **en caliente** (se descarta la primera ejecución) y **3
ejecuciones por consulta**. Con 48 × 3 = 144 muestras un p95 significa algo; con 48 el p95 es la
tercera peor muestra y es ruido puro.

*Absorbe los dos pendientes de C21 §12:* latencia real de la rama léxica dentro del orquestador, y
efecto del singleton del cliente de embeddings sobre el p95 en frío y en caliente.

### D13 · C24 cambia defaults si el veredicto es material

C21 escribió: *«estas cifras fijan un punto de partida, no dictan un veredicto: el juez es el golden
set de C24»*. **Decisión: C24 cambia el `default` en `Settings` cuando el juez dictamine**, bajo una
regla escrita **antes** de medir para que no sea *post hoc*:

```
 Se cambia un default si y sólo si:
   · el delta de nDCG@5 supera 0,05 (por encima del ruido de anotación que S10
     estima para golden sets de este tamaño), Y
   · el signo es el mismo en las tres lecturas de D4
     (global · conjunto de ajuste · consultas nuevas), Y
   · no empeora ninguna de las 7 categorías medibles en más de 0,05.
```

*Razón:* es literalmente para lo que se construyeron los knobs como parámetros; el cambio es una
línea, reversible por variable de entorno, sin migración y sin mover el `openapi.json`. Y con la
regla escrita, «el barrido de C21 se rehízo con el juez bueno» es una frase respaldada por un
criterio y no por una impresión.

---

## 5. El golden set: composición cerrada

**48 consultas juzgadas · 56 escritas · suelo duro 45.** Una fila por pleito, sin relleno.

| Categoría | Nº | Pleito | Recortable |
|---|---:|---|---|
| Descripción natural **sin anclaje léxico** | **12** | P1 — vector vs léxica | **No** |
| Variante / talla | **7** | el caso crítico del dominio (§11.1) | **No** |
| Materiales (incl. multi-valor) | 5 | P3 — solape `&&` vs `@>` | a 4 |
| Piedra (aísla `stone_type`) | 4 | P3 — pregunta abierta de C21 §12 | a 3 |
| Subjetiva (ocasión / estilo / regalo) | 5 | P3 — la propiedad emergente | a 4 |
| Sinónimos (2 por cada uno de los 3 tipos) | **6** | P4 | **No** |
| Léxico exacto (SKU y nombre) | 4 | P7 — donde el baseline puede ganar | a 3 |
| Fuera de dominio **plausible** | 5 | P5 — abstención | **No** |
| **Total juzgado** | **48** | | **suelo 45** |
| Sustituto / sin stock — *declaradas, `pooled_in: []`* | 4 | C26 | — |
| Ambigua → requiere aclaración — *declaradas* | 4 | C30 | — |
| **Total escrito** | **56** | | |

### Tres cambios respecto a la tabla del diseño §11.1, con su motivo

1. **Desaparece «descripción natural con anclaje» como categoría propia.** Ese control ya lo dan
   *materiales* y *sinónimos*, que son anclados por construcción. Era relleno.
2. **«Precio / ocasión / regalo» (8) se parte y encoge a «subjetiva» (5).** Motivo medido:
   `Ocasiones:` cubre el 13 % del corpus, `boda` casa 5 documentos y `regalo` 7 de 1.168. Ocho
   consultas sobre un campo cubierto al 13 % no miden ocho veces mejor: miden ocho veces el mismo
   hueco. El precio, además, es un filtro estructural extraído por reglas, no una señal de ranking,
   y no merece consultas propias.
3. **Aparece «piedra» (4)**, que no estaba. Cierra la pregunta que C21 dejó explícitamente abierta
   en su §12.

### Matriz de trazabilidad pleito → requisito verificable

Es lo que impide que el golden set salga sesgado, y **cada requisito es comprobable por código antes
de etiquetar**:

| Pleito | Requisito verificable | Nº |
|---|---|---:|
| P1 | ≥1 documento de grado 2 cuyo `doc_text` **no contenga ningún término de la consulta tras expansión** | 12 |
| P3 subjetiva | La consulta resuelve a `occasion_tags` o `style_tags` y a ningún campo de cobertura alta | 5 |
| P3 piedra | La consulta nombra un valor de `stone_type` y el `piece_type` no discrimina | 4 |
| P4 | Cobertura de los 3 tipos: artefacto de stemmer · sinónimo comercial · puente direccional | 6 |
| P5 | Plausible en dominio joyería **y** con cero documentos de grado ≥1 en el corpus | 5 |
| P7 | La consulta es un SKU literal o un nombre literal de producto | 4 |
| P2, P8 | (sin requisito propio: se sirven de las anteriores) | — |

Suma comprometida: **36 de 48**. El resto lo reparten *variante/talla* y *materiales*, que el diseño
ya define.

### Anclaje a productos reales

El §8.1.1 manda etiquetar **primero sobre productos reales** (436 de 1.200) y completar con
sintéticos sólo si no hay material. Se aplica **por categoría**, no globalmente, para que ninguna
categoría quede íntegramente sintética — un desglose por `data_origin` con una categoría entera de
un solo origen no sería comparable.

---

## 6. Formato de los artefactos

```
 ai-service/evals/
   golden/
     criterion.md            anclas de grado (D3), escritas ANTES de etiquetar
     queries.jsonl           id · texto · categoría · in_tuning_set · anclaje previsto
     judgements.jsonl        (query_id, product_id) → grade · pooled_in · judged_at · source_hash
     query_vectors.jsonl     congelados por model_version_key, 6 decimales      (D2)
     pricing.yaml            precios con fecha y fuente                          (D11)
   configs/
     v0-nombre.yaml  v0-fts.yaml  v0-cag.yaml  v1-vectorial.yaml  v2-hibrido.yaml
   results/
     c20-…md  c21-…md                     ya están
     c24-baselines-<fecha>.md             el informe de la tabla de ablations
     runs/<run_id>.jsonl                  crudo por caso, para diffear entre runs

 ai-service/src/jbg_ai/evals/
   golden.py      carga y valida el fichero; verifica la matriz de trazabilidad del §5
   pooling.py     unión de listas, profundidad adaptativa, detección de no juzgados
   metrics.py     nDCG@5 · Recall@5 · MRR · P@3 · abstención · unjudged@5 · desplazamiento_sintetico@5
   configs.py     las cinco configuraciones
   runner.py      orquesta y construye Report; NO sabe de persistencia
   report.py      Report → Markdown + JSONL
   repository.py  Report → ai.eval_run/case/result   (sumidero, sólo --persist)
   cli.py         uv run evals run --config vX [--persist] [--repeat 3]
```

Un juicio, con todo lo que las decisiones exigen:

```jsonl
{"query_id":"q07","product_id":"…","grade":2,"pooled_in":["v1-vectorial","v2-hibrido"],
 "judged_at":"2026-09-…","source_hash":"a3f…"}
```

---

## 7. Alcance y no-alcance

**Entra:**

- Paquete `ai-service/src/jbg_ai/evals/` y CLI `uv run evals run --config vX`.
- **Una** revisión de Alembic: `ai.eval_run`, `ai.eval_case`, `ai.eval_result`.
- Golden set de 48 juzgadas / 56 escritas, con su `criterion.md` y sus vectores congelados.
- Cinco configuraciones: `v0-nombre`, `v0-fts`, `v0-cag` (acotado), `v1-vectorial`, `v2-hibrido`.
- Informe versionado en `evals/results/` con la tabla de ablations v0→v2.
- **Desviación declarada:** `, d.product_id` en los dos `ORDER BY` de `retrieval/search.py` (D2).
- **Desviación declarada:** posible cambio de defaults en `Settings` bajo la regla de D13.
- Las dos mediciones que C21 §12 dejó sin dueño (latencia léxica en el orquestador; efecto del
  singleton sobre el p95 en frío y caliente).

**No entra, y se declara:**

- **Calibración del umbral de distancia** → C25 (D8). C24 entrega la distribución por grado.
- **`v3-señales`** → C25.
- **Fila escopada por punto de venta** (P6) → recortable declarado; si se cae, el informe dice que
  el coste del prefiltro en recall queda sin medir.
- **Cualquier cambio en `backend/`.** Cero.
- **`openapi.json`**: sin cambios. La ruta ya está publicada; sólo deja de ser stub.
- **RAGAS, validador anti-alucinación, escenarios de agente y adversarios** → C38.

---

## 8. Los tests de la ficha, releídos

| Test de la ficha | Qué significa tras esta exploración |
|---|---|
| `test_ndcg_matches_hand_computed_value_on_fixture` | Sin cambios. Fixture fijo, valor calculado a mano |
| `test_run_is_reproducible_for_same_config_and_seed` | «Seed» = tupla de procedencia (D2). **Depende del desempate del §3.1**; sin él el test miente |
| `test_metrics_reported_per_data_origin` | Verifica la semántica de D5: la recuperación corre sobre 1.168, el agrupamiento es por consulta y el recuento por juicio |
| `test_lexical_baseline_matches_dotnet_search_semantics` | **Paramétrico sobre dos baselines** (D1). Para `v0-fts`, fija además el prefijo `Descripción: ` como contrato del renderizador |
| `test_cag_baseline_respects_context_budget` | **Reescrito** (D6): trunca de forma determinista y registra `documents_omitted`, no «cabe» |
| `test_cost_per_query_recorded_per_config` | Se conserva porque se conserva `v0-cag` (D11). Comprueba que **cero es un valor registrado, no un hueco** |

Tests nuevos que las decisiones exigen: desempate determinista en ambas ramas; `unjudged@5`
reportado por configuración; validación de la matriz de trazabilidad del §5 al cargar el golden set;
detección de `source_hash` cambiado desde el etiquetado.

---

## 9. Riesgos

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| **R1** | El golden set se etiqueta con el sesgo del rúbrico de C21 (tipo + material) y confirma C21 por construcción | **Alto.** C24 dejaría de arbitrar nada | Matriz de trazabilidad del §5 **validada por código** antes de etiquetar; etiquetar antes de mirar los resultados de C21 |
| **R2** | Sin desempate, dos runs idénticos difieren | Alto | D2, dentro de C24 |
| **R3** | Lo no juzgado cuenta 0 y castiga a C25, C26 y a cualquier reranking | Alto y **diferido**: explota en C25 | Juicios apendables + `unjudged@5` + profundidad adaptativa (D7) |
| **R4** | Fatiga del anotador único en una sesión larga | Medio | Tres sesiones de ~1 h agrupadas por categoría (D7) |
| **R5** | El etiquetador escribió el corpus (los 764 sintéticos son suyos) | Medio, **irreducible** | Ya declarado en §15.4 del diseño; se añade que el sesgo **es el mismo en todas las filas**, que es lo que salva la comparación |
| **R6** | HT-ARTRUTX tiene surtido 0 y devuelve 503 | Bajo | Excluirlo explícitamente si se hace la fila escopada |
| **R7** | El criterio `p95 < 500 ms` se declara incumplido sin querer | Medio, de lectura | Dos columnas (D12) |
| **R8** | Un reenriquecimiento posterior invalida juicios en silencio | Bajo | `source_hash` por juicio (D9) |

---

## 10. Precondiciones de entorno — **verificar antes de empezar; si falla, parar y configurar**

El *pool* **no se puede construir desde un fichero**: hay que ejecutar las configuraciones contra el
índice real para saber qué devuelve cada una. Tres cosas encendidas a la vez:

| Requisito | Por qué | Comprobación |
|---|---|---|
| Contenedor `jpv-pv-postgres` en el **5433**, con los 1.168 documentos y sus embeddings | Las listas salen de SQL contra `ai.product_document` | `SELECT count(*) FROM ai.product_document WHERE is_active` → 1.168 |
| **`JPV_EMBEDDING_API_KEY`** operativa | Sin ella no hay lista `v1-vectorial` y el *pool* se queda cojo **justo en el pleito P1** | una llamada de prueba al proveedor |
| **`SSL_CERT_FILE`** apuntando al PEM de raíces de Windows concatenado con el bundle de `certifi` | El TLS de esta máquina está interceptado y `certifi` no lo acepta — misma causa del `--system-certs` de `CLAUDE.md` | nota de entorno del informe de exploración de C21 |

**Precedente que lo justifica:** C23 se exploró con el contenedor apagado, trabajó con proxies sobre
texto y su informe de implementación tuvo que re-medirlo y corregir cifras (`perla` 8 → 0, `coral`
102 → 23, `hilo` 63 → 37). En C24 no es una molestia: **sin base y sin clave no hay pool, y sin pool
no hay golden set.**

---

## 11. Qué queda pendiente y qué hereda C25

**Pendiente de medir, y este change lo mide:** todo el §2, más los dos huérfanos de C21 §12.

**Lo que C24 entrega a C25 y que hoy no existe:**

- La **distribución de distancias por grado de relevancia**, que es el insumo para decidir si el
  umbral por cuantil es viable (D8).
- El golden set con juicios **apendables** y el `unjudged@5`, para que `v3-señales` pueda profundizar
  el *pool* sin re-etiquetar y sepa cuándo su fila no es comparable (D7).
- Una tabla de ablations v0→v2 **reproducible con un comando**, a la que v3 añade una fila.

**Lo que queda declarado como no medido:**

- El coste del prefiltro por punto de venta en recall (P6), si la fila escopada se recorta.
- El reranking (P8): C24 deja el protocolo ejecutable y el número que lo haría decidible —consultas
  con grado 2 en el top-20 pero fuera del top-5—, no el reranker.
- La ausencia de acuerdo entre anotadores, que el README declara como limitación del golden set en
  lugar de reclamar una mitigación que no se aplicó.
