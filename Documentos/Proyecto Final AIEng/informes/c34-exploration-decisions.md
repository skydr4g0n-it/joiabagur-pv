# C34 — decisiones de exploración: la hidratación del asistente de venta, y unos marcadores que no dicen de quién son

**Change:** `add-dotnet-assist-and-recommendation-endpoints` (C34) · **Fecha:** 2026-09-21
**Árbol explorado:** `ai-eng` en `d42e5d6` · **Rama de implementación:** pendiente, derivada de `ai-eng`

Este informe recoge lo que la exploración **comprobó sobre el árbol** y las catorce decisiones de
arquitectura que salen de ello. Es la entrada de `/enrich-us` y del `/opsx:propose` posterior.

**Qué contiene y qué no.** Contiene **cinco mediciones nuevas**, todas reproducibles con el SQL o el
script que se da en el §5: tres sobre la base local (M-1 con su variante M-1b, M-2 y M-5), que es
el mundo simulado de C10 con el índice de C13, y dos sobre el artefacto de la pasada de C30b (M-3 y
M-4), que ya estaba en el repositorio. **No contiene
ninguna medición de C34**, porque C34 no existe: ninguna cifra de latencia de extremo a extremo
.NET → Python se mide aquí, y la que hace falta queda como medición pendiente (§6). Las cifras de
C26, C30b, C31 y C32b se **citan** de sus informes y no se vuelven a medir.

**Cuatro de las catorce decisiones se cerraron con el desarrollador en la sesión** (D-A, D-B, D-E y
D-N) y llevan la marca **«cerrada»**. Las demás son la recomendación de la exploración, que el
desarrollador no discutió. Quedan en pie salvo que la historia de usuario las revise.

La razón de ser del informe es que la ficha de C34 se escribió antes de que existiera nada de lo que
consume. Cuatro changes han pasado por el contrato desde entonces (C30a, C30b, C31 y C32b), y al
contrastar la ficha con el árbol, **una de sus anotaciones resulta falsa** y otras cuatro cosas que
daba por resueltas no lo están. Se corrigen aquí, y la ficha se corrige en el sitio.

---

## 1. El inventario, comprobado sobre el árbol y no sobre la ficha

### 1.1 · El andamio que ya existe

| Pieza | Estado verificado | Qué aporta a C34 |
|---|---|---|
| [`POST /v1/assist/sale`](../../../ai-service/src/jbg_ai/api/routers/assist.py) | Real desde C30a. Genera argumentario desde C30b, con `assist/v3`. Tres modos | Lo que C34 consume en **M2** (pieza sin pregunta) y **M3** (pieza y pregunta) |
| [`AssistResponse`](../../../ai-service/src/jbg_ai/api/schemas/assist.py) | `groups`, `pitch` con `{{price}}`/`{{stock}}`, `citations` con `claim_scope`, `warnings` de vocabulario cerrado, `intent`, `abstained`, `clarification_question`, `prompt_version` | La forma que se hidrata. **En los modos anclados hay un único grupo**: la familia de la pieza anclada, o la pieza sola si no tiene familia |
| [`POST /v1/retrieval/substitutes`](../../../ai-service/src/jbg_ai/retrieval/substitutes.py) | Real desde C26. Devuelve **la ventana entera**, `min(3·top_k, 60)`, y no `top_k` | El universo de candidatos que C34 filtra por stock |
| [`AssistedSearchService`](../../../backend/src/JoiabagurPV.Application/Services/AssistedSearchService.cs) (C15) | Autorizar el POS → una llamada → hidratar con una sola consulta → truncar sin reordenar → degradar | **El patrón a copiar.** `AuthoriseAsync` (L135) es exactamente la comprobación de 403 que C34 necesita |
| `IAssistedSearchRepository.HydrateAsync` | Una consulta sobre `Inventories` activos de productos activos en el POS. **Conserva las filas con cantidad 0** | La hidratación de miembros de familia y de sustitutos, sin escribir SQL nuevo |
| `ProductFamilyRepository.GetByProductIdAsync` | La familia de una pieza, con sus miembros ordenados por `SortOrder` | La familia **de .NET** para el card degradado (D-J) |
| [`AiGatewayOptions.AssistTimeoutMs`](../../../backend/src/JoiabagurPV.Application/Configuration/AiGatewayOptions.cs#L59) | `5000`, **reservado y sin usar** | El presupuesto que D-F recalcula |
| [`AiGatewayServiceCollectionExtensions.cs:148`](../../../backend/src/JoiabagurPV.Application/Extensions/AiGatewayServiceCollectionExtensions.cs#L148) | Un comentario que reserva el sitio: *«C34 registers its own named client here for the generative route, with a 5 s budget»* | Dónde se registra el cliente `ai-assist` |
| `FakeHttpMessageHandler`, `AiGatewayTestHost` | Pilotan el *pipeline* real de Polly cambiando sólo el socket | Los tests del cliente nuevo, sin inventar infraestructura |
| `AiContractSnapshotTests.ModelToSchema` | Tabla tipo .NET ↔ esquema de `openapi.json` que falla si un campo deriva | Los DTO nuevos entran como filas de esa tabla |
| `IAiGatewayClient` | Cinco métodos. **Ninguno de assist ni de sustitutos** | C34 es su primer consumidor |

### 1.2 · Los nueve hallazgos

| # | La ficha supone | El árbol dice | Decisión |
|---|---|---|---|
| **H1** | *«Ninguna hidratación nueva: no hay más `{{price}}` ni `{{stock}}` que los de los candidatos»* (anotación del 14 sep) | **Los marcadores no dicen de qué pieza son.** En M2 y M3 da igual, porque sólo hay una pieza. En M1 y en el agente, el prompt pide hablar de **varias piezas** ([`v4.md:104-108`](../../../ai-service/prompts/assist/v4.md#L104-L108)) y el modelo usa el mismo token para todas. .NET no puede resolverlo sin adivinar, y el propio prompt llama a una cifra equivocada *«un error de venta»*. **La anotación es falsa** | D-A, D-C |
| **H2** | El presupuesto de 5 s del §6.4 sirve para `/v1/assist/sale` | En el ancho que se sirve, **el 7,5 % de las peticiones pasa de 5 s** solo en llamadas al proveedor, el **55 %** hace la reparación, y el peor caso por construcción es **2 × 4 s** más las búsquedas (M-3). Además, `IsRetryable` **reintenta los timeouts** ([L169](../../../backend/src/JoiabagurPV.Application/Extensions/AiGatewayServiceCollectionExtensions.cs#L169)): un timeout costaría el doble de latencia y el doble de LLM | D-F |
| **H3** | — | [`TranslateStatus`](../../../backend/src/JoiabagurPV.Application/Services/AiGatewayClient.cs#L643) convierte **cualquier** respuesta que no sea 2xx, salvo 401 y 501, en `AiUnavailableException`. Las dos rutas de Python devuelven **422** para una pieza que no está en el índice. Una pieza dada de alta después de la última sincronización se leería como «IA no disponible» | D-F, D-I |
| **H4** | `GET …/sales-assist?question=` | La pregunta es texto libre del cliente, y en una URL acaba en el log de acceso de nginx, en el historial y en cualquier caché intermedia. Choca con D-I de C30 (*«no se loguea»*) y con las medidas del §15.11 del diseño | D-B |
| **H5** | `stock_critical` tiene un significado | .NET tiene **dos definiciones incompatibles** de stock bajo: [`StockValidationService`](../../../backend/src/JoiabagurPV.Application/Services/StockValidationService.cs#L18-L19) usa `max(10 %, 5)` sobre lo que queda tras la venta, y [`DashboardService`](../../../backend/src/JoiabagurPV.Application/Services/DashboardService.cs#L208) usa `≤ 2` | D-H |
| **H6** | Los avisos estructurales de Python se apilan tal cual | `family_has_variants` se calcula sobre la familia **del índice**. .NET tiene que quitar los miembros que no están en ese POS (access-control prohíbe enseñárselos a un operario). Medido: en las tiendas, **el 19,2 % de las piezas ancladas con familia llevaría un aviso de variantes falso** tras hidratar (M-2) | D-G |
| **H7** | .NET filtra por stock lo que llega | El tamaño de la ventana lo decide `top_k`, que **pone .NET**, y el filtro por stock es muy selectivo: Fornells tiene stock de **212 de 1.168** piezas indexadas. Con la ventana de 15 (`top_k=5`), **el 71,1 %** de sus piezas ancladas no llenaría una página de 5. Con la de 60, el 7,1 % (M-1) | D-I |
| **H8** | — | **Los tests de integración de C15 no llegan nunca al gateway**: no hay sección `AiSearch` en ningún `appsettings`, el interruptor vale `false` por defecto y el test recorre el camino «desactivado». Y **siete dobles escritos a mano** de `IAiGatewayClient` dejan de compilar al añadir un método | D-L |
| **H9** | — | **La demo no genera argumentario**: `compose.demo.yaml` no pasa ninguna credencial generativa (tarea diferida de C30b). En la demo, la sustitución de marcadores de C34 no se ejecutaría nunca | D-N |

---

## 2. Las catorce decisiones

### D-A · Alcance: sólo las dos rutas del card — **cerrada**

**Decisión.** C34 expone el argumentario y la pregunta sobre una pieza (M2 y M3) y los sustitutos.
**Ni la consulta libre (M1) ni la ruta del agente** (`/v1/assist/agent`).

| Opción | A favor | En contra |
|---|---|---|
| **Sólo el card** ★ | Todo en la zona .NET. El contrato de Python no se mueve. La referencia de los marcadores es trivial, porque la pieza es una | M1 y el agente siguen sin pantalla: el §15.12 del diseño sigue declarado |
| Card + M1 | Cierra el §15.12 y hace visible el «no lo sé» del enrutador | Por H1, o se retira casi todo argumentario de M1 o hay que tocar Python. Y C16/C36 necesitan un bloque de respuesta nuevo en el panel |
| Card + agente | El agente llega a algo más que el arnés | El mismo problema de H1, agravado: hay grupos de catálogo y grupos de sustitutos. Sin pantalla de conversación no hay consumidor, y la tarea diferida de C32b dice expresamente que se espere a tenerlo |

**Lo que desbloquearía M1 y el agente, identificado y no hecho.** Es pequeño y es de Python: en las
tareas de prompt **sin pieza anclada**, se prohíben los marcadores (las filas del panel ya enseñan el
precio y el stock hidratados de cada pieza, así que el argumentario no los necesita), y la puerta
numérica trata un marcador en esas tareas como una violación. **El problema tampoco es sólo de
C34**: cualquier consumidor futuro de M1 o del agente lo hereda.

**La consecuencia para el diseño.** El §15.12 (*«la pregunta libre sin pieza elegida no tiene
pantalla»*) **sigue siendo cierto** después de C34, y la anotación del 14 de septiembre en la ficha,
que asignaba esa ruta a C34, se corrige.

### D-B · Forma de las rutas — **cerrada**

**Decisión.**

```text
POST /api/ai/products/{productId}/sales-assist
     body: { pointOfSaleId: guid, question?: string (≤ 500) }

GET  /api/ai/products/{productId}/substitutes?pointOfSaleId={guid}&pageSize={1..20, def. 5}
```

`pointOfSaleId` es **obligatorio en las dos**, con la regla de C15: nunca se infiere y nunca se usa un
comodín (*«Every assisted search is scoped to one concrete point of sale»*). La ficha no lo llevaba en
`/sales-assist`, y sin él `AiCallScope.ForPointOfSale` no se puede construir.

**Por qué `POST` y no `GET` en el argumentario**, del motivo más fuerte al menos fuerte:

1. **H4.** La pregunta del cliente no debe acabar en logs sin política de retención.
2. **Un `GET` es seguro y cacheable por definición.** Un navegador, un proxy o una precarga lo pueden
   repetir, y cada repetición es una llamada de pago al proveedor.
3. **El precedente de C15**: *«a write-free POST under the AI namespace»*.

En contra: la semántica REST pura de una lectura. Se acepta.

**Los sustitutos se quedan en `GET`**, porque no llevan texto libre, no llaman al LLM y son
idempotentes de verdad.

**Dos rutas y no una**, y no por cortesía con la ficha: la de sustitutos tarda menos de un segundo y
el argumentario ~4. Separadas, **el card de C36 puede lanzarlas en paralelo** y pintar los sustitutos
mientras el argumentario llega.

### D-C · Los marcadores: a qué pieza se refieren y por qué valor se sustituyen

**Decisión.**

| Regla | Valor |
|---|---|
| Referencia | **La pieza anclada**, siempre |
| `{{price}}` | `Product.Price` con formato es-ES: «39,90 €» |
| `{{stock}}` | La cantidad en el POS de la petición, **como entero**: «3» |
| Respuesta sin pieza anclada que trae un marcador | Se retira el argumentario (fallo cerrado). C34 no expone ese caso, pero lo defiende |

**La evidencia de `{{stock}}` como entero (M-4).** En las 213 generaciones de C30b que llevan
marcadores:

```text
«y tenemos {{stock}}» 114 · «actualmente tenemos» 38 · «stock de» 26 · «y hay» 6 · «inventario hay» 4
   → leído como NÚMERO: 188/213 (88,3 %)
«y en {{stock}}» 18 · «y con» 3 · «modelo por» 2 · «en stock» 2
   → 25/213 (11,7 %) no encajan con ninguna sustitución de una sola forma
seguido de «unidades»: 4/213
```

| Sustitución | Encaja en | Descartada porque |
|---|---|---|
| **Entero** ★ | 188/213 | — |
| «N unidades» | Casi los mismos | Rompe además los 4 que ya van seguidos de «unidades» («hay 3 unidades unidades») y obliga a gestionar el singular |
| Etiqueta cualitativa de C32a («disponible», «últimas unidades») | ~25 | Rompe el 88 %: «tenemos disponible en tienda» |

**`{{price}}` no plantea dudas**: 147 de 213 son «disponible(s) por {{price}}» y 52 «es de {{price}}».
Las dos se leen bien con un importe formateado.

**El 11,7 % que queda mal escrito se acepta y se declara.** Arreglarlo exige que el modelo sepa qué
tipo de sustitución recibirá, y eso es un cambio de prompt en Python con su pasada de medición.

### D-D · Un marcador sin resolver retira el argumentario, no la respuesta

**Decisión.** Después de sustituir los dos marcadores conocidos, si en el texto queda **cualquier**
`{{` o `}}` —un marcador desconocido como `{{precio}}`, uno mal formado o uno que no se pudo
resolver—, .NET **retira el argumentario**, marca `pitchStatus = withheld_unresolved` y **sirve el
resto de la respuesta**: grupos, avisos y citas.

**Por qué no un error HTTP, que es lo que leía la ficha** (*«rechazo de la respuesta»*):

- **La política ya existe y es ésta.** Las puertas de C30b hacen lo mismo cuando fallan: se entrega
  la parte estructurada sin argumentario. Un rechazo en .NET que tirara también grupos y citas sería
  **más severo** que el de Python por un fallo del mismo tipo.
- **Los apuntes lo piden por escrito.** La S4 (*«cada guardrail debe declarar explícitamente cuál de
  las tres políticas aplica»*) y la S11 (`gate_line`, que degrada la parte y no el todo).
- **Lo que protege el invariante es que la plantilla cruda nunca llegue al cliente**, y eso se cumple
  igual retirando sólo el argumentario.

**Un matiz que se declara.** Cuando es **Python** quien retira el argumentario, las citas vuelven a
ser **todas las que fundamentaron** la respuesta ([`orchestrator.py:402-409`](../../../ai-service/src/jbg_ai/assist/orchestrator.py#L402-L409)).
Cuando lo retira **.NET**, sólo tiene **las que el argumentario usó**, que son un subconjunto, y no
puede reconstruir el resto. La respuesta degradada por .NET sale con menos citas que la degradada por
Python. Es aceptable, pero el contrato hacia el frontend lo tiene que decir (D-K).

**El argumentario ya resuelto no se escribe en ningún log**, a ningún nivel: lleva el precio real, que
es justamente lo que D-I de C30 (punto d) prohíbe. Se loguean el `trace_id`, el `pitchStatus`, la
longitud, los `citation_id` y los códigos de aviso.

### D-E · La pieza anclada sin stock — **cerrada**

**Decisión.** Si la pieza anclada tiene **0 unidades** en el POS:

- **En M2** (sin pregunta), **se retira el argumentario**, con `pitchStatus = withheld_out_of_stock`,
  y el card muestra el bloque de sustitutos.
- **En M3** (con pregunta), **se sustituye el 0 tal cual**.

**Por qué.** En 147 de 213 generaciones el modelo escribe «disponible por {{price}}» **antes de saber el
stock**, porque no lo sabe. Con 0 saldría «está disponible por 39,90 € y tenemos 0 en tienda». En M2
eso es el argumento de venta de algo que no se puede vender. En M3 la respuesta a la pregunta vale
igual: un cliente puede preguntar si se puede mojar una pieza que compró hace un año.

**Cuánto pasa.** Medido: **el 6,5 %** de las piezas ancladas en las tiendas tiene 0 unidades (M-2).

| Alternativa | Descartada porque |
|---|---|
| Sustituir el 0 siempre | Deja la contradicción en el caso más frecuente |
| Retirar siempre | Pierde la respuesta de conocimiento sobre una pieza agotada, que es el único camino por el que el corpus de C23 llega al mostrador |

### D-F · Presupuesto de tiempo y resiliencia

**Decisión.**

| | Cliente | Timeout | Reintentos | Circuito |
|---|---|---|---|---|
| Argumentario | **`ai-assist`**, nuevo | **10 s** | **Ninguno en timeout.** Sólo uno ante un fallo de transporte rápido (conexión rechazada) | Propio |
| Sustitutos | **`ai-retrieval`**, el existente | 2,5 s (el vigente) | 1, el vigente | Compartido con la búsqueda |

Y una excepción nueva, **`AiRequestRejectedException`**, para el **422**: no se reintenta, no cuenta
para el circuito y **no se lee como «IA no disponible»** (H3).

**Por qué 10 s.** El presupuesto de fuera tiene que ser **mayor o igual que el peor caso que declara
el de dentro**. Si no, .NET tira respuestas que Python iba a entregar, ya degradadas pero útiles, y
cae a su propia degradación, que tiene menos cosas. El peor caso de Python en M2 y M3 es, por
construcción, `MAX_PITCH_PROVIDER_CALLS × PITCH_TIMEOUT_SECONDS = 2 × 4 s` más la lectura de la pieza,
de la familia y del corpus (y en M3 un *embedding*): unos 8,5 s. 10 s deja margen de red.

| Opción | Cuánto corta (M-3, ancho servido) | Espera en la cola | En contra |
|---|---|---|---|
| 5 s, lo reservado | **7,5 %** (20 % con 3 secciones) | 5 s | Las peticiones cortadas pierden argumentario y citas |
| **10 s** ★ | ~0 %: Python se acota solo | 9-10 s en el p99 | El operario espera en la cola |
| 5 s y pasar el plazo a Python | 0 % desperdiciado | 5 s | Cambio en Python: una cabecera de plazo y saltarse la reparación. Zona cruzada, y sin precedente en los apuntes |
| Asíncrono con consulta periódica | — | — | Desproporcionado. La S15: *«síncrono hasta que duela»* |

**Por qué ningún reintento en timeout.** El predicado actual reintenta `TimeoutRejectedException`.
En el argumentario, eso son 20 s de espera y **dos llamadas de pago** por petición. Es la desviación
consciente de la S9, que reintenta 502/503/504 con *backoff* dentro de un presupuesto de 30 s: en un
mostrador no hay 30 s.

**Por qué los sustitutos van en `ai-retrieval`.** Es la misma familia de rutas (`/v1/retrieval`),
**no llama al proveedor** —el *embedding* de origen ya está almacenado— y comparte el dominio de
fallo con la búsqueda: si falla uno, falla el otro por la misma causa.

**Una observación que conviene tener presente.** Cuando cae el proveedor del LLM, Python responde
**200 sin argumentario**, no un 5xx. Así que esa caída **no abre el circuito de .NET**. Es lo
correcto: quien degrada es Python, y el circuito de .NET protege de que Python no responda.

**El invariante, escrito para la spec:** *el presupuesto de .NET para el argumentario es mayor o igual
que el peor caso declarado por el servicio de IA*. Y un test que falle si alguien baja
`AssistTimeoutMs` por debajo de 2 × 4 s.

### D-G · El grupo y la pieza anclada

**Decisión.** El grupo lo da Python y .NET lo hidrata (**R1**), con cinco reglas:

1. **La pieza anclada tiene que estar en ese POS** (inventario activo de producto activo, con cualquier
   cantidad). Si no, **404 antes de llamar a la IA**: se ahorra una llamada de pago. La regla es la
   misma para todos los roles, porque el ámbito de la petición es un POS concreto, en coherencia con
   la regla de hidratación de C15.
2. Se quitan los miembros que no están en ese POS. **Se conserva el orden de Python.**
3. **`family_has_variants` se recalcula sobre los miembros que sobreviven**: sólo se mantiene si
   quedan dos o más. **H6 medido: el 19,2 %** de las piezas ancladas con familia en las tiendas lo
   llevaría falso sin esta regla, y el **55,6 %** pierde algún miembro al hidratar.
4. La pieza anclada va marcada (`isAnchor`) para que el card no tenga que buscarla.
5. Un operario asignado a otro POS recibe **403** sin que se llame a la IA, con la comprobación de
   `AuthoriseAsync`.

| Alternativa | A favor | En contra |
|---|---|---|
| **R1 · el grupo de Python, hidratado** ★ | Es el patrón de C15 y es para lo que C30a construyó el contrato | Una familia editada entre dos sincronizaciones tarda unos minutos en verse |
| R2 · .NET construye siempre el grupo desde `ProductFamily` | Una sola autoridad sobre las familias, que son de .NET según el §6.2 | Desaprovecha el agrupado de C30a y pone en .NET una regla que Python ya tiene escrita, y tensa el «Python redacta, .NET decide» |

**La regla 3 no duplica a Python, lo complementa.** Python afirma algo sobre la familia; .NET afirma
algo sobre **lo que ese POS puede vender**. Es la misma razón por la que los avisos de stock son de
aquí.

### D-H · Los avisos de stock

**Decisión.**

| Código | Se emite cuando | Frecuencia medida en las tiendas (M-2) |
|---|---|---|
| `stock_critical` | La pieza anclada tiene **entre 1 y 2 unidades** en el POS. Umbral configurable, 2 por defecto | **4,0 %** de las piezas ancladas con familia · 4,2 % de las filas con stock (M-5) |
| `family_members_out_of_stock` | **Otro** miembro de la familia que **sí está** en ese POS tiene 0 unidades | **11,2 %** |

**El stock 0 no es un aviso: es un estado** (`hasStock = false` en el miembro). Es lo que dispara el
bloque de sustitutos de C36 y la retirada de D-E.

**Por qué 2 y no `max(10 %, 5)`** (H5):

- **Coincide con el vocabulario que el proyecto ya tiene.** El *bucket* `1-2` de `QTY_BUCKETS` es
  `ultimas_unidades` en C32a, y 2 es el valor por defecto del panel de stock bajo del dashboard.
- **Es señal, no ruido.** Salta en el 4,2 % de las filas con stock. `≤ 5` saltaría en el 14,4 %, sobre
  una mediana de 12 unidades.
- **La regla de ventas mide otra cosa**: lo que queda *después* de vender, en términos relativos. No
  es una definición de «esta pieza está en las últimas».

**Los miembros que no están en el POS no cuentan** para `family_members_out_of_stock`: se han quitado
en D-G, y un operario no puede verlos.

### D-I · Sustitutos: ventana, filtro y los cuatro vacíos

**Decisión.**

1. **Siempre `top_k = 20`**, que da la ventana máxima de 60, en una sola llamada y sin repetirla. Es
   la regla de C15 (*«the largest candidate window… requested once»*).
2. Filtro de .NET: **inventario activo de producto activo en el POS y `Quantity > 0`**. Se conserva el
   orden de Python y después `Take(pageSize)`.
3. Se exige que la pieza anclada esté en el POS, igual que en D-G, y la comprobación de 403 es la misma.
4. **Se registra el embudo en el log**: candidatos devueltos → presentes en el POS → con stock →
   servidos. Es lo que la S9 pide para el post-filtrado: *«si tu wide_k es 50 pero solo 2 de esos
   cumplen el filtro, has fallado… sin instrumentación, no te enteras»*.
5. **Cuatro resultados vacíos que la respuesta distingue**, con el precedente de *«the three empty
   outcomes are distinguishable»* de C15:

| `outcome` | Significa |
|---|---|
| `ok` | Hay al menos un sustituto con stock |
| `none_in_stock` | La IA contestó y ningún candidato tiene stock en este POS |
| `product_not_indexed` | Python respondió 422: la pieza todavía no está en el índice (H3) |
| `ai_unavailable` | El circuito está abierto, hubo timeout o la IA no responde |

**La evidencia de la ventana (M-1).** Sobre todas las piezas ancladas posibles:

| POS | Piezas ancladas | Mediana de supervivientes, ventana 60 | < 5 con ventana 60 | < 5 con ventana 15 |
|---|---|---|---|---|
| Fornells | 239 | 11 | **7,1 %** | **71,1 %** |
| Aeroport de Menorca | 416 | 16 | 5,3 % | 45,2 % |
| Estació Marítima, Maó | 402 | 20 | 4,0 % | 34,6 % |
| Ciutadella Centre | 853 | 46 | 1,4 % | 3,8 % |

Y sobre el caso que de verdad dispara el bloque, **las piezas ancladas sin stock en su tienda
(428)**: mediana de **20** supervivientes y **3,0 %** por debajo de 5 con la ventana de 60, contra el
**30,6 %** con la de 15 (M-1b).

**El aviso de C26 que conviene saber aquí.** El término de disponibilidad de C26 **particiona** en la
práctica: los candidatos agotados quedan siempre detrás de los disponibles. El filtro de .NET no
cambia eso; lo que hace es quitar la cola.

### D-J · Degradación del card

**Decisión.** Si la IA no responde (circuito abierto, timeout, 422 o interruptor apagado), la
respuesta es **200 con `aiAvailable: false`**, y lleva:

- **la pieza anclada y su familia leída de .NET** (`GetByProductIdAsync` + el `HydrateAsync` que ya
  existe);
- los **avisos de stock** y `family_has_variants` calculados en .NET;
- **sin argumentario, sin citas y sin `size_label_missing`**, que es un dato del índice.

**Por qué la familia y no sólo la pieza.** La **confirmación de variante antes de vender** es la
funcionalidad del card con más valor en el mostrador, y es lógica de negocio, no de IA: las familias
son entidades de .NET (§6.2). Cuesta una consulta y reutiliza la hidratación. Es el *«el sistema nunca
se cae por culpa de la IA»* del §6.4 aplicado a este card.

**Alternativa descartada:** devolver sólo la pieza anclada. Es más simple, pero el card degradado
pierde justo lo que no necesitaba a la IA.

### D-K · El contrato hacia el frontend

**Decisión.** Esbozo; los nombres definitivos los fija la historia de usuario:

```text
SalesAssistResponse
  aiAvailable            bool
  pointOfSaleId          guid
  intent                 string              // pasa tal cual: product_pitch en M2
  groups[]               { familyId?, familyLabel?, members[] }
    members[]            { productId, sku, name, variantLabel?, price, quantityAtPointOfSale,
                           hasStock, primaryPhotoUrl?, materials[], matchReasons[], isAnchor }
  pitch                  string?             // ya resuelto; null cuando no hay
  pitchStatus            generated | not_generated | withheld_by_ai
                         | withheld_unresolved | withheld_out_of_stock | ai_unavailable
  citations[]            { citationId, documentTitle, sectionTitle, docType, claimScope, snippet }
  warnings[]             string              // los 5 de Python + stock_critical + family_members_out_of_stock
  clarificationQuestion  string?
  promptVersion          string?
  traceId                string

SubstitutesResponse
  outcome                ok | none_in_stock | product_not_indexed | ai_unavailable
  results[]              { productId, sku, name, variantLabel?, price, quantityAtPointOfSale,
                           primaryPhotoUrl?, materials[], matchReasons[],
                           familyMatch, materialOverlap, styleSimilarity }
  candidatesReturned     int
  survivedHydration      int
```

**Por qué `pitchStatus` como enumerado.** C30b codificó el estado del argumentario en dos campos
(`prompt_version` nulo significa «no se generó»; `pitch` vacío con `prompt_version` presente significa
«la puerta lo retiró»), y descartó un campo `pitch_status` porque **movía el esquema congelado**. El
contrato .NET → frontend **no está congelado** y se despliega junto con el cliente, así que aquí la
opción limpia es gratis. C36 no tiene que reimplementar la codificación, y los dos estados nuevos de
este change (`withheld_unresolved` y `withheld_out_of_stock`) tienen dónde vivir.

**Los `warnings` pasan tal cual**, incluidos los que .NET no conoce: el vocabulario es cerrado pero
versionado, y la regla de etiqueta neutra para un código desconocido ya es de C36.

### D-L · Dobles de test y tests de integración

**Decisión.**

1. Se **extiende `IAiGatewayClient`** con `AssistSaleAsync` y `SubstitutesAsync`. La interfaz lo pide
   por escrito: *«each contracted endpoint is added by the change that first calls it»*.
2. Para que el siguiente método no vuelva a romper siete ficheros, se **extrae una clase base de test**
   (`ThrowingAiGatewayClient`, con todos los métodos lanzando) de la que heredan los siete dobles.
3. **Los tests de integración usan un doble del gateway**, con el patrón de `AiCatalogControllerTests`
   (`WithWebHostBuilder` + `ConfigureServices`), **y encienden el interruptor de forma explícita**.
   Copiar el patrón de C15 daría tests en verde que nunca hidratan una respuesta de la IA (H8).
4. Los DTO nuevos entran como filas de `AiContractSnapshotTests.ModelToSchema`.

| Alternativa | Descartada porque |
|---|---|
| Una interfaz segregada nueva (`IAiAssistGatewayClient`) | No toca los siete dobles, pero parte en dos la capability «typed gateway client» y contradice la regla escrita de la interfaz |

### D-M · Operación: límite, interruptor, caché y logs

| Tema | Decisión | Por qué |
|---|---|---|
| Límite de peticiones | Política propia `AiSalesAssist`, del orden de **10 por minuto y usuario**. Los sustitutos reutilizan la de la búsqueda | Coste de LLM y, sobre todo, la **cuota de tokens por minuto** de la organización que midió C32b. La S9 separa los límites de recuperación y de generación |
| Interruptor por POS | **Propio** (`AiSalesAssist:EnabledByDefault` + lista de POS), con la forma de `AiSearchOptions` | Poder apagar la generación por coste sin apagar la búsqueda |
| Caché | **Ninguna** | 0,00077 USD por petición (C30b) no la justifica, y D-I de C30 no se basó en el coste |
| Logs | Nunca el argumentario ya resuelto. La pregunta, sólo a nivel `Debug`, como la consulta de C15 | D-D y §15.11 |
| Telemetría | No se registra `ProductSearchEvent` | No es una búsqueda, y ningún indicador lo pide |

### D-N · La demo: activar la generación como última tarea — **cerrada**

**Decisión.** La última tarea de C34 activa la generación en la demo, con los **cuatro pasos ya
escritos** en [`DEFERRED_TASKS.md`](../../../openspec/DEFERRED_TASKS.md) (sección *«C30b — la demo no
genera argumentario»*): el parámetro SSM creado a mano, la lectura en `deploy.sh` sin `:?`, dos líneas
en `compose.demo.yaml` y el runbook. **Terraform no se toca.** La zona del change **pasa a incluir
`deploy/demo/` y `compose.demo.yaml`**.

**Lo que C34 añade a esos cuatro pasos:**

- **La configuración .NET de la demo**: `AiGateway__AssistTimeoutMs: "10000"` y
  `AiSalesAssist__EnabledByDefault: "true"`, junto a los `AiGateway__RetrievalTimeoutMs` y
  `AiSearch__EnabledByDefault` que ya están. Sin ella, **el card no se vería en la demo**, por la misma
  razón que H8.
- **Volver a medir la memoria del `t3.small`**. `DEFERRED_TASKS` lo pide literalmente *«if a generative
  route lands»*, y ésta es la primera. `jbg-demo-ai` tiene un tope de 512 MiB y estaba al 45 % sin
  generación.
- **La cuota de tokens por minuto** pasa a limitar el mostrador de la demo. Se comprueba y se declara.

**Por qué dentro de C34.** Sin la credencial, la sustitución de marcadores —la mitad del change— no se
puede enseñar en el vídeo, y el `pitchStatus` sería siempre `not_generated`.

---

## 3. Contraste con los apuntes del máster

| Apunte | Relación con C34 |
|---|---|
| S11 *«Agregar antes de generar»*, S14 *«la divergencia se calcula, no se opina»* | Coinciden: los números no los calcula el modelo. **El proyecto es más estricto**: los apuntes dejan escribir la cifra y comprueban que cae en el rango de las fuentes (S11, anclaje numérico). Aquí la cifra **nunca** llega al modelo, porque precio y stock son vivos y distintos en cada POS. Se declara como decisión, no como omisión |
| S4 Guard, *«las tres políticas de fallo»* | D-D: se degrada **la parte** que falla y la política se declara |
| S11 Citación, *«una citación inventada es peor que una sincera»* | El matiz de D-D sobre las citas se declara en vez de ocultarse |
| S9 Capa: reintentar 502/503/504 con *backoff* y 30 s de presupuesto | **Desviación consciente** en D-F: ningún reintento en el argumentario |
| S15 Partir, *«síncrono hasta que duela»* | D-F: síncrono con 10 s |
| S9 Retrieval: el post-filtrado sin instrumentar falla en silencio | D-I: ventana máxima y embudo en el log |
| S3 Cacheo: no cachear lo que depende de precio o inventario | D-M: sin caché |
| S3 Observabilidad: loguear la respuesta literal | **Desviación consciente**, por D-I de C30 y D-D |
| S9 Capa: límites distintos para recuperación y generación | D-M |
| **Lo que los apuntes no cubren** | La referencia de un marcador a su pieza (H1), pasar el plazo de un servicio a otro y los tests de contrato dirigidos por el consumidor |

En la rúbrica del PF, C34 cae en **Funcionalidad (25 %)** —*«el flujo principal resuelve el caso de
uso»*— y en **Producción (20 %)**, por la gestión de errores y de costes.

---

## 4. Mapa de deltas

### Specs

| Capability | Delta | Qué lleva |
|---|---|---|
| **`ai-sales-assist`** | **ADDED**, nueva | Las dos rutas, la autorización y la comprobación previa de la pieza anclada, la hidratación del grupo, los avisos de stock y el recálculo de `family_has_variants`, la sustitución de marcadores con sus retiradas, los cuatro vacíos de sustitutos, la degradación y la política de logs |
| `ai-gateway-client` | **MODIFIED** | Dos métodos tipados más, el 422 distinguible, el cliente `ai-assist` con su presupuesto, circuito propio y sin reintento en timeout, y el invariante de presupuesto |

### Fichas del plan

| Ficha | Cambio |
|---|---|
| **C34** | Corregida en el sitio el mismo día: rutas, zona, tests, y la anotación del 14 de septiembre marcada como refutada |
| C36 | **Corregida el mismo día, sólo en la ruta**: su caja de pregunta llama a `POST …/sales-assist` con `question` en el cuerpo, y ya no a `/sales-assist?question=`. Lo mismo en el párrafo del §4 del plan que cierra el hueco del corpus. El resto de C36 se decide al explorarla |

### Diseño

Nada cambia hoy. **Al archivar C34** habrá que actualizar el §6.4 (los 5 s de assist pasan a 10 s,
con el motivo) y precisar en el §7.7 que el marcador se refiere a la pieza anclada y que, sin ella, se
retira.

### `DEFERRED_TASKS.md`

| Entrada | Qué pasa con C34 |
|---|---|
| *C30b — la demo no genera argumentario* | **Se cierra** con D-N |
| *C32b — política de timeout y circuito de `/v1/assist/agent`* | **Sigue diferida**: D-A deja fuera el agente |
| *C32b — desglose del uso por etapa* | Sigue diferida, por el mismo motivo |
| *Instance sizing (C17)* | Se vuelve a medir en D-N |

---

## 5. Mediciones reproducibles

Las cinco se reproducen con el árbol en `d42e5d6`. Las de la base necesitan el contenedor local de
PostgreSQL (`jpv-pv-postgres`) con el mundo de C10 y el índice de C13 cargados. **Esos datos describen
el mundo simulado, no la tienda**: el stock y la cobertura por POS los generó C10.

### M-1 · Supervivencia de la ventana de sustitutos por POS

**Qué replica.** La pertenencia a la ventana de
[`SqlAlchemyProductSearch.neighbours_of`](../../../ai-service/src/jbg_ai/retrieval/search.py#L713),
con el mismo SQL que compone `compile_neighbours_sql` ([L366-395](../../../ai-service/src/jbg_ai/retrieval/search.py#L366-L395)):
mismo `piece_type` con `IS NOT DISTINCT FROM`, embedding no nulo, `is_active`, excluida la propia pieza,
`ORDER BY distancia, product_id` y `LIMIT`. La reordenación posterior de Python (talla,
disponibilidad) **no cambia qué candidatos entran**, así que el recuento de supervivientes es exacto.
Las piezas ancladas son todas las indexadas que el POS lleva, con cualquier cantidad, que es la
condición de D-G.

```bash
docker exec -i jpv-pv-postgres psql -U postgres -d joiabagur_pv <<'SQL'
WITH carried AS (
  SELECT i."PointOfSaleId" AS pos_id, i."ProductId" AS product_id, i."Quantity" AS qty
  FROM "Inventories" i JOIN "Products" p ON p."Id" = i."ProductId"
  WHERE i."IsActive" AND p."IsActive"
),
anchors AS (
  SELECT d.product_id, d.piece_type, d.embedding
  FROM ai.product_document d
  WHERE d.embedding IS NOT NULL AND d.is_active IS TRUE
),
win AS (
  SELECT a.product_id AS anchor_id, n.product_id AS cand_id, n.rk
  FROM anchors a
  CROSS JOIN LATERAL (
    SELECT d.product_id, row_number() OVER (ORDER BY d.embedding <=> a.embedding, d.product_id) AS rk
    FROM ai.product_document d
    WHERE d.embedding IS NOT NULL AND d.is_active IS TRUE
      AND d.product_id <> a.product_id
      AND d.piece_type IS NOT DISTINCT FROM a.piece_type
    ORDER BY d.embedding <=> a.embedding, d.product_id
    LIMIT 60
  ) n
),
per_anchor AS (
  SELECT c.pos_id, c.product_id AS anchor_id,
         count(w.cand_id) FILTER (WHERE w.rk <= 60) AS win60,
         count(w.cand_id) FILTER (WHERE w.rk <= 15) AS win15,
         count(w.cand_id) FILTER (WHERE w.rk <= 60 AND cc.qty > 0) AS surv60,
         count(w.cand_id) FILTER (WHERE w.rk <= 15 AND cc.qty > 0) AS surv15
  FROM carried c
  JOIN anchors a ON a.product_id = c.product_id
  LEFT JOIN win w ON w.anchor_id = c.product_id
  LEFT JOIN carried cc ON cc.pos_id = c.pos_id AND cc.product_id = w.cand_id
  GROUP BY c.pos_id, c.product_id
)
SELECT s."Name" AS pos,
       count(*) AS anchors,
       round(avg(win60),1) AS avg_win60,
       percentile_disc(0.10) WITHIN GROUP (ORDER BY surv60) AS p10_s60,
       percentile_disc(0.50) WITHIN GROUP (ORDER BY surv60) AS p50_s60,
       round(100.0*avg((surv60 < 5)::int),1) AS pct_lt5_w60,
       round(100.0*avg((surv60 = 0)::int),1) AS pct_zero_w60,
       percentile_disc(0.50) WITHIN GROUP (ORDER BY surv15) AS p50_s15,
       round(100.0*avg((surv15 < 5)::int),1) AS pct_lt5_w15
FROM per_anchor pa JOIN "PointOfSales" s ON s."Id" = pa.pos_id
GROUP BY s."Name"
ORDER BY pct_lt5_w60 DESC;
SQL
```

Salida (3,6 s):

```text
          pos           | anchors | avg_win60 | p10_s60 | p50_s60 | pct_lt5_w60 | pct_zero_w60 | p50_s15 | pct_lt5_w15
------------------------+---------+-----------+---------+---------+-------------+--------------+---------+-------------
 Fornells               |     239 |      58.9 |       5 |      11 |         7.1 |          0.4 |       4 |        71.1
 Aeroport de Menorca    |     416 |      57.8 |       7 |      16 |         5.3 |          1.2 |       5 |        45.2
 Estació Marítima, Maó  |     402 |      57.5 |       8 |      20 |         4.0 |          0.5 |       6 |        34.6
 Eivissa Marina         |     435 |      57.6 |      10 |      23 |         3.9 |          0.5 |       8 |        25.3
 Hotel Alcúdia          |     420 |      57.8 |       9 |      26 |         3.8 |          0.7 |       8 |        21.7
 Hotel Cala Galdana     |     464 |      57.8 |      12 |      26 |         3.0 |          0.4 |       9 |        19.2
 Hotel Son Bou          |     431 |      57.8 |      10 |      27 |         2.8 |          0.2 |       8 |        25.3
 Boutique Binibeca      |     452 |      58.5 |      12 |      24 |         1.5 |          0.4 |       7 |        23.0
 Ciutadella Centre      |     853 |      58.1 |      30 |      46 |         1.4 |          0.2 |      12 |         3.8
 Palma Jaume III        |     798 |      58.1 |      24 |      44 |         1.1 |          0.4 |      12 |         4.9
 Taller Joia Bagur, Maó |    1055 |      58.2 |      50 |      54 |         0.8 |          0.2 |      14 |         0.8
```

`avg_win60` es menor que 60 porque algunos tipos de pieza tienen menos de 61 documentos en el índice.

### M-1b · Lo mismo, sólo para las piezas ancladas sin stock en su tienda

Es M-1 con `WHERE c.qty = 0` en `per_anchor`, agregado sobre las diez tiendas (el Taller no tiene
ceros):

```bash
docker exec -i jpv-pv-postgres psql -U postgres -d joiabagur_pv <<'SQL'
WITH carried AS (
  SELECT i."PointOfSaleId" AS pos_id, i."ProductId" AS product_id, i."Quantity" AS qty
  FROM "Inventories" i JOIN "Products" p ON p."Id" = i."ProductId"
  WHERE i."IsActive" AND p."IsActive"
),
anchors AS (
  SELECT d.product_id, d.piece_type, d.embedding
  FROM ai.product_document d
  WHERE d.embedding IS NOT NULL AND d.is_active IS TRUE
),
win AS (
  SELECT a.product_id AS anchor_id, n.product_id AS cand_id, n.rk
  FROM anchors a
  CROSS JOIN LATERAL (
    SELECT d.product_id, row_number() OVER (ORDER BY d.embedding <=> a.embedding, d.product_id) AS rk
    FROM ai.product_document d
    WHERE d.embedding IS NOT NULL AND d.is_active IS TRUE
      AND d.product_id <> a.product_id
      AND d.piece_type IS NOT DISTINCT FROM a.piece_type
    ORDER BY d.embedding <=> a.embedding, d.product_id
    LIMIT 60
  ) n
),
per_anchor AS (
  SELECT c.pos_id, c.product_id AS anchor_id,
         count(w.cand_id) FILTER (WHERE w.rk <= 60 AND cc.qty > 0) AS surv60,
         count(w.cand_id) FILTER (WHERE w.rk <= 15 AND cc.qty > 0) AS surv15
  FROM carried c
  JOIN anchors a ON a.product_id = c.product_id
  LEFT JOIN win w ON w.anchor_id = c.product_id
  LEFT JOIN carried cc ON cc.pos_id = c.pos_id AND cc.product_id = w.cand_id
  WHERE c.qty = 0
  GROUP BY c.pos_id, c.product_id
)
SELECT count(*) AS anclas_sin_stock,
       percentile_disc(0.10) WITHIN GROUP (ORDER BY surv60) AS p10_s60,
       percentile_disc(0.50) WITHIN GROUP (ORDER BY surv60) AS p50_s60,
       round(100.0*avg((surv60 < 5)::int),1) AS pct_lt5_w60,
       percentile_disc(0.50) WITHIN GROUP (ORDER BY surv15) AS p50_s15,
       round(100.0*avg((surv15 < 5)::int),1) AS pct_lt5_w15
FROM per_anchor pa JOIN "PointOfSales" s ON s."Id" = pa.pos_id
WHERE s."Name" <> 'Taller Joia Bagur, Maó';
SQL
```

```text
 anclas_sin_stock | p10_s60 | p50_s60 | pct_lt5_w60 | p50_s15 | pct_lt5_w15
------------------+---------+---------+-------------+---------+-------------
              428 |      10 |      20 |         3.0 |       7 |        30.6
```

### M-2 · La familia de la pieza anclada, antes y después de hidratar

La familia es la que devuelve `family_roster()`: los miembros activos de `ai.product_document` con el
mismo `family_id`. El tope de 24 no se alcanza nunca, porque el máximo medido es 8. Tras hidratar,
quedan los miembros con inventario activo de producto activo en el POS de la petición.

```bash
docker exec -i jpv-pv-postgres psql -U postgres -d joiabagur_pv <<'SQL'
WITH carried AS (
  SELECT i."PointOfSaleId" AS pos_id, i."ProductId" AS product_id, i."Quantity" AS qty
  FROM "Inventories" i JOIN "Products" p ON p."Id" = i."ProductId"
  WHERE i."IsActive" AND p."IsActive"
),
doc AS (
  SELECT product_id, family_id FROM ai.product_document WHERE is_active IS TRUE
),
per_anchor AS (
  SELECT c.pos_id, c.product_id AS anchor_id, c.qty AS anchor_qty,
         count(m.product_id)                                   AS roster,
         count(cm.product_id)                                  AS carried_members,
         count(cm.product_id) FILTER (WHERE m.product_id <> c.product_id AND cm.qty = 0) AS other_zero
  FROM carried c
  JOIN doc a ON a.product_id = c.product_id AND a.family_id IS NOT NULL
  JOIN doc m ON m.family_id = a.family_id
  LEFT JOIN carried cm ON cm.pos_id = c.pos_id AND cm.product_id = m.product_id
  GROUP BY c.pos_id, c.product_id, c.qty
)
SELECT CASE WHEN s."Name" = 'Taller Joia Bagur, Maó' THEN 'Taller (origen de suministro)' ELSE 'tiendas (10 POS)' END AS grupo,
       count(*)                                                   AS anclas_con_familia,
       round(100.0*avg((carried_members < roster)::int),1)        AS pct_pierde_miembros,
       round(100.0*avg((roster >= 2 AND carried_members < 2)::int),1) AS pct_variants_falso,
       round(100.0*avg((other_zero > 0)::int),1)                  AS pct_members_oos,
       round(100.0*avg((anchor_qty BETWEEN 1 AND 2)::int),1)      AS pct_stock_critical,
       round(100.0*avg((anchor_qty = 0)::int),1)                  AS pct_ancla_sin_stock
FROM per_anchor pa JOIN "PointOfSales" s ON s."Id" = pa.pos_id
GROUP BY 1 ORDER BY 1 DESC;
SQL
```

```text
             grupo             | anclas_con_familia | pct_pierde_miembros | pct_variants_falso | pct_members_oos | pct_stock_critical | pct_ancla_sin_stock
-------------------------------+--------------------+---------------------+--------------------+-----------------+--------------------+---------------------
 tiendas (10 POS)              |               1897 |                55.6 |               19.2 |            11.2 |                4.0 |                 6.5
 Taller (origen de suministro) |                443 |                22.1 |                2.7 |             0.0 |                0.0 |                 0.0
```

Los porcentajes de las dos últimas columnas se calculan sobre las piezas **con familia**, que es donde
se ven los dos avisos a la vez. La cifra de `stock_critical` sobre todas las filas con stock está en
M-5, y cuadra (4,2 %).

### M-3 y M-4 · Latencia por petición y uso de los marcadores, sobre el artefacto de C30b

**El artefacto** es `ai-service/evals/results/c30b-assist-sweep-5a6e1b4b8621.json`: 120 peticiones M2
—40 piezas × tres anchos de sección—, `openai/gpt-4o-mini`, `assist/v1`. **El ancho que se sirve es el
de 2 secciones** (`DEFAULT_PITCH_SECTIONS` en
[`constants.py:108`](../../../ai-service/src/jbg_ai/assist/constants.py#L108)).

**Tres cautelas antes de leer las cifras:**

1. La latencia se tomó **desde una máquina de desarrollo en España, en serie y a través del
   interceptor TLS de Norton**. Es una **cota superior** del proveedor, como declara el propio informe
   de C30b.
2. Es la suma de las llamadas al proveedor; **no incluye** las búsquedas ni la red entre servicios.
3. La ruta sirve hoy `assist/v3`. Contrastado con `diff`: sus **dos tareas ancladas y sus reglas
   invariantes son idénticas a las de v1**. Sólo cambia la frase de presentación del sistema, que
   desde v2 dice *«unas veces sobre una pieza concreta del catálogo, otras sobre las piezas que una
   búsqueda ha traído»*. No es una garantía de que la distribución se mantenga, pero sí de que la
   instrucción que produce los marcadores es la misma.

Desde `ai-service/`:

```bash
PYTHONIOENCODING=utf-8 uv run --system-certs python - <<'PY'
import json, re
from collections import Counter

ART = "evals/results/c30b-assist-sweep-5a6e1b4b8621.json"
d = json.load(open(ART, encoding="utf-8"))
rows = d["rows"]
prov = d["provenance"]
print(f"artefacto: {ART} · modelo {prov['model']} · prompt {prov['prompt_version']} · filas {len(rows)}")

def pct(xs, p):
    xs = sorted(xs); k = (len(xs) - 1) * p; f = int(k); c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)

print("\nM-3 · suma de latencias de proveedor por petición (ms), por ancho de secciones")
for s in sorted({r["sections"] for r in rows}):
    rs = [r for r in rows if r["sections"] == s]
    el = [sum(r["call_latencies_ms"]) for r in rs]
    two = sum(1 for r in rs if r["provider_calls"] >= 2)
    over5 = sum(1 for x in el if x > 5000)
    print(f"  secciones={s} n={len(rs)} · reparación {two}/{len(rs)} ({100*two/len(rs):.1f} %) · "
          f"p50 {pct(el,.5):.0f} · p95 {pct(el,.95):.0f} · máx {max(el):.0f} · >5 s {over5}/{len(rs)} ({100*over5/len(rs):.1f} %)")

gens = [g["pitch"] for r in rows for g in (r.get("generation"), r.get("initial_generation")) if g and g.get("pitch")]
with_ph = [p for p in gens if "{{price}}" in p or "{{stock}}" in p]
print(f"\nM-4 · generaciones con texto (finales + iniciales): {len(gens)} · con marcadores: {len(with_ph)}")
print("  ocurrencias por generación · price:", sorted(Counter(p.count('{{price}}') for p in gens).items()),
      "· stock:", sorted(Counter(p.count('{{stock}}') for p in gens).items()))

before_stock = Counter(m.group(1).lower() for p in gens for m in re.finditer(r"(\S+(?:\s+\S+)?)\s+\{\{stock\}\}", p))
after_stock = Counter((m.group(1) or "").lower() for p in gens for m in re.finditer(r"\{\{stock\}\}\s*([^\s.,;]*)", p))
before_price = Counter(m.group(1).lower() for p in gens for m in re.finditer(r"(\S+(?:\s+\S+)?)\s+\{\{price\}\}", p))
numeric = re.compile(r"(tenemos|hay|quedan|contamos con|stock de|disponemos de)$")
tot = sum(before_stock.values())
num = sum(n for k, n in before_stock.items() if numeric.search(k))
print(f"  {{{{stock}}}} leído como número (tras tenemos/hay/stock de…): {num}/{tot} ({100*num/tot:.1f} %)")
print(f"  {{{{stock}}}} seguido de «unidades»: {sum(n for k,n in after_stock.items() if k.startswith('unidad'))}/{tot}")
print("  dos palabras antes de {{stock}}:", before_stock.most_common())
disp = sum(n for k, n in before_price.items() if k.endswith(("disponible por", "disponibles por")))
print(f"  «disponible(s) por {{{{price}}}}»: {disp}/{sum(before_price.values())}")
print("  dos palabras antes de {{price}}:", before_price.most_common(8))
PY
```

```text
artefacto: evals/results/c30b-assist-sweep-5a6e1b4b8621.json · modelo openai/gpt-4o-mini · prompt assist/v1 · filas 120

M-3 · suma de latencias de proveedor por petición (ms), por ancho de secciones
  secciones=1 n=40 · reparación 5/40 (12.5 %) · p50 2139 · p95 5249 · máx 10082 · >5 s 5/40 (12.5 %)
  secciones=2 n=40 · reparación 22/40 (55.0 %) · p50 3829 · p95 5237 · máx 6407 · >5 s 3/40 (7.5 %)
  secciones=3 n=40 · reparación 28/40 (70.0 %) · p50 4300 · p95 5782 · máx 6548 · >5 s 8/40 (20.0 %)

M-4 · generaciones con texto (finales + iniciales): 240 · con marcadores: 213
  ocurrencias por generación · price: [(0, 27), (1, 213)] · stock: [(0, 27), (1, 213)]
  {{stock}} leído como número (tras tenemos/hay/stock de…): 188/213 (88.3 %)
  {{stock}} seguido de «unidades»: 4/213
  dos palabras antes de {{stock}}: [('y tenemos', 114), ('actualmente tenemos', 38), ('stock de', 26), ('y en', 18), ('y hay', 6), ('inventario hay', 4), ('y con', 3), ('en stock', 2), ('modelo por', 2)]
  «disponible(s) por {{price}}»: 147/213
  dos palabras antes de {{price}}: [('disponible por', 135), ('es de', 52), ('disponibles por', 12), ('precio de', 10), ('pendientes por', 2), ('adquirir por', 2)]
```

El máximo de 10.082 ms del ancho de 1 sección es una única llamada, tomada antes de que el timeout
por llamada subiera a 4 s. Con el valor vigente habría cortado a 4 s y se habría servido sin
argumentario.

Los marcadores aparecen **siempre una vez cada uno, y siempre juntos**: 213 generaciones con uno de
cada y 27 sin ninguno. Esto es lo que permite resolverlos contra una sola pieza en M2 y M3.

### M-5 · Cobertura de stock por POS y los dos umbrales de «stock bajo»

```bash
docker exec -i jpv-pv-postgres psql -U postgres -d joiabagur_pv <<'SQL'
SELECT s."Name" AS pos, count(*) AS llevadas, sum((i."Quantity" > 0)::int) AS con_stock,
       round(100.0*sum((i."Quantity" > 0)::int)/(SELECT count(*) FROM ai.product_document WHERE is_active),1) AS pct_del_indice
FROM "Inventories" i JOIN "Products" p ON p."Id" = i."ProductId" JOIN "PointOfSales" s ON s."Id" = i."PointOfSaleId"
WHERE i."IsActive" AND p."IsActive"
GROUP BY s."Name" ORDER BY con_stock;

SELECT sum((i."Quantity" BETWEEN 1 AND 2)::int) AS de_1_a_2, sum((i."Quantity" BETWEEN 1 AND 5)::int) AS de_1_a_5,
       sum((i."Quantity" > 0)::int) AS con_stock,
       round(100.0*sum((i."Quantity" BETWEEN 1 AND 2)::int)/sum((i."Quantity" > 0)::int),1) AS pct_1_2,
       round(100.0*sum((i."Quantity" BETWEEN 1 AND 5)::int)/sum((i."Quantity" > 0)::int),1) AS pct_1_5,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY i."Quantity") FILTER (WHERE i."Quantity" > 0) AS mediana
FROM "Inventories" i JOIN "Products" p ON p."Id" = i."ProductId" JOIN "PointOfSales" s ON s."Id" = i."PointOfSaleId"
WHERE i."IsActive" AND p."IsActive" AND s."Name" <> 'Taller Joia Bagur, Maó';
SQL
```

```text
          pos           | llevadas | con_stock | pct_del_indice
------------------------+----------+-----------+----------------
 Fornells               |      241 |       212 |           18.2
 Aeroport de Menorca    |      416 |       273 |           23.4
 Estació Marítima, Maó  |      404 |       357 |           30.6
 Hotel Alcúdia          |      422 |       402 |           34.4
 Eivissa Marina         |      441 |       402 |           34.4
 Hotel Son Bou          |      434 |       411 |           35.2
 Hotel Cala Galdana     |      469 |       414 |           35.4
 Boutique Binibeca      |      457 |       424 |           36.3
 Palma Jaume III        |      813 |       806 |           69.0
 Ciutadella Centre      |      871 |       839 |           71.8
 Taller Joia Bagur, Maó |     1082 |      1082 |           92.6

 de_1_a_2 | de_1_a_5 | con_stock | pct_1_2 | pct_1_5 | mediana
----------+----------+-----------+---------+---------+---------
      191 |      653 |      4540 |     4.2 |    14.4 |      12
```

---

## 6. La medición pendiente, antes de fijar `AssistTimeoutMs`

**Latencia de extremo a extremo de M2 y M3, .NET → Python → proveedor, en Docker Compose y sin pasar
por el interceptor de Norton.** M-3 es una cota superior que sólo cuenta el proveedor; la cifra que
fija el presupuesto es la de la petición entera. Si la distribución real queda muy por debajo, los
10 s de D-F se pueden bajar, **pero nunca por debajo del peor caso declarado de Python** (el invariante
de D-F). Se toma en la propia implementación, con la demo o con el compose local, y se escribe con la
procedencia al lado, como hizo C30b con su 3 → 4 s.

---

## 7. Tests

**Los de la ficha que se mantienen:**

- `SalesAssist_ReplacesPlaceholdersWithRealValues`
- `Substitutes_ExcludeProductsWithoutStockAtTargetPos`
- `SalesAssist_AsOperatorOfAnotherPos_Returns403`
- `SalesAssist_StockWarningsComputedAfterHydration_NotTakenFromPython`
- `SalesAssist_WithQuestion_ReturnsCitationsCarryingClaimScope`

**Uno que se renombra**, porque la decisión cambió (D-D):
`SalesAssist_WhenPlaceholderUnresolved_ReturnsErrorInsteadOfRawTemplate` →
**`SalesAssist_WhenPlaceholderUnresolved_WithholdsThePitchInsteadOfShippingTheRawTemplate`**.

**Los que añade la exploración**, uno por decisión que lo necesita:

| Test | Decisión |
|---|---|
| `SalesAssist_AnchorNotCarriedAtPos_Returns404WithoutCallingAi` | D-G |
| `SalesAssist_FamilyHasVariantsDroppedWhenOneMemberSurvives` | D-G |
| `SalesAssist_UnknownPlaceholder_WithholdsPitch` | D-D |
| `SalesAssist_UnanchoredResponseWithPlaceholder_WithholdsPitch` | D-C |
| `SalesAssist_AnchorOutOfStock_WithholdsPitchWithoutQuestion_KeepsItWithQuestion` | D-E |
| `SalesAssist_WhenAiUnavailable_ServesAnchorAndFamilyFromCatalog` | D-J |
| `SalesAssist_ResolvedPitchIsNeverLogged` | D-D |
| `SalesAssist_QuestionTravelsInTheBodyNeverInTheUrl` | D-B |
| `AssistSaleAsync_WhenTimeout_DoesNotRetry` | D-F |
| `AssistTimeout_IsNotBelowTheAiServiceWorstCase` | D-F |
| `SubstitutesAsync_When422_ThrowsRequestRejected_NotUnavailable` | D-F |
| `Substitutes_AlwaysRequestsTheLargestWindow` | D-I |
| `Substitutes_DistinguishesTheFourEmptyOutcomes` | D-I |
| `AssistSaleAsync_WhenItsCircuitOpens_RetrievalKeepsWorking` | D-F |

Los nombres siguen la convención `Método_Condición_Resultado` de la suite. La historia de usuario los
puede fusionar o partir.
