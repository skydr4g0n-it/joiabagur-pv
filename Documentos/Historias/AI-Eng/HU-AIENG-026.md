# HU-AIENG-026: Sustitutos por falta de stock — cerrar el 501 del contrato con un recuperador que explica por qué propone cada pieza

## Formato estándar

**Como** operador de un punto de venta,
**quiero** que, cuando la pieza que el cliente ha elegido no se le pueda vender, el sistema me proponga **piezas intercambiables del mismo tipo**, ordenadas por parecido real y **diciéndome por qué** propone cada una,
**para** no perder la venta ni tener que buscar a mano en un catálogo de 1.200 referencias delante del cliente.

---

## Descripción

El sistema ya sabe buscar. Lo que no sabe es **qué ofrecer cuando la respuesta correcta no está
disponible**, y ése es el momento en el que el mostrador pierde la venta.

`POST /v1/retrieval/substitutes` **existe en el contrato congelado desde C02** y hoy responde
**501** fuera de modo stub ([`deps.require_stub_mode`](../../../ai-service/src/jbg_ai/api/deps.py)).
Es el único agujero de ese tipo que queda cerrable: `/v1/inventory/propose` también responde 501,
pero su rama se anuló el 2026-08-31 y eso ya está declarado. Cerrar éste es, además, lo que hace
real la tool `buscar_sustitutos` del agente de venta de C32 — y el diseño ya escribió la regla:
*«una tool que devuelve error es peor que una tool ausente»*.

### La diferencia con la búsqueda, que es toda la historia

No es «otra búsqueda». Es **la misma búsqueda con el filtro que sólo se puede escribir cuando ya
sabes qué pieza ha fallado**:

| | `/v1/retrieval/products` (C14/C21/C25) | `/v1/retrieval/substitutes` (esta historia) |
|---|---|---|
| **Ancla** | **texto**: lo que el cliente describió | **`product_id`**: la pieza que el cliente ya eligió |
| **Pregunta** | *¿qué encaja con lo que describe?* | *ésta no se la puedo vender: ¿qué le enseño?* |
| **Lo que sabes del objetivo** | lo que se infiera de la prosa | **exactamente**: tipo, talla, materiales, banda de precio |
| **Coste por llamada** | embedding del proveedor, 170-1707 ms | **cero** — el embedding de origen ya está guardado |

Cuando el ancla es texto hay que *adivinar* que el cliente quería una talla M de plata. Cuando el
ancla es `SKU13`, se **sabe**. Todo el valor está ahí, y es honesto decir que la mitad vectorial es
la misma maquinaria: lo que esta historia añade son **restricciones y explicación**, no un motor
nuevo. Por eso **no llama al proveedor, no tiene rama léxica, no expande sinónimos y no fusiona**:
es **una sola consulta SQL** sobre un embedding ya almacenado.

### Lo que la exploración midió, y los dos puntos de la ficha que refuta

Medido contra el Postgres local el 2026-09-12, sobre los 1.168 documentos vivos y los cuatro
productos origen de las consultas que el golden set dejó reservadas.

**Primero: la ficha dice «misma familia primero» y la medición dice que eso lidera con los peores
candidatos.** La familia es, por construcción, el conjunto de piezas que se diferencian **justo en
el atributo que descalifica** — la talla. Vecinos por coseno de `SKU13 Anillo erizo de mar M`:

| # | candidato | dist | familia | mismo tipo | misma talla |
|---:|---|---:|:---:|:---:|:---:|
| 1 | Anillo erizo de mar **L** | 0,0868 | ✅ | ✅ | ❌ |
| 2 | Anillo erizo de mar **S** | 0,0908 | ✅ | ✅ | ❌ |
| 3 | Anillo Erizo de mar **XL** | 0,1229 | ✅ | ✅ | ❌ |
| 4 | **Colgante** erizo de mar M | 0,1306 | ❌ | ❌ | ✅ |
| 5 | Anillo Erizo oro **S** | 0,1375 | ❌ | ✅ | ❌ |
| **6** | **Anillo oreja de mar M** | 0,1535 | ❌ | ✅ | ✅ |

**El top-5 del vector puro no contiene ni un sustituto usable.** Un anillo que no entra no es una
segunda opción: es invendible. Y el vector además **viola el tipo de pieza** (#4 es un colgante).

**Segundo: pero la familia no se puede excluir.** El mejor sustituto de `SKU159 Anillo lapislázuli
mediano` es el **#1 y es de su familia**: `Anillo lapislázuli mediano oro` — **misma talla, otro
material**. Ése es el patrón de sustituto ideal, y una regla que excluyera la familia lo perdería.

> **La pertenencia a familia es ortogonal.** El discriminante real es **la talla**, y cruza la
> frontera de la familia en las dos direcciones.

**Tercero, y lo confirma el criterio de etiquetado que el proyecto ya tenía escrito.**
[`criterion.md`](../../../ai-service/evals/golden/criterion.md) define el grado **1** como *«falla
UN atributo que la consulta nombró explícitamente (**talla**, uno de varios materiales, color,
piedra)»*. Una talla distinta **ya estaba clasificada como segunda opción, no como respuesta**. La
rúbrica de anotación coincide con la medición y discrepa de la ficha.

**Cuarto: el peso de la degradación por talla, simulado y no argumentado.** Con `sim = 1 − coseno`:

| origen | `w = 0` (vector puro) | **`w = 0,05`** | `w = 0,08` |
|---|---|---|---|
| `SKU13` anillo **M** | L, S, XL, oro S, **oreja M**⁵ | L, S, **oreja M**³, **estrella M**⁴, XL | **oreja M**¹, **estrella M**², L³ |
| `SKU77` colgante **S** | L, M, XS, **oreja S**⁴, **S oro**⁵ | **oreja S**¹, **S oro**², L³, **mejillón S**⁴ | **oreja S**¹, …, M⁸, XS¹⁰ |
| `SKU159` anillo **mediano** | **mediano oro**¹ | sin cambios | sin cambios |

`0,02` apenas mueve nada; `0,08` manda la `M` de `SKU77` al puesto 8, que ya es «a la cola».
**`0,05` interleava**: los de talla correcta suben al top-4 y el hermano de otra talla **sigue
visible en el top-5**. Es la degradación *suave* que el negocio pidió.

**Quinto: `style_similarity` es un campo requerido del contrato cuyo dato no existe.** Contando
cuántos productos tienen **algún candidato del mismo tipo con el que compartir etiqueta**:

| origen | productos | por **material** | por **estilo** |
|---|---:|---:|---:|
| **real** | 404 | **395 — 97,8 %** | **1 — 0,2 %** |
| sintético | 764 | 646 — 84,6 % | 122 — 16,0 % |

`material_overlap` es sólido. `style_similarity` como Jaccard de `style_tags` sería **0,0 para 403
de 404 productos reales**, por construcción.

**Sexto: no hay abstención posible, y está medido.** Distancia al vecino más próximo, muestra de
300: con familia mediana **0,049** y máximo 0,123; sin familia mediana **0,121** y máximo
**0,255**. **Todo producto del catálogo tiene algún vecino a menos de 0,255**, y el rango de «sin
familia» contiene el de «con familia» — la misma firma de contención que C25 encontró al intentar
re-fijar su umbral escalar. En un catálogo de 1.168 piezas de joyería marina menorquina, todo se
parece a algo.

Detalle completo y SQL reproducible en
[`c26-exploration-measurements.md`](../../Proyecto%20Final%20AIEng/informes/c26-exploration-measurements.md).

### Alcance de esta historia (sí)

1. **Módulo nuevo `retrieval/substitutes.py`** que implementa `POST /v1/retrieval/substitutes`
   contra `ai.product_document`, retirando el stub y el `require_stub_mode` de esa ruta.
2. **Filtro duro por `piece_type`** y exclusión de la propia pieza origen.
3. **Orden por similitud vectorial** sobre el embedding almacenado, **sin llamada al proveedor**.
4. **Degradación suave y continua por talla distinta** (`w ≈ 0,05`, configurada y barrida), que
   **sólo se activa cuando ambas piezas declaran talla**.
5. **Degradación por disponibilidad** reutilizando `business_score` de C25 — que **degrada y nunca
   excluye** —, con sobre-recuperación para que .NET pueda filtrar después.
6. **Señales por candidato**: `material_overlap` (Jaccard de `materials`), `style_similarity`
   (Jaccard de `style_tags`), `family_match` y `visual_similarity = null`.
7. **`match_reasons` como vía de explicación**, incluida la talla —que el contrato congelado no
   puede expresar— y la ausencia de etiquetas de estilo.
8. **Cinco consultas del golden set ancladas con `source_product_id` explícito** y evaluadas en
   **rebanada separada**, con informe propio.
9. **Specs delta** de la capability y documentación: README del servicio, plan, épicas e informe de
   implementación.

### Fuera de alcance (no)

1. **Excluir por stock en Python.** Lo cubre `Substitutes_ExcludeProductsWithoutStockAtTargetPos`
   en C34, que es donde vive la autoridad sobre el stock.
2. **Mover `ai-service/openapi.json`.** El contrato ya contiene la ruta y los esquemas.
3. **Migraciones de Alembic o de EF Core**, reindexado o cambio del modelo de datos.
4. **Diff en `backend/`, `frontend/`, `terraform/` o `.github/workflows/`.**
5. **Tocar la tabla de ablations publicada de C24/C25**, sus configuraciones o sus juicios.
6. **Complementarios.** C27 se cortó el 2026-09-12 con cinco mediciones
   ([`c27-cut-measurements.md`](../../Proyecto%20Final%20AIEng/informes/c27-cut-measurements.md)).
7. **Corregir la familia contaminada de `SKU77`**, que contiene el sintético `SKU610`. Se deja y se
   observa: corregir familias es de C28.
8. **Deduplicar contra el bloque de variantes de la card.** El endpoint es autocontenido; la
   deduplicación de presentación es de C36.
9. **Llamar al proveedor de embeddings** por cualquier vía.
10. **Cerrar las tres brechas que C25 dejó declaradas** (`Recall@5` 0,758, abstención 0,150,
    `v3` sin batir a `v2b` por el margen).

### Decisiones de diseño ya acordadas

| # | Decisión | Razón corta |
|---|---|---|
| **D1** | **Python nunca excluye por stock**: degrada, declara y sobre-recupera; **.NET filtra** | El §15.10 del diseño y el contrato de `ports.py` ya lo fijan: la proyección puede desfasarse minutos, y `pos_id` restringe mientras `signal_pos_id` sólo lee. El propio `SubstitutesRequest.top_k` está documentado como *«la página que .NET quiere **después** de hidratar y filtrar»*. La exclusión ya estaba asignada a C34 |
| **D2** | **Filtro duro por `piece_type`** · la familia **entra en el conjunto pero no impone orden** · **degradación suave y continua por talla**, sólo si ambas piezas la declaran | Medido: «familia primero» lidera con los invendibles en 3 de 4 casos y expulsa a `SKU39`, mejor sustituto que media familia; pero excluir la familia perdería el #1 de `SKU159`. Y el vector viola el tipo de pieza en 2 de 4 |
| **D2b** | El término de talla es un **score continuo en la cola**, **nunca un bloque entero** | Un bloque entero manda a la cola por construcción. C25 midió ese fallo con la rotación: 11.067 pares invertidos, el 71,2 % a más de diez puestos. Su solución —cuarto entero convertido en score continuo— es la forma que aquí se reutiliza |
| **D2c** | La ausencia de talla **no es desajuste de talla** | El 54 % de los anillos no tiene `size_label`. Penalizar a un candidato por *tener* talla cuando el origen no la tiene es tratar la ausencia como valor, y `ports.py` ya prohíbe eso por escrito para las señales de negocio |
| **D3** | Las consultas reservadas se anclan con **`source_product_id` explícito** y se evalúan en **rebanada separada** | El endpoint recibe `product_id` y las consultas son texto. Resolver el texto primero mediría **la cadena**, que es de C32, e imputaría a esta historia el fallo del primer paso. Y añadir filas a la tabla publicada movería su denominador |
| **D4** | `style_similarity` = Jaccard de `style_tags`, con la **ausencia declarada en `match_reasons`** | Un `0,0` que significa «no hay dato» es el fallo que el proyecto tiene nombrado. Derivarlo del embedding lo convertiría en una copia de `score`: la segunda definición que diverge, que es por lo que se anuló C19 |
| **D5** | **No abstiene**; `low_confidence` se emite `false` con el motivo escrito | Todo producto tiene vecino a < 0,255 y los rangos se contienen. Se declara por **decisión medida**, no por aplazamiento — el precedente exacto de C25 con su umbral escalar |
| **D6** | **Módulo nuevo `substitutes.py`**; reutiliza `business_score`, `OUT_OF_STOCK_BUCKET`, `projection` y `ports`. **No** reutiliza `demotion_rank` ni `fuse` | El orquestador ya tiene ~870 líneas y cinco responsabilidades. Y con **una sola lista** no hay nada que fusionar: el docstring de `fusion.py` que predice *«C26 is the next caller»* queda corregido |
| **D7** | Endpoint **autocontenido**: incluye la familia, porque `buscar_sustitutos` se llama sin la card delante | La deduplicación contra el bloque de variantes es de presentación y pertenece a C36 |

### Referencias

- Change: [`add-substitutes-retrieval`](../../../openspec/changes/archive/2026-09-12-add-substitutes-retrieval/) · rama `c26-add-substitutes-retrieval`
- Mediciones: [`c26-exploration-measurements.md`](../../Proyecto%20Final%20AIEng/informes/c26-exploration-measurements.md)
- Plan de changes: [`proyecto-final-plan-changes-openspec.md`](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md), ficha C26
- Diseño RAG: [`proyecto-final-diseno-rag-joiabagur.md`](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) §4 (fila 6, **Núcleo**), §6.2, §7.6, §15.10
- Especificaciones funcionales v2 §6.3.2 — criterios de similitud
- Specs vivas afectadas: [`vector-retrieval`](../../../openspec/specs/vector-retrieval/spec.md) · [`hybrid-fusion`](../../../openspec/specs/hybrid-fusion/spec.md) · [`pos-projection`](../../../openspec/specs/pos-projection/spec.md) · [`retrieval-evaluation`](../../../openspec/specs/retrieval-evaluation/spec.md) · [`business-signals-ranking`](../../../openspec/specs/business-signals-ranking/spec.md)
- Contrato congelado: [`ai-service/openapi.json`](../../../ai-service/openapi.json), ruta `/v1/retrieval/substitutes`
- Historias previas: [HU-AIENG-022](HU-AIENG-022.md) (proyección por POS) · [HU-AIENG-024](HU-AIENG-024.md) (arnés y golden set) · [HU-AIENG-025](HU-AIENG-025.md) (fusión y señales)

---

## Criterios de Aceptación

### Escenario 1: El endpoint deja de responder 501 y devuelve sustitutos reales

- **Dado que** el servicio corre con el modo stub desactivado,
- **cuando** se pide `POST /v1/retrieval/substitutes` con el identificador de un producto indexado,
- **entonces** la respuesta es `200` con candidatos reales del catálogo indexado,
- **y** cada candidato lleva sus señales de similitud y sus motivos,
- **y** ya no existe ninguna ruta que responda 501 remitiendo a esta historia.

### Escenario 2: Nunca propone una pieza de otro tipo

- **Dado que** la pieza origen es un colgante,
- **cuando** se piden sus sustitutos,
- **entonces** ningún candidato devuelto es de un `piece_type` distinto,
- **y** esto se cumple aunque la similitud vectorial coloque una pieza de otro tipo por delante.

### Escenario 3: La pieza origen nunca es su propio sustituto

- **Dado que** se piden los sustitutos de una pieza,
- **cuando** se examina la respuesta,
- **entonces** esa misma pieza no aparece entre los candidatos.

### Escenario 4: Ninguna variante viva de la familia se pierde

- **Dado que** la pieza origen pertenece a una familia con otros miembros activos,
- **cuando** se piden sus sustitutos con la ventana de sobre-recuperación por defecto,
- **entonces** todos los miembros activos de esa familia están presentes en el conjunto devuelto,
- **y** cada uno lleva `family_match` verdadero,
- **y** su posición la decide el orden general y **no** su pertenencia a la familia.

### Escenario 5: Un candidato de la misma talla supera a un hermano de familia de talla distinta

- **Dado que** la pieza origen declara una talla y su familia tiene miembros de otras tallas,
- **y** existe fuera de la familia un candidato del mismo tipo y de la **misma** talla,
- **cuando** se piden los sustitutos,
- **entonces** el candidato de la misma talla queda por delante de al menos un hermano de familia de
  talla distinta,
- **y** ese hermano **sigue apareciendo** dentro de la ventana visible, no al final de la lista,
- **y** el motivo de su posición está declarado en sus `match_reasons`.

### Escenario 6: La ausencia de talla no se trata como desajuste de talla

- **Dado que** la pieza origen no declara talla, o el candidato no la declara,
- **cuando** se calcula el orden,
- **entonces** el término de talla no resta nada a ese candidato,
- **y** el orden coincide exactamente con el que produciría el mismo cálculo sin ese término.

### Escenario 7: El solape de materiales sube la puntuación

- **Dado que** dos candidatos tienen similitud vectorial equivalente y el mismo estado de talla,
- **cuando** uno comparte material con la pieza origen y el otro no,
- **entonces** el que comparte material queda por delante,
- **y** su `material_overlap` es mayor que cero y el del otro es cero.

### Escenario 8: La disponibilidad degrada y nunca elimina

- **Dado que** la petición llega con un punto de venta en el token y la proyección marca a un
  candidato como agotado,
- **cuando** se piden los sustitutos,
- **entonces** ese candidato **sigue presente** en la respuesta, por debajo de sus pares disponibles,
- **y** la respuesta declara la antigüedad de la proyección,
- **y** ninguna pieza se elimina por razones de stock.

### Escenario 9: No abstiene, y lo dice

- **Dado que** la pieza origen es una referencia sin familia y sin equivalentes obvios,
- **cuando** se piden sus sustitutos,
- **entonces** la respuesta trae candidatos y `low_confidence` es falso,
- **y** la documentación declara que este endpoint **no abstiene por decisión medida**, con la
  distribución de distancias que lo justifica.

### Escenario 10: Una señal sin dato se declara en vez de fingirse

- **Dado que** ni la pieza origen ni el candidato tienen etiquetas de estilo,
- **cuando** se devuelve el candidato,
- **entonces** `style_similarity` vale cero,
- **y** sus `match_reasons` declaran explícitamente que no había etiquetas de estilo que comparar,
- **y** ese cero nunca puede leerse como «estilos distintos».

### Escenario 11: No se llama al proveedor de embeddings

- **Dado que** el embedding de la pieza origen ya está almacenado en el índice,
- **cuando** se atiende una petición de sustitutos,
- **entonces** no se realiza ninguna llamada al proveedor de embeddings ni a ningún LLM,
- **y** un doble del cliente de embeddings que falle al ser invocado no rompe la petición.

### Escenario 12: La pieza origen tiene que estar en el índice

- **Dado que** se pide sustitutos de un identificador que no existe en el índice, o que está
  inactivo, o que no tiene embedding,
- **cuando** se atiende la petición,
- **entonces** la respuesta es un error explícito que nombra la causa,
- **y** no se devuelve una lista vacía con apariencia de respuesta válida.

### Escenario 13: La evaluación entra por su propia rebanada

- **Dado que** el golden set tiene consultas de sustituto declaradas sin juicios,
- **cuando** esta historia las etiqueta y las mide,
- **entonces** cada una queda anclada a un producto origen explícito,
- **y** su informe es una rebanada propia con sus métricas,
- **y** la tabla de ablations publicada de C24/C25 **no cambia ni una cifra**,
- **y** el conjunto cubre al menos un producto origen **sin familia**.

### Escenario 14: Fuera de alcance explícito

- **Dado que** esta historia vive dentro del servicio de IA,
- **cuando** se revisa el diff completo,
- **entonces** el snapshot del contrato queda sin cambios y no hay migración,
- **y** no hay diff en `backend/`, `frontend/`, `terraform/` ni en los flujos de CI,
- **y** no se ha modificado ningún peso calibrado por C25, ni el golden set existente, ni las
  configuraciones supervivientes.

---

## Notas adicionales

- **Actor**: el operador, indirectamente. Esta historia no entrega superficie de usuario — la card
  que la hace visible es C36, y el endpoint .NET que la hidrata es C34. Lo que entrega es la
  capacidad y su medida.
- **Prerrequisitos, ambos cumplidos**: C22 (proyección por punto de venta, archivado el 2026-09-05)
  y C25 (fusión y señales, archivado el 2026-09-12).
- **Está en la cadena crítica** `C26 → C34 → C36`, y es lo único que queda en ella tras el corte de
  C27. Desbloquea también la tool `buscar_sustitutos` de C32.
- **La zona real es mayor que la de la ficha**: además de `retrieval/` toca `evals/` y
  `evals/golden/`. Es la **decimocuarta vez** que la zona de una ficha se queda corta en este plan.
- **Limitación conocida y declarada**: `style_similarity` es prácticamente cero sobre catálogo real
  (1 de 404 productos tiene etiqueta de estilo). El README debe declararlo, y la señal útil es
  `material_overlap`, que cubre el 97,8 %.
- **Limitación conocida y aceptada**: la familia `Colgante estrella de mar` contiene el producto
  sintético `SKU610` y tiene variantes «dorado» partidas en una segunda familia, con `SKU91`
  huérfano. Se deja como está a propósito, para ver cómo se comporta la contaminación; bajo la
  degradación por talla el contaminante además se hunde solo.
- **Limitación conocida**: la medición aísla la calidad del sustituto **dado el producto origen
  correcto**. La cadena completa «texto del operador → producto → sustitutos» es de C32 y se mide
  allí.
- **Tentación que el diseño convierte en fallo**: hacer que la talla sea un bloque entero «porque es
  más fácil de testear». C25 ya midió a dónde lleva eso.
- **Change de OpenSpec por el que se implementa**:
  [`add-substitutes-retrieval`](../../../openspec/changes/archive/2026-09-12-add-substitutes-retrieval/), sobre la rama
  `c26-add-substitutes-retrieval`.

---

## Tareas

1. **Puerta de entrada**: registrar la línea base de la suite por **nombres** de test en rojo, no
   por recuento, y confirmar la huella del índice y la versión del golden set.
2. **Consulta de candidatos** en `retrieval/search.py`: k-NN sobre el embedding almacenado de la
   pieza origen, con filtro duro por `piece_type`, exclusión de la propia pieza y lectura de la
   proyección por punto de venta como **señal** y nunca como restricción.
3. **Módulo `retrieval/substitutes.py`**: orquestación de la petición, composición del orden
   —similitud, término de talla, término de disponibilidad— y construcción de las señales.
4. **Término de talla**: score continuo en la cola de la clave, inerte cuando alguna de las dos
   piezas no declara talla, con el peso leído de configuración.
5. **Señales y motivos**: `material_overlap`, `style_similarity`, `family_match`,
   `visual_similarity` nulo, y `match_reasons` con talla, material, familia y la declaración de
   ausencia de etiquetas de estilo.
6. **Router**: retirar `require_stub_mode` y el stub de esa ruta, conectando la implementación real
   y conservando el comportamiento en modo stub para los tests de contrato.
7. **Ajustes**: añadir el peso de talla a `Settings` como valor opcional al arranque, con su valor
   por defecto y su documentación.
8. **Corregir el docstring de `fusion.py`**, que predice que esta historia sería su siguiente
   consumidora y no lo es.
9. **Golden set**: anclar las cuatro consultas de sustituto con su producto origen, **añadir una
   quinta sin familia**, etiquetar por pooling y registrar el criterio aplicado.
10. **Rebanada de evaluación**: ejecutar la medición de sustitutos, barrer el peso de talla y
    publicar informe propio, sin tocar la tabla publicada.
11. **Tests**: los siete escenarios nuevos más los de perímetro y los de contrato.
12. **Verificar el perímetro**: contrato sin diff, sin migración, sin diff fuera de `ai-service/`,
    `Documentos/` y `openspec/`, y cero llamadas al proveedor en la ruta.
13. **Specs delta** y `openspec validate --all --strict` en verde.
14. **Documentación**: README del servicio, README de tests, informe de implementación, plan y
    épicas.

---

## Estimaciones y atributos de priorización

| Atributo | Valor |
|---|---|
| Puntos de historia | _Pendiente_ — a fijar en refinamiento |
| Impacto en usuario / valor de negocio | **4/5** — es el momento en el que hoy se pierde la venta. No es visible hasta C36, pero es la capacidad que la hace posible |
| Urgencia | **4/5** — único eslabón vivo de la cadena crítica `C26 → C34 → C36`, y desbloquea la tool `buscar_sustitutos` de C32 |
| Complejidad / esfuerzo | **2/5** — todos los datos están puestos e indexados, no hay migración, no hay contrato que mover y no hay llamada al proveedor. Lo caro no es el recuperador: es etiquetar y medir |
| Riesgos | Que el término de talla se implemente como bloque entero y mande los hermanos a la cola (mitigado por el Escenario 5, que exige que sigan visibles); que `style_similarity` se derive del embedding y se convierta en una copia de `score`; que la rebanada de evaluación contamine la tabla publicada (Escenario 13); que el etiquetado de las cinco consultas lo haga la misma persona que diseñó el orden, sesgo que el README ya declara para el golden set entero |
| Dependencias | **C22** y **C25**, ambos archivados. Bloquea a **C34** (y con él a C36) y a la tool `buscar_sustitutos` de **C32** |
