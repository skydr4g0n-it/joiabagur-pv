## Context

El sistema tiene dos índices vectoriales vivos y una búsqueda híbrida completa, y **ninguna decisión de recuperación se ha tomado con una métrica de relevancia**. La rúbrica que gobierna las decisiones de C20, C21, C22 y `FIX1` cuenta aciertos como «tipo de pieza y material correctos», y es la función objetivo de una de las dos partes en litigio: `doc_text` lleva líneas canónicas `Tipo:` y `Materiales:` y la expansión apunta justo ahí.

Bajo ese juez, medido sobre 12 consultas y los 1.168 documentos vivos:

| Configuración | aciertos / 120 |
|---|---:|
| Vectorial sola | 67 |
| Léxica sola | 107 |
| Mejor fusión (`wC=0,33`, profundidad 40-50) | 113-114 |

**El precedente que fija el método.** El 2026-09-06, en el corpus de conocimiento, el embebedor sustituto de C23 había medido que la rama léxica ganaba +6,2 pp de Recall@3. Al indexar contra el proveedor real y re-medir, el recall resultó ser **93,8 % en las dos configuraciones**: la rama léxica no gana recuperación, sólo orden. El informe lo escribe sin adornos — *«el +6,2 pp del §1 era un efecto del sustituto léxico, no una propiedad del sistema»*— y el umbral que aquel sustituto había calibrado (0,81) **citaba cuatro de las cinco preguntas fuera de dominio**: el mecanismo de abstención inoperante, no una imprecisión. El valor correcto contra el embebedor real es 0,51.

Ese episodio deja dos restricciones que este diseño hereda:

1. **Se mide contra el proveedor real y el índice real.** Un sustituto léxico no puede arbitrar un pleito entre una rama léxica y una vectorial: *es* una de las partes.
2. **Ninguna constante puede a la vez gobernar una medición y aseverar un default de producción.** La causa de fondo que C23 documentó fue una constante compartida: *«ese test pasaba en verde mientras el defecto se enviaba, porque ataba dos números que viven en escalas distintas»*.

**Restricciones del entorno.** Índice de 1.168 documentos (436 reales + 764 sintéticos de 1.200 productos). Pool de conexiones capado a 5, compartido con la ruta viva. `openapi.json` congelado por un MUST que enumera diez rutas. Un solo anotador, sin doble etiquetado ni conciliación, decisión tomada el 2026-08-31.

## Goals / Non-Goals

**Goals**

- Arbitrar con relevancia graduada los ocho pleitos que los informes de C20, C21, C22 y C23 dejaron abiertos.
- Responder la decisión 12 del diseño: ¿la búsqueda semántica mejora el buscador que la joyería tenía?
- Hacer **comparables** dos ejecuciones separadas en el tiempo, que es lo que convierte un arnés en red de seguridad frente a regresiones y no en una foto aislada.
- Entregar a C25 la distribución de distancias por grado de relevancia y un golden set con juicios ampliables.
- Dejar el protocolo del reranking **ejecutable**, no retórico.

**Non-Goals**

- **No** se recalibra `JPV_RETRIEVAL_DISTANCE_THRESHOLD`: es alcance de C25, cuya ficha ya lo pide, y el §9 de C21 demostró que hace falta un cuantil por consulta y no un escalar — un rediseño, no un barrido.
- **No** hay señales de negocio en el ranking (`v3-señales`, C25), ni sustitutos (C26), ni validador anti-alucinación, RAGAS o escenarios de agente (C38).
- **No** se implementa reranking.
- **No** se etiqueta escopado por punto de venta: decisión ya tomada en C22 para no mezclar calidad de recuperación con cobertura de surtido.
- **No** se mueve el `openapi.json` ni se toca `backend/`, `frontend/`, `terraform/` ni `.github/workflows/`.

## Decisions

### D1 · Dos líneas base léxicas, no una

El repositorio contiene **dos** buscadores léxicos y sólo uno es anterior al trabajo de IA: `ProductService.SearchProductsAsync` (coincidencia de subcadena sobre el nombre más código exacto, en memoria) y `AssistedSearchRepository.SearchLexicalAsync` (FTS español con `websearch_to_tsquery`, construido por C15/C16 como ruta degradada).

**Decisión: las dos, con nombres que no mientan — `v0-nombre` y `v0-fts`.**

*Alternativas:* sólo la primera responde la decisión 12 pero expone a la objeción de hombre de paja; sólo la segunda es un baseline justo pero **no responde la decisión 12** —la construyó el propio trabajo de IA— y además es casi el `mode=lexical` del pipeline, o sea ya está en la escalera de ablación.

*Razón:* el argumento no es de justicia sino de **información**. Con una sola fila no se sabe qué parte de la mejora es tokenizar en español —gratis, sin IA— y qué parte es recuperación semántica. Si esa segunda parte resulta pequeña, **es un hallazgo del proyecto y no un fracaso**.

**Fidelidad de `v0-fts`, que no es trivial.** `ai.product_document` tiene `name` y `sku` pero **no `description`**: tiene `doc_text`, que es el `source-text/v1` completo con `Tipo:`, `Materiales:`, `Colores:` y el resto. Un FTS sobre `doc_text` sería una **cota superior**, no una réplica. La sentencia recompone el texto equivalente extrayendo la línea `Descripción: `, y un test fija ese prefijo como contrato del renderizador para que un cambio en `build_source_text` rompa el test y no la fidelidad en silencio. Leer `public."Products"` queda descartado: el puerto declara *«implementations must not read `public`»*.

### D2 · Reproducibilidad: vectores congelados, procedencia como «seed», y desempate

**Vectores de consulta congelados** en `golden/query_vectors.jsonl`, seis decimales (~700 KB, legible y diffeable; la pérdida es órdenes de magnitud menor que la separación entre distancias medidas, 0,366 a 0,700), indexados por `model_version_key`.

**«Seed» deja de ser un RNG.** El pipeline no tiene aleatoriedad: lo que hace comparable una ejecución con otra es la procedencia. Cada `eval_run` guarda `(golden_set_version, config_id, index_set_hash, embedding_model_version_key, git_sha)`, y dos ejecuciones cuya tupla no coincide se marcan **no comparables** en lugar de compararse igualmente.

*Alternativas:* el patrón offline de C23 está descartado por el precedente del Context; llamar al proveedor en cada ejecución no es reproducible y multiplica el coste por configuración y repetición.

**Y el hallazgo que obliga a tocar ruta viva.** Ninguna de las dos sentencias tiene desempate:

```sql
-- retrieval/search.py:99    ORDER BY d.embedding <=> CAST(:q AS vector) ASC
-- retrieval/search.py:124   ORDER BY coordination DESC, ts_rank DESC
```

Con `LIMIT 60`, qué filas sobreviven al corte cuando hay empate **no está definido en PostgreSQL**. En la rama léxica los empates son masivos: `coordination` toma tres valores y `ts_rank` se repite entre documentos con el mismo patrón de campos.

**Decisión: `, d.product_id` como última clave en ambas, dentro de C24.** *Desviación declarada* — la ficha describe C24 como change de evaluación. Se hace porque sin ella `test_run_is_reproducible_for_same_config_and_seed` pasa en verde mientras el arnés produce ruido, que es el mismo patrón que C23 acaba de sufrir. Precedente: C22 abrió una revisión de Alembic contra su propia ficha y lo escribió.

*Trade-off:* cambia el orden observable entre documentos empatados en la ruta de producción. Hoy ese orden es indefinido, así que no se rompe ninguna garantía existente; se añade una.

### D3 · Relevancia graduada 0-2 con anclas mecánicas, publicando también la lectura binaria

El apunte de S10 recomienda binario por consistencia entre anotaciones; el diseño §11.1 manda 0/1/2.

**Decisión: 0-2 con anclas escritas y versionadas en `golden/criterion.md` antes de etiquetar, y el informe publica también la lectura binaria** (`relevante ⇔ grado ≥ 1`).

```
 2  Se lo enseño al cliente como respuesta a ESA consulta.
 1  Mismo piece_type o misma familia, pero falla UN atributo que la consulta
    nombró explícitamente (talla, uno de varios materiales, color, piedra).
    O bien: sustituto plausible que el operador ofrecería como segunda opción.
 0  Todo lo demás.
```

*Razón:* el binario destruye el caso crítico del dominio —«anillo correcto, talla equivocada» no es 0 ni 2—, que es exactamente lo que C18 construyó. La frase que hace el trabajo es *«un atributo que la consulta nombró explícitamente»*: convierte el grado 1 en una comprobación de solape entre consulta y ficha, no en una impresión, y es lo que mitiga la deriva del anotador único.

*Y la lectura binaria sale gratis:* si las dos ordenan igual las configuraciones, la robustez queda demostrada; si difieren, es un hallazgo. Contesta la objeción del apunte con datos.

*Regla de proceso:* etiquetar **por categoría**, no por orden de id. Mantiene la vara más quieta.

### D4 · 48 juzgadas, 56 escritas, derivadas de los pleitos

Las 60-70 del diseño se fijaron antes de que existieran las mediciones que dicen qué hay que medir. El tamaño se re-deriva desde abajo:

| Categoría | Nº | Pleito | Recortable |
|---|---:|---|---|
| Descripción natural **sin anclaje léxico** | 12 | vector vs léxica | **No** |
| Variante / talla | 7 | caso crítico del dominio | **No** |
| Materiales (incl. multi-valor) | 5 | solape `&&` vs `@>` | a 4 |
| Piedra (aísla `stone_type`) | 4 | pregunta abierta de C21 §12 | a 3 |
| Subjetiva (ocasión / estilo / regalo) | 5 | propiedad emergente de la coordinación | a 4 |
| Sinónimos (2 por cada uno de los 3 tipos) | 6 | expansión en ranking | **No** |
| Léxico exacto (SKU y nombre) | 4 | donde el baseline puede ganar | a 3 |
| Fuera de dominio **plausible** | 5 | abstención | **No** |
| **Total juzgado** | **48** | | suelo 45 |
| Sustituto (C26) y ambigua (C30), *declaradas sin juicios* | 8 | — | — |

*Cambios frente al §11.1 del diseño, con motivo medido:* desaparece «descripción natural con anclaje» —ese control lo dan materiales y sinónimos, era relleno—; «precio/ocasión/regalo» encoge de 8 a 5 porque `Ocasiones:` cubre el 13 % del corpus y `boda` casa **5 documentos de 1.168**, de modo que ocho consultas no miden ocho veces mejor sino ocho veces el mismo hueco; y aparece «piedra» (4), que cierra la pregunta que C21 dejó abierta.

**Contaminación del conjunto de ajuste.** Las 24 consultas de C20/C21 se usaron para fijar `wC`, la profundidad y la regla de coordinación. Entran **marcadas `in_tuning_set`**, y el informe publica tres lecturas: global · sólo ajuste · sólo nuevas.

*Alternativas:* excluirlas tiraría las 12 únicas consultas no inventadas por el harness y rompería la comparabilidad con C21; incluirlas sin marcar sería medir sobre el conjunto de ajuste sin decirlo.

**Potencia estadística, declarada y no descubierta al final:** con ~25-30 consultas reales, el intervalo del criterio de aceptación es de ±0,13. **No distingue 0,80 de 0,88.** Lo comparable entre configuraciones sigue siendo válido, porque el sesgo del anotador único es el mismo en todas las filas.

**Las dos categorías no medibles** se escriben pero no se juzgan: no existe configuración que las recupere, así que no se pueden agrupar, y etiquetarlas produciría juicios sesgados hacia lo que devuelve el recuperador general.

### D5 · Desglose por origen: agrupar por consulta, contar por juicio

**La recuperación corre SIEMPRE sobre los 1.168 documentos.** Las consultas se agrupan por el origen de sus documentos relevantes y la métrica cuenta sólo los relevantes de ese origen.

*Alternativa descartada:* restringir la recuperación a `data_origin='real'` daría un corpus de 436 —**más fácil**— e inflaría el número del titular. Contradice el §8.1.1 del diseño, cuya frase *«si el global cumple y el real no, el corpus sintético es demasiado fácil»* sólo tiene sentido si ambos corren sobre el mismo corpus.

**Métrica adicional:** `desplazamiento_sintetico@5`, la fracción de consultas reales en las que un sintético de grado 0 precede al primer grado 2 real. Distingue «el sintético es más fácil» de «el sintético estorba», que hoy nadie puede separar.

### D6 · `v0-cag` acotado: no es una fila de calidad, es la prueba de por qué existe RAG

CAG **no tiene una sola línea en el sistema**: aparece en el diseño §11.2 y en los checklists del PF, y en ningún otro sitio. El enunciado del PF pide *«escala desde un prototipo CAG hasta un sistema RAG»* y que el README describa *«CAG/RAG»* como componentes.

**Decisión: medición acotada, fechada y declarada.** Produce (1) tokens y coste del catálogo compactado, (2) Recall@5 sobre el subconjunto de 12 consultas sin anclaje léxico —donde CAG debería brillar por tener el catálogo entero delante—, (3) curva de escala hasta 2.500 y 5.000 productos.

Contexto: `sku · nombre · tipo · materiales`, una línea por producto, **sin precio**. La regla de frontera es que .NET es la autoridad sobre el precio y `RetrievalResult` no lo emite; meterlo en un prompt abriría por adelantado la superficie que el validador de C38 existe para cerrar.

*Alternativas:* quitarlo dejaría la sección CAG del README sin evidencia y la columna de coste a cero; la fila completa de ablación mezcla una medición no reproducible con filas que sí lo son y cuesta cuatro veces más para responder una pregunta cualitativa.

*Razón del subconjunto de 12:* el resultado que importa es grande y cualitativo. Si CAG con el catálogo entero delante no bate al híbrido donde más le favorece, no lo bate en ninguna parte.

**El presupuesto de contexto es un parámetro del informe, no una suposición.** Si el catálogo excede el presupuesto, se trunca de forma determinista por `product_id` y se registra `documents_omitted`, de modo que el Recall se lea sabiendo qué parte del catálogo nunca se vio. Así el requisito sigue valiendo cuando el catálogo crezca — que es justamente el punto del argumento CAG→RAG.

### D7 · *Pooling* de profundidad adaptativa

El *pool* es la unión sin repetir de lo que devuelve cada configuración; se juzga esa unión y **lo que queda fuera se asume grado 0** (supuesto estándar, declarado). La profundidad no mejora las métricas de las configuraciones ya incluidas —esas sólo necesitan sus cinco primeros juzgados—: compra un **denominador de recall honesto** y **cobertura para el futuro**.

Aritmética con 48 consultas, a ~4,6 s por juicio:

| Profundidad | Docs únicos/consulta | Juicios | Tiempo |
|---:|---:|---:|---|
| 10 × 4 configs | ~20 | 960 | ~1 h 15 |
| 20 × 4 | ~37 | 1.780 | ~2 h 20 |
| 60 × 4 | ~120 | 5.760 | ~7 h 20 |

**Decisión: adaptativa.** Base 20 (el `top_k×3` que recibe .NET); se continúa en bloques de 10 mientras el bloque anterior aporte algún grado ≥1; tope 60 (`branch_depth`, más allá el pipeline no puede mostrarlo); `judged_depth` registrado por consulta. Estimación ~3 h 15, en **tres sesiones agrupadas por categoría**.

*Alternativas:* fija 10 da un denominador optimista y deja el agujero de C25 abierto; fija 60 gasta la mayor parte del esfuerzo en ceros evidentes —para `joya con forma de concha marina` sólo existen ~4 piezas de caracola, y las posiciones 20 a 60 son 40 descartes garantizados— y siete horas seguidas activan el modo de fallo que el plan nombra: *«un etiquetador cansado y único es exactamente el fallo que el doble etiquetado ya no puede corregir»*.

**Y la mecánica que salva la tabla de C25.** Los juicios se identifican por `(query_id, product_id)` y son **apendables**: C25 profundiza sin re-etiquetar. El **`unjudged@5`** reportado por configuración hace que una fila con el 40 % de su top-5 sin juzgar sea *visiblemente* no comparable en vez de silenciosamente injusta.

### D8 · Abstención: medir y publicar la distribución; calibrar es C25

Con el umbral en 0,65 dejando pasar 1.168 de 1.168 en consultas ordinarias, el número dirá que `v0-nombre` abstiene al 100 % —no encuentra nada nunca— y que el híbrido no. Cierto y engañoso.

**Decisión: C24 mide la abstención y publica la distribución de distancias por grado; no toca el umbral.**

*Razón:* la ficha de C25 ya reclama *«re-fijación del umbral con la distribución empírica»*, y el §9 de C21 demostró que hace falta un cuantil por consulta. El histograma «distancia del grado 2 frente a distancia del grado 0» no existe hoy y es el insumo que falta.

**Y ya se sabe qué forma tiene una respuesta buena**, porque el corpus de conocimiento la dio: hueco limpio entre 0,5062 (máximo de las preguntas con respuesta) y 0,5145 (mínimo de las de fuera de dominio), ocho milésimas de margen. **La pregunta que C24 contesta es si el corpus de productos tiene ese hueco.** Si no lo tiene —que es lo que el §9 de C21 hace esperar—, queda demostrado que hace falta un cuantil, y **eso es un resultado**, no una tarea pendiente.

*Corolario sobre el golden set:* las consultas fuera de dominio deben ser **plausibles pero imposibles**, nunca texto sin sentido. Con `xyzzy quimbombo` todas las configuraciones abstienen al 100 % y la métrica no discrimina nada.

### D9 · Anclaje de juicios: `product_id` + `source_hash`

Cada juicio guarda el `source_hash` que el documento tenía al etiquetarse, y el runner reporta cuántos juicios se apoyan en un texto que ya cambió.

*Razón:* `FIX1` reenriqueció 22 productos con el plazo *«antes de que C24 etiquete»*. Esa ventana se cumplió **por planificación**; con el hash deja de depender de ella. La columna ya existe (`CHAR(64) NOT NULL`).

### D10 · *Artifact-first*, con las tres tablas bajo `--persist`

```
 runner  ──produce──▶  Report (objeto en memoria)
                          ├──▶ report.py      → Markdown + JSONL en git   [SIEMPRE]
                          └──▶ repository.py  → ai.eval_run/case/result   [SÓLO --persist]

 El runner no importa repository.py: no sabe que la base de datos existe.
```

**Decisión: las tres tablas con su migración, escritas sólo con `--persist`. El golden set es un fichero, nunca una tabla.**

*Razón, dicha sin adornos:* **no es de utilidad, es de contrato.** Nadie hará SQL contra esas tablas —los informes están en git y son diffeables—, pero `GET /v1/evals/runs` está publicado en el `openapi.json` congelado, la spec viva lo especifica, y su stub **nombra a C24**. Dejar una ruta mintiendo cuesta más explicarlo que implementarlo. Y C38 hereda el sitio.

*Alternativas:* sin tablas obligaría a reescribir la nota del stub y a declarar desviación contra el diseño §7.2 y contra la spec viva; sólo `ai.eval_run` cumpliría el contrato pero exige desviación escrita sobre las otras dos.

*Detalle de esquema:* `metrics jsonb` en vez de una columna por métrica, porque C38 añadirá métricas de generación al mismo runner y no debe forzar una segunda revisión de Alembic.

### D11 · Coste por consulta, ligado a D6

`pricing.yaml` versionado con fecha y fuente. **Cero es un valor registrado, no un hueco.**

```
 v0-nombre / v0-fts   0 tokens                      $0
 v1 / v2              ~10 tokens de consulta        $0,0000002
 v0-cag               ~26.000 tokens de contexto    $0,0039      ← cuatro órdenes de magnitud
```

*Razón:* sin `v0-cag` la columna sería toda ceros y no informaría de nada. Con él, permite la frase que el marco de decisión de S10 exige —*la ganancia se lee contra un coste*—: «RAG cuesta cuatro órdenes de magnitud menos que CAG por consulta y no tiene techo de catálogo». Uso secundario que sobrevive: fija el denominador del «no» al reranking.

### D12 · Latencia: dos columnas, en caliente, tres ejecuciones

El criterio del diseño §11.2 —*«p95 de retrieval < 500 ms»*— no se puede cumplir leído a una sola columna: con el proveedor en 170-1707 ms, un p95 extremo a extremo será ~1.700 ms.

**Decisión: `p95_retrieval` (sin el ida y vuelta del proveedor) lleva el criterio; `p95_e2e` va al README junto al presupuesto de C16.** La instrumentación ya existe: el orquestador emite `latency_ms` por etapa.

**Higiene:** se descarta la primera ejecución y se toman 3 por consulta. Con 144 muestras un p95 significa algo; con 48 es la tercera peor muestra y es ruido.

*Absorbe los dos pendientes de C21 §12:* latencia real de la rama léxica dentro del orquestador y efecto del singleton del cliente de embeddings sobre el p95 en frío y en caliente.

### D13 · Cambio de defaults bajo regla escrita antes de medir

```
 Se cambia un default de Settings si y sólo si:
   · delta de nDCG@5 > 0,05, Y
   · mismo signo en las tres lecturas de D4, Y
   · ninguna de las 7 categorías medibles empeora más de 0,05.
```

Candidatos: `JPV_RRF_WEIGHT_VECTOR` y `JPV_BRANCH_DEPTH`. **No** se toca el umbral de distancia (D8).

*Razón:* es para lo que se construyeron los knobs como parámetros; el cambio es una línea, reversible por variable de entorno, sin migración y sin mover el contrato. El barrido es **direccional**: la rúbrica de C21 infravalora la rama vectorial por construcción, así que el óptimo verdadero está en `wC ≥ 0,33`, nunca por debajo.

*Y la regla escrita antes evita el ajuste post hoc*, que con un intervalo de ±0,13 sería exactamente el ruido que S10 advierte que no se persiga.

### D14 · Contención del sesgo: la matriz de trazabilidad es código, no buena intención

Si el golden set se etiqueta con el sesgo de la rúbrica de C21, **confirmará C21 por construcción y el change no habrá arbitrado nada**. La contención es una validación que hace **fallar la carga** del golden set:

| Requisito | Mínimo |
|---|---:|
| Consultas con ≥1 grado 2 cuyo `doc_text` no contiene ningún término tras `expand_query` | 12 |
| Consultas que resuelven a `occasion_tags` o `style_tags` y a ningún campo de cobertura alta | 5 |
| Consultas que nombran un valor de `stone_type` sin que `piece_type` discrimine | 4 |
| Cobertura de los 3 tipos del diccionario: stemmer · comercial · puente direccional | 6 |
| Consultas plausibles en dominio con cero documentos de grado ≥1 | 5 |
| Consultas que son un SKU o un nombre literal | 4 |

Y anclaje a productos reales **por categoría**, no globalmente: una categoría íntegramente sintética no sería comparable en el desglose por origen.

## Risks / Trade-offs

| Riesgo | Mitigación |
|---|---|
| **El golden set nace con el sesgo de la rúbrica de C21** y confirma a C21 por construcción | D14: la matriz se valida por código y la carga falla si no se cumple. Etiquetar **antes** de mirar los resultados de C21 |
| **El desempate no determinista** hace que el test de reproducibilidad pase en verde mientras el arnés produce ruido | D2: dos líneas y un test que lo demuestra sobre puntuaciones empatadas. Es el mismo patrón que C23 sufrió con su constante compartida |
| **Lo no juzgado cuenta 0** y el daño es **diferido**: explota en C25 cuando `v3-señales` promueva documentos sin juicio | D7: juicios apendables por `(query_id, product_id)` y `unjudged@5` reportado |
| **Fatiga del anotador único** en ~3 h de etiquetado | Tres sesiones de ~1 h agrupadas por categoría; relectura diferida de las dudosas |
| **El etiquetador escribió parte del corpus** (764 sintéticos de C06b) | Irreducible. Se declara en el README; el sesgo es el mismo en todas las filas, que es lo que salva la comparación |
| **El conjunto es pequeño**: ±0,13 sobre la porción real | Declarado por delante. Si la porción real baja de 20 consultas, el criterio se declara **no concluyente** en vez de darse por cumplido o incumplido |
| **Tres ejecuciones concurrentes agotarían el pool** capado a 5, que se comparte con la ruta viva | Las configuraciones se ejecutan **en serie**, nunca en paralelo |
| **El criterio `p95 < 500 ms` leído a una sola columna** entregaría un rojo que no es del change | D12: dos columnas, y el criterio se aplica a la del recuperador |
| **`v0-cag` no es reproducible** ni con temperatura 0 | Es una medición fechada con su modelo, no una fila que se re-ejecute en cada run. Declarado en el informe |
| **Zona compartida** con C25 y C26 en `retrieval/` | Limitada a dos claves de `ORDER BY`. C38 comparte el runner, no el fichero |

## Migration Plan

1. **Verificar el entorno y parar si falla** (§ Open Questions resueltas / precondiciones): contenedor en el 5433 con los 1.168 documentos, `JPV_EMBEDDING_API_KEY` operativa, `SSL_CERT_FILE` apuntando al PEM de raíces de Windows concatenado con `certifi`.
2. **Revisión de Alembic** aditiva con las tres tablas. Ninguna tabla existente se altera; el `downgrade` las elimina y no deja rastro.
3. **Desempate** en `retrieval/search.py` con su test, antes de construir el *pool*: un *pool* construido sobre listas no deterministas no sería reproducible.
4. **Congelar los vectores** de las 48 consultas contra el proveedor real, una sola vez.
5. **Construir el *pool*** ejecutando las cuatro configuraciones indexadas, y **etiquetar en tres sesiones**.
6. **Ejecutar el barrido**, aplicar la regla de D13 y escribir el informe.

**Rollback.** El arnés es aditivo: borrar el paquete y revertir la migración deja el sistema exactamente como estaba. Los dos puntos con efecto sobre la ruta viva tienen reversión propia — el desempate es una revocación de dos líneas, y un default cambiado se revierte por variable de entorno sin desplegar.

## Open Questions

Las seis preguntas abiertas del ticket **quedan cerradas en sus opciones por defecto**. Se registran aquí con su resolución para que el apply no vuelva a abrirlas.

| # | Pregunta | Resolución |
|---|---|---|
| 1 | Modelo para `v0-cag` | **`gpt-4o-mini` vía `JPV_RAG_LLM_*`**, temperatura 0, registrando modelo y fecha en el informe. No se introduce ninguna dependencia ni configuración nueva |
| 2 | Precios de `pricing.yaml` | **Verificar contra `https://openai.com/api/pricing/`** y sellar `as_of` con la fecha de la corrida. **Si la fuente no es accesible, se registra `as_of: unknown` y el coste se declara no verificado** en el informe, en vez de copiar cifras de memoria |
| 3 | Fila escopada por punto de venta | **Recortable declarado, fuera de alcance.** El README dice que el coste del prefiltro en recall queda sin medir. Si más adelante entra, se ejecuta contra un POS nombrado excluyendo `HT-ARTRUTX`, que tiene surtido cero y responde 503 |
| 4 | Tamaño real de la porción real (estimado ~25-30) | Si baja de 20 consultas, **el criterio de aceptación sobre la porción real se declara no concluyente** en el informe |
| 5 | Nombre de la capability | **`retrieval-evaluation`**, coherente con `vector-retrieval`, `hybrid-fusion` y `query-expansion`, y con sitio para las métricas de generación de C38 |
| 6 | ¿Se persisten los runs sin coste? | **Sí.** Una tabla de ablations a la que le faltan las filas de referencia no es una tabla de ablations |

**Lo que queda genuinamente abierto**, y se resuelve midiendo, no decidiendo:

- **¿Tiene el corpus de productos un hueco limpio de distancias entre grado 2 y grado 0?** Si lo tiene, C25 fija un escalar como hizo C23; si no, queda demostrado que hace falta un cuantil por consulta.
- **¿Se dispara la regla de D13?** El barrido es direccional y el resultado se documenta se muevan los defaults o no.
- **¿`stone_type` debe contar para la coordinación?** Las cuatro consultas de piedra existen para responderlo. Si el resultado es concluyente, la decisión se traslada a `hybrid-fusion` en un change posterior; C24 sólo aporta la evidencia.
