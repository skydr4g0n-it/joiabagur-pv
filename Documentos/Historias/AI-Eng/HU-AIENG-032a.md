# HU-AIENG-032a: El registro de herramientas del asistente de venta — seis tools que no escriben, y la que no tenía servicio detrás

## Formato estándar

**Como** desarrollador del proyecto,
**quiero** que las seis herramientas del asistente de venta existan como un registro tipado, de solo
lectura y probado sin llamar a ningún proveedor,
**para** que el bucle agéntico de C32b sólo tenga que aportar la capa de decisión, y para que el
invariante de que *ningún agente escribe* sea una propiedad comprobable del código y no una promesa
del documento de diseño.

---

## Descripción

C32 se partió el 2026-09-20 por la regla 5 del §1 del plan de changes, con el mismo corte que
funcionó en C30: **la mitad que no llama a ningún proveedor va primero**. Esta historia es esa
mitad. Entrega las herramientas y el registro; **no entrega el bucle**, que es C32b y que es lo
único que el Proyecto Final evalúa como «capa agéntica».

El corte no es sólo de tamaño. Un registro de herramientas es **medible por sí solo** —cada tool se
prueba contra su puerto sin que nadie decida nada— y deja a C32b una superficie ya en verde sobre
la que montar la única pieza cara: el bucle, sus presupuestos y su ruta.

### El hallazgo que reencuadra el change: la sexta tool no tenía servicio detrás

La ficha del plan enumeraba seis tools y, en el mismo párrafo, invocaba dos veces la regla que
retiró a `perfil_punto_venta` y a `buscar_complementarios`: *«una tool que devuelve error es peor
que una tool ausente — el bucle la reintenta y quema presupuesto»*. Aplicada literalmente a
`consultar_disponibilidad`, esa regla la retira y deja el registro en cinco.

Pero la misma ficha nombra `test_out_of_stock_query_triggers_substitutes_tool`, y **sin señal de
disponibilidad ese test no tiene disparador**: el pivote a sustitutos es el escenario de venta más
característico del dominio y es la razón por la que C26 existe. Las dos frases de la ficha no pueden
ser ciertas a la vez.

Lo que las reconcilia no estaba en la ficha sino en el diseño. El §6.1 dibuja la arista
`R2 -->|tool: consultar_disponibilidad| API` y dice, con todas sus letras, que el esquema de la
llamada de vuelta Python → .NET *«queda como **decisión abierta del change del agente de venta**»*.
Esta historia la resuelve, y la resuelve **difiriéndola con motivo**: no hay que inventar un esquema
de autenticación de vuelta para un dato que Python ya tiene proyectado.

### Estado actual del código, verificado en el repositorio

| Tool | La sirve | Estado | Evidencia |
|---|---|---|---|
| `buscar_catalogo` | `retrieve_products()` | ✅ **existe**, falta el envoltorio | [`retrieval/orchestrator.py`](../../../ai-service/src/jbg_ai/retrieval/orchestrator.py) |
| `buscar_sustitutos` | `retrieve_substitutes()` | ✅ **existe** (C26) | [`retrieval/substitutes.py`](../../../ai-service/src/jbg_ai/retrieval/substitutes.py) |
| `listar_familia` | `ProductSearchPort.family_roster()` | ✅ **existe** (C30a) | [`retrieval/ports.py`](../../../ai-service/src/jbg_ai/retrieval/ports.py) |
| `consultar_conocimiento` | `search_knowledge()` + `piece_scoped_exclusions()` | ✅ **existe** (C23 + C30a) | [`knowledge/search.py`](../../../ai-service/src/jbg_ai/knowledge/search.py), [`assist/knowledge_scope.py`](../../../ai-service/src/jbg_ai/assist/knowledge_scope.py) |
| `pedir_aclaracion` | `clarification_for()` / `clarification_axes()` | ✅ **existe** (C31) | [`assist/routing.py`](../../../ai-service/src/jbg_ai/assist/routing.py) |
| `consultar_disponibilidad` | — | ❌ **cero** | No hay consulta puntual en .NET. `scope_buckets(pos_id)` existe en el puerto, declarado *«Read by the evaluation only»* |

**Cuatro de las seis son envoltorios de código que ya funciona y está probado.** Lo nuevo de esta
historia no son las tools: es **el registro y sus invariantes**, más la única tool que había que
construir.

### Por qué la proyección y no .NET, y por qué etiqueta y no bucket

La única arista Python → .NET que existe hoy es
[`AiIndexFeedController`](../../../backend/src/JoiabagurPV.API/Controllers/AiIndexFeedController.cs):
autenticada por `X-Index-Feed-Key`, **sin `[Authorize]` a propósito** —*«a user JWT must not open
these routes»*— y sin transportar `pos_id`. Su ruta `pos-availability` es un **feed paginado de 200
filas con keyset**, pensado para un drenaje batch y no para una consulta puntual por producto.
Construir el endpoint aquí significaría una ruta .NET nueva, un filtro de autenticación con ámbito
de punto de venta y tests de integración: **zona .NET dentro de un change de zona Python**, y la
sesión desbordada.

Y hay un segundo hallazgo, éste del vocabulario. `QTY_BUCKETS` es `{"0", "1-2", "3+"}` en
[`indexing/feed.py`](../../../ai-service/src/jbg_ai/indexing/feed.py): **son dígitos**. Pasarle el
bucket crudo al modelo es pasarle literalmente una cifra de stock, que es exactamente lo que el §6.2
y el §15.10 del diseño prohíben y lo que `SearchHit.qty_bucket` declara al decir que *«a bucket on
the wire would be the beginning of one»*. La tool traduce a **etiqueta cualitativa sin dígitos**,
que además es el patrón de vocabulario cerrado que el proyecto ya usa para los `warnings[]`.

La puerta numérica de C30b sigue siendo la red. Lo que cambia es que deja de tener que salvarnos.

### La repregunta como tool no escribe la pregunta

C31 dejó escrito en la capability viva `assist-generation` que *«The clarification question is
resolved in code from a closed catalogue of templates»*, y la razón está en su propio código: el
contrato tipa `clarification_question` como **prosa**, así que la capa de presentación no puede
resolverla como resuelve un código de aviso, y **ninguna puerta numérica inspecciona ese campo**.

Una tool que dejara al modelo redactar la pregunta sería la primera prosa escrita por un modelo en
ese campo, y **retiraría un requisito vivo**. Así que `pedir_aclaracion` recibe **un eje del enum
cerrado** que `clarification_axes()` ya publica —`piece_type`, `material`, `occasion`, `price`— y el
castellano lo sigue escribiendo `clarification_for()`. El modelo decide *qué falta*; el código
decide *cómo se pregunta*.

Es, además, lo que distingue esta tool de la repregunta de C31, que la ficha del plan ya advertía
que **no son la misma cosa**: aquélla se decide antes de recuperar, ésta a media conversación.

### El invariante de solo-lectura, estructural y no declarativo

El §9.2 del diseño dice *«ninguna tool escribe»* y el §15.8 lo declara como limitación publicada:
*«Ningún agente escribe. Toda acción con efecto pasa por el operador o el admin.»* Es una de las
tres afirmaciones que el README entrega, así que **o se demuestra o no se declara**.

Un campo `writes: bool = False` en el descriptor de la tool no lo demuestra: lo puede poner
cualquiera a `False`. La comprobación es **por introspección del registro** y mira el grafo de
objetos, no una promesa: qué nombres contiene el registro, qué puertos captura cada tool, y qué
métodos exponen esos puertos.

---

### Alcance de esta historia (sí)

1. **Seis tools** con nombre, descripción en castellano orientada al modelo, esquema de parámetros
   tipado y **validación de argumentos antes de ejecutar**.
2. **El registro**: conjunto congelado de nombres, resolución por nombre, y la exportación del
   esquema de *function calling* de cada una.
3. **Errores como observaciones**, nunca como excepción que escape: vocabulario cerrado de causas y
   una observación que informa lo bastante como para que el modelo pueda reformular.
4. **`consultar_disponibilidad` servida desde `ai.pos_projection`**, con **etiqueta cualitativa sin
   dígitos**, declaración de frescura y un valor propio para «sin ámbito de punto de venta».
5. **Direccionamiento por `sku`** en todas las tools, con la lectura por SKU que eso añade al puerto
   de búsqueda.
6. **El invariante de solo-lectura comprobado por introspección.**
7. **Tests sin proveedor, sin red y sin base de datos real**, con fakes inyectados como en toda la
   zona `assist/`.

### Fuera de alcance (no)

1. **El bucle agéntico**, sus iteraciones y su decisión — **C32b**.
2. **`POST /v1/assist/agent`** y cualquier movimiento de `ai-service/openapi.json` — **C32b**.
3. **La transcripción multi-turno** y su delimitado por turno — **C32b**.
4. **Los tres presupuestos** (iteraciones, llamadas a tools, llamadas al proveedor) y el de tokens —
   **C32b**.
5. **El endpoint .NET de disponibilidad puntual** y el esquema de autenticación de vuelta: quedan
   **identificados, acotados y no hechos**, con la tool diseñada para que sean un reemplazo directo.
6. **`perfil_punto_venta`** (la servía C33, anulada) y **`buscar_complementarios`** (cortada con C27
   el 2026-09-12). No vuelven.
7. **Los escenarios de agente, los adversarios y los de inyección sistemáticos** — **C38**.
8. **Ningún cambio en `backend/`, `frontend/` ni `terraform/`.** Sin migración de EF Core.

---

### Decisiones de diseño ya acordadas

Tomadas en la sesión de exploración del 2026-09-20 y registradas en el §0 del plan de changes.

| # | Decisión | Razón |
|---|---|---|
| **D-1** | `consultar_disponibilidad` se sirve **desde `ai.pos_projection`**, no desde .NET | Resuelve la decisión abierta del §6.1 **difiriéndola con motivo**: no hay que inventar un esquema de autenticación de vuelta para un dato que Python ya tiene proyectado. La única arista existente lleva `X-Index-Feed-Key`, sin `[Authorize]` y sin `pos_id`, y su ruta es un feed paginado, no una consulta puntual |
| **D-2** | La observación es una **etiqueta cualitativa sin dígitos**, nunca el bucket | `QTY_BUCKETS` es `{"0", "1-2", "3+"}`: son cifras, y una cifra de stock en el contexto del modelo es lo que el §6.2 y el §15.10 prohíben. Vocabulario cerrado, como los `warnings[]` |
| **D-3** | La observación **declara su frescura** y **degrada, nunca elimina** | Invariante del §15.10, ya cableado en `ProjectionFreshness.reported_age` y publicado como `projection_age_seconds` en la recuperación. Una proyección de minutos no puede ocultar una pieza que la tienda sí puede vender |
| **D-4** | Sin `pos_id` en el token, la observación dice **«sin ámbito»**, que no es «agotado» | Precedente literal del puerto: `qty_bucket = None` significa *«ran unscoped, which is not the same as a bucket of zero»*. Inventar ausencia dispararía el pivote a sustitutos sobre una pieza disponible |
| **D-5** | `pedir_aclaracion` recibe **un eje del enum cerrado**; el texto lo escribe `clarification_for()` | Conserva intacto el requisito vivo de `assist-generation`. El campo está tipado como prosa y ninguna puerta numérica lo inspecciona, así que dejarlo al modelo abriría el único flanco sin red |
| **D-6** | El invariante de solo-lectura es **estructural y por introspección**, no un `writes: bool` | Una bandera declarativa no demuestra nada. El §15.8 es una de las tres declaraciones que el README entrega: o se comprueba o no se declara |
| **D-7** | **Los errores son observaciones con información**, con causa de vocabulario cerrado | Un `"error"` genérico deja ciego al modelo; una observación que dice *qué* falló le permite reformular. Y una excepción que escapa mataría el bucle de C32b en vez de gastarle una vuelta |
| **D-8** | Las tools se direccionan por **`sku`**, nunca por UUID | Precedente propio: C30b y C31 **excluyen los identificadores internos de producto** del payload por ser *«dígitos arbitrarios, nunca se dicen en mostrador»*. Un SKU es estable, real y semántico, que es justo lo que un resultado de tool debe llevar. Coste: una lectura por SKU nueva en el puerto |
| **D-9** | El registro **no se cablea a ninguna ruta HTTP** en este change | Su único consumidor es el bucle de C32b. Cablearlo antes sería exponer una superficie sin decisión detrás, y **`openapi.json` no se mueve** |
| **D-10** | Las tools **no llaman a ningún proveedor de chat**; los **embeddings** que sí pagan se cuentan aparte | Es lo que hace a esta mitad medible sin coste y la ablación limpia. `_usage()` suma enrutador y argumentario, así que un contador propio evita que el de C31 cambie de significado |
| **D-11** | Los **resultados son acotados y de alto valor**, no volcados de filas | El contexto acumulado es el factor dominante del coste de un bucle, y lo que esta mitad decida se reenvía en cada vuelta de C32b. Menos y más limpio decide mejor y cuesta menos |

### Referencias

- Change de OpenSpec: `openspec/changes/add-sales-assistant-tool-registry/` (C32a)
- Ficha del plan: [§3 · C32a](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) y la nota del **§0 del 2026-09-20**
- Diseño RAG: [§6.1, §6.2, §9.1, §9.2, §15.8 y §15.10](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md)
- Capability viva: [`assist-generation`](../../../openspec/specs/assist-generation/spec.md)
- Capabilities consumidas: [`vector-retrieval`](../../../openspec/specs/vector-retrieval/spec.md), [`substitutes-retrieval`](../../../openspec/specs/substitutes-retrieval/spec.md), [`knowledge-corpus`](../../../openspec/specs/knowledge-corpus/spec.md), [`pos-projection`](../../../openspec/specs/pos-projection/spec.md), [`product-family`](../../../openspec/specs/product-family/spec.md)
- Historia siguiente: **HU-AIENG-032b** *(el bucle, aún sin escribir)*
- Historia anterior: [HU-AIENG-031](HU-AIENG-031.md) · [HU-AIENG-030b](HU-AIENG-030b.md)
- Épica: [EP15 — Venta Asistida, Sustitutos y Agentes](../../epicas.md)

---

## Criterios de Aceptación

### Escenario 1: El registro contiene exactamente las seis herramientas esperadas

- **Dado que** el servicio expone el registro de herramientas del asistente de venta,
- **Cuando** se enumera su contenido,
- **Entonces** contiene **exactamente seis** entradas, ni una más ni una menos,
- **Y** sus nombres son los del conjunto congelado declarado en esta historia,
- **Y** **no** aparecen `perfil_punto_venta` ni `buscar_complementarios`, retiradas con C33 y con el
  corte de C27,
- **Y** cada entrada publica un esquema de parámetros válido con su descripción en castellano.

### Escenario 2: Ninguna herramienta registrada puede escribir

- **Dado que** el registro está construido con sus puertos inyectados,
- **Cuando** se inspecciona cada herramienta por introspección,
- **Entonces** ningún puerto capturado expone método alguno del vocabulario de escritura,
- **Y** ningún cliente HTTP registrado emite otro verbo que `GET`,
- **Y** la comprobación **falla** si se registra una herramienta nueva que no cumpla lo anterior,
  aunque su descriptor afirme lo contrario.

### Escenario 3: Un fallo de dependencia vuelve como observación y no como excepción

- **Dado que** la dependencia que una herramienta consulta no está disponible,
- **Cuando** se ejecuta esa herramienta,
- **Entonces** la llamada **no lanza** ninguna excepción al llamante,
- **Y** devuelve una observación marcada como fallida,
- **Y** la observación trae una **causa de vocabulario cerrado** que dice qué falló,
- **Y** esa causa es lo bastante informativa como para que un consumidor pueda decidir reformular en
  vez de reintentar a ciegas.

### Escenario 4: La disponibilidad se responde con una etiqueta y nunca con una cifra

- **Dado que** el token de servicio trae un punto de venta con ámbito asignado,
- **Cuando** se consulta la disponibilidad de una pieza por su SKU,
- **Entonces** la observación trae una **etiqueta del vocabulario cerrado** de disponibilidad,
- **Y** esa etiqueta **no contiene ningún dígito**,
- **Y** la observación declara **la antigüedad de la proyección** que la sirvió,
- **Y** en ninguna parte de la observación aparece una cantidad de existencias.

### Escenario 5: Sin ámbito de punto de venta, la disponibilidad dice «sin ámbito» y no «agotado»

- **Dado que** el token de servicio **no** trae punto de venta,
- **Cuando** se consulta la disponibilidad de una pieza,
- **Entonces** la observación declara explícitamente que **no hay ámbito de lectura**,
- **Y** **no** devuelve la etiqueta de agotado,
- **Y** la observación se distingue en el consumidor de una pieza realmente sin existencias.

### Escenario 6: La repregunta elige un eje y el castellano lo escribe el código

- **Dado que** se invoca la herramienta de aclaración con un eje del enum cerrado,
- **Cuando** se resuelve la observación,
- **Entonces** el texto devuelto es **exactamente** la plantilla que el catálogo cerrado de C31
  asocia a ese eje,
- **Y** dos invocaciones con el mismo eje devuelven **el mismo texto**,
- **Y** un eje que no pertenece al enum cerrado se rechaza en la validación de argumentos **antes**
  de ejecutar nada.

### Escenario 7: Las herramientas se direccionan por SKU, y una referencia desconocida es observación

- **Dado que** una herramienta anclada a pieza recibe un SKU que no existe en el índice,
- **Cuando** se ejecuta,
- **Entonces** devuelve una observación fallida con la causa correspondiente,
- **Y** **no** lanza excepción,
- **Y** ninguna herramienta acepta un identificador interno de producto como argumento.

### Escenario 8: La mitad sin proveedor — ninguna herramienta llama a un modelo de chat

- **Dado que** la suite de pruebas corre sin credencial de ningún proveedor configurada,
- **Cuando** se ejecutan todas las herramientas del registro,
- **Entonces** **todas** completan su observación,
- **Y** **ninguna** llama a un proveedor de chat,
- **Y** las llamadas de *embeddings* que sí se producen quedan contabilizadas en un contador propio,
  separado del `usage.calls` que C31 publicó.

### Escenario 9: Fuera de alcance explícito — aquí no hay bucle

- **Dado que** este change entrega el registro y no la capa de decisión,
- **Cuando** se revisa el código entregado,
- **Entonces** **no** existe ningún bucle de iteraciones ni presupuesto de vueltas,
- **Y** **no** se añade ninguna ruta a `ai-service/openapi.json`, que queda **byte a byte igual**,
- **Y** el comportamiento de `POST /v1/assist/sale` es **idéntico** al que dejó C31.

---

## Notas adicionales

**Actor.** Desarrollador del proyecto. Esta historia es **habilitadora**: no tiene superficie de
operario y su consumidor es C32b. El operario la nota, indirectamente, el día que el bucle pivota a
sustitutos porque la pieza que tiene en la mano está agotada en su tienda.

**Encaje con los apuntes del máster (S12).** *«Function calling en la práctica»* dice tres cosas que
esta historia convierte en criterios: la **descripción es la interfaz** —el modelo elige leyendo
sólo eso—, los **resultados deben ser de alto valor** y no volcados de filas, y **los errores también
son resultados**, de los importantes. *«Patrones de agentes y diseño de tools de calidad»* añade la
cuarta: cuidar la **granularidad**, una tool por operación con límites nítidos — y avisa de que si te
descubres explicando en la descripción cuándo *no* usar una tool, probablemente esa tool hace
demasiadas cosas.

**Limitaciones conocidas que se declaran y no se cierran.**

1. **La disponibilidad la sirve una proyección que puede desfasarse minutos.** La autoridad sobre el
   stock es de .NET (§6.2) y lo sigue siendo: por eso la observación declara su frescura, degrada y
   nunca elimina. El endpoint puntual queda acotado y no hecho.
2. **Las descripciones de las tools no se han iterado contra un modelo real**, porque esta mitad no
   llama a ninguno. Son un prompt, y un prompt se itera con medición: eso ocurre en C32b, y el
   apunte de S12 avisa de que una elección equivocada de tool casi nunca es culpa del modelo sino de
   una descripción vaga.
3. **El recuento de seis no es lo que el PF evalúa**, y conviene repetirlo: lo evaluable son el
   bucle, el presupuesto duro, el invariante de solo-lectura y el `partial: true`. De los cuatro,
   esta historia entrega **uno**.
4. **`style_similarity` sigue en cero para 403 de 404 productos reales** (C26), así que las
   observaciones de `buscar_sustitutos` heredan esa limitación ya declarada. No es de aquí.

**Change de OpenSpec por el que se implementa.**
`openspec/changes/add-sales-assistant-tool-registry/`, rama
`c32a-add-sales-assistant-tool-registry`.

---

## Tareas

1. **Puerta de entrada**: línea base de la suite de `ai-service` **por nombres de test** y no por
   recuento (`git stash push -u`, correr, `git stash pop`), y `openspec validate --all --strict` en
   verde antes de tocar nada.
2. **Vocabulario cerrado de disponibilidad** en `assist/constants.py`: las etiquetas cualitativas,
   el valor de «sin ámbito» y el mapa desde `QTY_BUCKETS`, con un test que compruebe que **ninguna
   etiqueta contiene un dígito** y que el mapa cubre el vocabulario entero del feed.
3. **Vocabulario cerrado de causas de error** de tool, en el mismo sitio y con el mismo patrón que
   los `warnings[]`: códigos, nunca prosa.
4. **Lectura por SKU en `ProductSearchPort`** y su implementación SQL en `retrieval/search.py`,
   leyendo sólo `ai.product_document`, con el mismo tratamiento de fila ausente que
   `source_document()` ya tiene: el ausente viaja como valor y no como excepción.
5. **Lectura de disponibilidad por producto** sobre `ai.pos_projection`, reutilizando la frescura ya
   cableada en `retrieval/projection.py` en vez de recalcularla.
6. **Descriptor de tool y registro** en `assist/tools.py`: nombre, descripción, esquema de
   parámetros, validación de argumentos y ejecución. El conjunto de nombres **congelado** y expuesto
   como constante.
7. **Las seis tools**, cuatro como envoltorios de lo que ya existe y dos nuevas de construcción:
   `consultar_disponibilidad` y `pedir_aclaracion`.
8. **Observación acotada** por tool: qué campos viajan y cuáles no, con la exclusión explícita de
   identificadores internos y de *scores* crudos, siguiendo el precedente del *payload* de C30b.
9. **Exportación del esquema de *function calling*** de cada tool, fijada con un test de forma —no
   con un *snapshot* congelado como `openapi.json`, porque aquí no hay frontera con .NET.
10. **Test de introspección del invariante de solo-lectura**, con sus tres comprobaciones, escrito
    de modo que **falle al registrar** una tool futura que no cumpla.
11. **Fakes de puerto para la suite**, reutilizando los de `tests/assist/conftest.py` y
    `tests/support/` en vez de escribir otros: la suite de `assist/` ya tiene esa costura.
12. **Delta de la capability `assist-generation`** —o capability nueva si el registro no encaja en
    ella, a decidir al redactar el `proposal`—, con `openspec validate --all --strict` en verde.
13. **Informe de implementación** con lo que la implementación refute de esta historia, siguiendo el
    patrón de los nueve anteriores.
14. **Documentación**: `Documentos/epicas.md`, plan de changes, `ai-service/README.md`,
    `ai-service/tests/README.md`, `openspec/config.yaml` y la ficha de C32b si el trabajo mueve algo
    de lo que ya lleva anotado.

---

## Estimaciones y atributos de priorización

| Atributo | Valor |
|---|---|
| Puntos de historia | _Pendiente_ — a fijar en refinamiento |
| Impacto en usuario / valor de negocio | **3/5** — es habilitadora y no llega a pantalla. Su valor propio es el **invariante de solo-lectura**, que convierte una de las tres declaraciones del README (*«ningún agente escribe»*) en propiedad comprobable; el resto del valor lo cobra C32b |
| Urgencia | **5/5** — **taponea a C32b**, y con él a **C38** y **C39**. El §6 del plan marca C32a y C32b como **«nunca se recortan»** |
| Complejidad / esfuerzo | **2/5** — cuatro de las seis tools son envoltorios de código probado, no hay proveedor, no hay migración, no hay `backend/` ni `frontend/`, y `openapi.json` no se mueve. Lo único de construcción real son la disponibilidad cualitativa y la lectura por SKU |
| Riesgos | **Que el registro se lleve por delante la frontera de `retrieval/`**: esta historia toca `ports.py` y `search.py`, que C31 declaró explícitamente no haber tocado (mitigado por las tareas 4 y 5, que añaden lecturas y no modifican las existentes). **Que la etiqueta cualitativa se quede corta** y C32b descubra que el modelo necesitaba distinguir `1-2` de `3+` para decidir el pivote (mitigado porque el vocabulario es una constante y ensancharlo no mueve ningún contrato). **Que la delta de spec no encaje en `assist-generation`** y haga falta capability nueva, lo que alarga la sesión (recogido en las preguntas abiertas). **Que la granularidad de las seis resulte equivocada** al probarla contra un modelo real, que es algo que esta mitad no puede medir por construcción |
| Dependencias | **C30b** y **C31**, los dos archivados (14 y 16 de septiembre). Consume **C14/C21/C25** (recuperación), **C26** (sustitutos), **C23** (corpus), **C30a** (roster y filtro de slug), **C31** (plantillas de repregunta) y **C22** (proyección por punto de venta y su frescura). **Bloquea a C32b**, y con él a C38 y C39 |

---

## Preguntas Abiertas

| # | Pregunta | Opción por defecto si no hay respuesta antes del *apply* |
|---|---|---|
| **Q-1** | ¿El registro entra como delta de `assist-generation` o nace capability propia? | **Capability propia** `sales-assistant-tools`: `assist-generation` ya tiene 41 requisitos y describe una ruta HTTP, mientras esto es una biblioteca sin ruta. Se decide al redactar el `proposal` |
| **Q-2** | ¿La etiqueta cualitativa lleva tres valores o cuatro? | **Cuatro**: los tres de disponibilidad más «sin ámbito», porque D-4 exige que no sea confundible con agotado |
| **Q-3** | ¿`buscar_catalogo` expone `top_k` al modelo? | **Sí, acotado**, con mínimo y máximo en el esquema. Un `enum` o un límite explícito hace más por la fiabilidad que cualquier ajuste de temperatura, según el apunte de S12 |
| **Q-4** | ¿Los esquemas de *function calling* se congelan en un *snapshot* versionado? | **No.** `openapi.json` se congela porque es frontera con .NET; esto no cruza ninguna frontera. Se fija con un test de forma |
| **Q-5** | ¿La lectura por SKU va en `ProductSearchPort` o en un puerto nuevo? | **En `ProductSearchPort`**, junto a `source_document()` y `family_roster()`, que responden preguntas de la misma naturaleza sobre la misma tabla |
