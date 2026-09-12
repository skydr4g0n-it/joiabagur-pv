## Context

El recuperador de catálogo está completo y medido: expansión de consulta (C20), fusión híbrida en
dos etapas (C21 + C25), prefiltro por punto de venta (C22), señales de negocio y abstención relativa
(C25), y un arnés con golden set de 71 consultas (C24). Lo que no existe es la respuesta a *«esta
pieza no se la puedo vender: ¿qué le enseño?»*.

La ruta `POST /v1/retrieval/substitutes` está en el contrato congelado desde C02 con sus modelos
—`SubstitutesRequest`, `SubstituteResult`, `SimilaritySignals`, `SubstitutesResponse`— y devuelve
**501** por una obligación explícita de la spec viva `vector-retrieval`.

**Estado del árbol, comprobado y no recordado** (2026-09-12, `d825a8d`, 1.168 documentos vivos):

| Pieza | Medido |
|---|---|
| `embedding` en `ai.product_document` | **1.168 de 1.168**, índice HNSW `vector_cosine_ops` |
| `family_id` | 491 (42,0 %) · 156 familias de 2 a 8 miembros |
| `materials` | 1.046 (89,6 %), índice GIN |
| `price_band` | 1.168 (100 %) |
| `style_tags` | 131 (11,2 %) · **1 de 404 productos reales** tiene par del mismo tipo con el que compartir etiqueta |
| `size_label` | 46 % de los anillos, 51 % de los pendientes, 53 % de los colgantes |
| `ai.pos_projection` | 6.720 filas |

La consecuencia que gobierna el coste: **sustituto es producto→producto**, el embedding de origen ya
está almacenado, y por tanto la capacidad se entrega **sin llamada al proveedor, sin rama léxica, sin
expansión y sin fusión** — una sentencia SQL.

## Goals / Non-Goals

**Goals:**

- Que `POST /v1/retrieval/substitutes` devuelva candidatos reales, explicables y ordenados por una
  regla que el golden set pueda medir.
- Que el orden refleje lo que un mostrador necesita: **la talla que el cliente pidió manda sobre el
  parecido del diseño**, sin desterrar las variantes de la misma pieza.
- Que ninguna variante viva de la familia pueda perderse, aunque no encabece.
- Que cada candidato diga **por qué** está ahí, incluido lo que el contrato congelado no puede
  expresar.
- Que una señal sin dato se declare en lugar de emitir un cero que miente.
- Que la capacidad se mida sin tocar la tabla de ablations publicada.

**Non-Goals:**

- **Excluir por falta de stock.** Es de C34, donde vive la autoridad sobre el stock.
- **Mover `ai-service/openapi.json`.** La ruta y los esquemas ya están.
- **Migraciones**, reindexado o cambios en el modelo de datos.
- **Llamar al proveedor de embeddings o a un LLM** por cualquier vía.
- **Corregir familias contaminadas.** Es de C28; aquí se observan.
- **Deduplicar contra el bloque de variantes de la card.** Es de C36.
- **Complementarios.** C27 se cortó el 2026-09-12 con cinco mediciones.
- **Cerrar las tres brechas declaradas por C25.**

## Decisions

### D1 · La disponibilidad degrada y nunca elimina; la exclusión por stock es de .NET

La ficha del plan pedía una bandera que excluyera lo agotado. Choca de frente con el invariante mejor
argumentado del sistema: la proyección puede desfasarse minutos, y por eso `pos_id` **restringe por
surtido** (`is_assigned_hint`) mientras el stock **sólo se lee** y nunca elimina.

Lo decisivo es que **la exclusión ya estaba asignada, y a .NET**: la ficha de C34 lleva el test
`Substitutes_ExcludeProductsWithoutStockAtTargetPos`. Estaba especificada dos veces, y la versión de
.NET es la que respeta la frontera *«Python calcula parecidos; .NET calcula números y decide»*. El
contrato congelado ya lo previó: `top_k` está documentado como la página que .NET quiere **después**
de hidratar y filtrar, así que el recuperador sobre-recupera y lo declara.

**Alternativas descartadas:** excluir en Python (rompe el invariante y oculta piezas vendibles con
proyección vieja); bandera con valor por defecto (una perilla que nadie mide, y C25bis acaba de
retirar tres por ser trampas).

### D2 · La familia entra en el conjunto pero no impone orden

La ficha pedía *«misma familia primero»*. Medido sobre los cuatro productos origen del golden set, ese
orden lidera con los candidatos invendibles, porque **la familia es el conjunto de piezas que se
diferencian justo en el atributo que descalifica**:

```
  SKU13 «Anillo erizo de mar M» — vecinos por coseno, sin reglas

  #1  Anillo erizo de mar L     familia ✅  tipo ✅  TALLA ❌
  #2  Anillo erizo de mar S     familia ✅  tipo ✅  TALLA ❌
  #3  Anillo Erizo de mar XL    familia ✅  tipo ✅  TALLA ❌
  #4  Colgante erizo de mar M   familia ❌  TIPO ❌  talla ✅
  #6  Anillo oreja de mar M     familia ❌  tipo ✅  talla ✅   ← el primero usable
```

Pero excluir la familia perdería el mejor caso: el #1 de `SKU159` es su hermano `mediano oro`,
**misma talla y otro material**. La pertenencia a familia es **ortogonal**; el discriminante es la
talla. Y `criterion.md` ya lo decía: fallar la talla nombrada es **grado 1**, segunda opción.

**Lo que se garantiza en su lugar** es recall: ninguna variante viva de la familia puede quedar fuera
del conjunto devuelto, y `family_match` la declara. El orden lo decide la regla general.

### D3 · El tipo de pieza es el único filtro duro

El vector puro viola el tipo en 2 de los 4 casos medidos: mete un colgante entre los sustitutos de un
anillo y un anillo entre los de un colgante. Un anillo no es una segunda opción para quien quería un
colgante; es otra cosa. El §6.3.2 de las especificaciones funcionales ya le daba peso «alto».

Se implementa como predicado SQL y no como degradación, porque aquí eliminar **no** tiene el riesgo
que tiene con el stock: el tipo de pieza es un atributo del catálogo indexado, no una proyección que
se desfasa.

### D4 · La talla degrada de forma suave, como término continuo, y es inerte sin dato

`demotion_rank` ya tiene degradación por talla, pero como **bloque entero** en la posición 2 de 4. Un
bloque entero manda a la cola por construcción, que es exactamente el fallo que C25 midió con la
rotación —11.067 pares invertidos, el 71,2 % a más de diez puestos—. La forma correcta es la que C25
adoptó al convertir su cuarto entero en score: **un término continuo en la cola**.

Simulado sobre los cuatro orígenes, con la similitud como `1 − distancia`:

| peso | efecto |
|---|---|
| `0,02` | inerte en la práctica |
| **`0,05`** | **interleava**: los de talla correcta entran en el top-4 y el hermano de otra talla sigue **visible dentro del top-5** |
| `0,08` | destierra: la `M` de `SKU77` cae al puesto 8 |

Se adopta `0,05` como valor por defecto **sujeto al barrido** sobre las cinco consultas. El número
sale de la medición, no de esta tabla.

**El término es inerte cuando alguna de las dos piezas no declara talla.** Penalizar a un candidato
por *tener* talla cuando el origen no la tiene es tratar la ausencia como valor, que es lo que
`ports.py` ya prohíbe por escrito para las señales de negocio. No es cosmético: **el 54 % de los
anillos no tiene `size_label`**.

**Advertencia sobre un hallazgo de C25 que no se traslada.** Aquél concluyó que *«el valor del peso no
cambia el orden, sólo su signo»*, cierto **allí** porque el score tomaba dos valores. Aquí la cola
mezcla similitud continua con un término binario, de modo que el peso fija un tipo de cambio real
—cuánta similitud vale una talla equivocada— y el barrido tiene sentido.

### D5 · Una señal sin dato se declara; `match_reasons` es la válvula del contrato congelado

`SimilaritySignals` exige `style_similarity` como campo **requerido y no nulable**, y el dato no
existe: **1 de 404** productos reales tiene con quién compartir etiqueta de estilo. Se emite el
Jaccard —que será cero casi siempre— y **la ausencia se declara en `match_reasons`**, para que ese
cero no pueda leerse nunca como «estilos distintos».

**Alternativa descartada:** derivarlo del coseno del documento. Tendría cobertura del 100 % y sería
una **copia de `score`** — una señal que no explica nada nuevo, y la segunda definición que diverge,
que es el motivo por el que se anuló C19.

Y `match_reasons` resuelve además el hueco estructural: el contrato no puede expresar la **talla**, y
la talla discrimina en 2 de las 4 consultas reservadas.

### D6 · El endpoint no abstiene, y se declara

Distancia al vecino más próximo, muestra de 300: con familia mediana 0,049 y máximo 0,123; sin
familia mediana 0,121 y **máximo 0,255**. **Todo producto tiene vecino a menos de 0,255**, y el rango
de «sin familia» contiene el de «con familia» — la misma contención que impidió a C25 re-fijar su
umbral escalar.

En un catálogo de 1.168 piezas de joyería marina menorquina, todo se parece a algo. Un umbral absoluto
o acepta todo o empieza a rechazar casos buenos. `low_confidence` se emite falso **por decisión
medida**, no por aplazamiento.

Lo que sí existe es el caso degenerado y se trata aparte: **pieza origen inexistente, inactiva o sin
embedding produce un error explícito que nombra la causa**, nunca una lista vacía con apariencia de
respuesta válida — la firma que este proyecto persigue desde C17.

### D7 · Módulo propio, y sin fusión

`orchestrator.py` tiene ~870 líneas y cinco responsabilidades. El flujo de sustitutos es distinto —sin
proveedor, sin rama léxica, sin expansión— así que vive en `substitutes.py`. Reutiliza `business_score`
y `OUT_OF_STOCK_BUCKET` para que la semántica de disponibilidad siga en un solo sitio, y `projection`
y `ports` tal cual. **No reutiliza `demotion_rank`** (D4) **ni llama a `fuse()`**: con una sola lista
no hay nada que fusionar, y el docstring de `fusion.py` que predice lo contrario se corrige.

### D8 · La evaluación se ancla por producto origen y va en rebanada propia

El golden set tiene cuatro consultas de sustituto declaradas sin juicios y con la nota escrita *«La
hereda C26»*. Son **texto**, y el endpoint recibe **`product_id`**.

**Se anclan con un `source_product_id` explícito.** Resolver el texto con el buscador y encadenar
mediría **la cadena**, que es de C32, e imputaría a este change el fallo del primer paso.

**Van en rebanada separada**, con informe propio: el endpoint no atraviesa el mismo arnés —`v0-fts` y
`v1-vectorial` ni siquiera podrían ejecutarlo— y añadir filas movería el denominador de la tabla
publicada por C24 y C25.

**Entra una quinta consulta sin familia**, porque las cuatro reservadas tienen familia y el camino sin
ella es el **58 %** del catálogo. El criterio de etiquetado se reutiliza sin cambios: el grado 1 de
`criterion.md` ya está redactado en términos de sustituto.

## Risks / Trade-offs

| Riesgo | Mitigación |
|---|---|
| **Que la talla se implemente como bloque entero** y destierre a los hermanos al final de la lista. Es el atajo que el código invita a tomar, porque `demotion_rank` ya lo tiene escrito | Un escenario propio exige que el hermano de talla distinta **siga dentro de la ventana visible**, no sólo que el de talla correcta suba |
| **Que `style_similarity` se derive del embedding** por parecer más útil | Escenario que exige la declaración de ausencia en `match_reasons`; el cero es correcto y lo que no puede faltar es su explicación |
| **Que la rebanada de evaluación contamine la tabla publicada** | Escenario que exige que la tabla de C24/C25 no cambie ni una cifra |
| **Que el etiquetado lo haga quien diseñó el orden.** Es real y no se mitiga aquí | Se declara, como el README ya declara la ausencia de acuerdo entre anotadores para el golden set entero |
| **Que la familia contaminada de `SKU77`** (con el sintético `SKU610` dentro y variantes partidas) distorsione una de las cinco medidas | Se deja a propósito y se observa. Bajo D4 el contaminante además se hunde solo, por talla |
| **Que el barrido del peso de talla sobreajuste** a cinco consultas | El peso se declara con su recorrido, y si la diferencia entre candidatos queda bajo el ruido se adopta `0,05` por ser el medido como interleave |
| **Sobre-recuperar poco** y que .NET se quede sin candidatos tras filtrar por stock | Se mantiene la ventana de `retrieve_products` y `candidates_returned` declara lo producido |

**Trade-off aceptado y declarado:** la medición aísla la calidad del sustituto **dado el producto
origen correcto**. La cadena completa «texto del operador → producto → sustitutos» no se mide aquí;
es de C32.
